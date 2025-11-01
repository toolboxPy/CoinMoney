# ai/protocol_pruning.py

"""
프로토콜 정리 시스템 (언어 파편화 방지)
주간 실행: 사용 안 하는 약어 삭제
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
from datetime import datetime
from utils.logger import info, warning


class ProtocolPruner:
    """프로토콜 정리 (Pruning)"""

    def __init__(self):
        self.protocol_file = "data/dynamic_protocol.json"

        # 정리 기준
        self.min_usage_threshold = 10  # 최소 10회 사용
        self.similarity_threshold = 0.7  # 유사도 70% 이상 = 중복

    def prune_protocol(self):
        """
        프로토콜 정리 실행

        1. 사용 안 하는 약어 삭제
        2. 중복/유사 약어 통합
        3. v2.0으로 승격
        """
        info(f"\n{'=' * 60}")
        info("🧹 프로토콜 정리 시작")
        info(f"{'=' * 60}\n")

        # 프로토콜 로드
        try:
            with open(self.protocol_file, 'r', encoding='utf-8') as f:
                protocol = json.load(f)
        except FileNotFoundError:
            warning("⚠️ 프로토콜 파일 없음")
            return

        original_count = len(protocol['dynamic_abbreviations'])
        info(f"📊 현재 약어: {original_count}개")

        if original_count == 0:
            info("✅ 정리 불필요 (약어 없음)")
            return

        # 1단계: 저사용 약어 삭제
        abbrs = protocol['dynamic_abbreviations']
        deleted = self._delete_unused_abbreviations(abbrs)

        # 2단계: 유사 약어 통합
        merged = self._merge_similar_abbreviations(abbrs)

        # 3단계: 버전 업그레이드
        if deleted or merged:
            protocol['version'] = self._upgrade_version(protocol['version'])
            protocol['last_pruned'] = datetime.now().isoformat()
            protocol['pruning_history'] = protocol.get('pruning_history', [])
            protocol['pruning_history'].append({
                'timestamp': datetime.now().isoformat(),
                'deleted': deleted,
                'merged': merged,
                'version': protocol['version']
            })

            # 저장
            with open(self.protocol_file, 'w', encoding='utf-8') as f:
                json.dump(protocol, f, indent=2, ensure_ascii=False)

            final_count = len(protocol['dynamic_abbreviations'])
            info(f"\n✅ 정리 완료!")
            info(f"   {original_count}개 → {final_count}개")
            info(f"   삭제: {len(deleted)}개")
            info(f"   통합: {len(merged)}개")
            info(f"   버전: v{protocol['version']}")
        else:
            info(f"\n✅ 정리 불필요 (모두 활성 상태)")

    def _delete_unused_abbreviations(self, abbrs):
        """저사용 약어 삭제"""
        deleted = []

        to_delete = []
        for abbr, data in list(abbrs.items()):
            usage = data.get('usage_count', 0)

            # 10회 미만 = 삭제
            if usage < self.min_usage_threshold:
                to_delete.append(abbr)
                deleted.append({
                    'abbr': abbr,
                    'meaning': data['meaning'],
                    'usage': usage,
                    'reason': 'Low usage'
                })

        # 삭제 실행
        for abbr in to_delete:
            usage = abbrs[abbr].get('usage_count', 0)
            del abbrs[abbr]
            info(f"  🗑️ 삭제: {abbr} (사용 {usage}회)")

        return deleted

    def _merge_similar_abbreviations(self, abbrs):
        """유사 약어 통합"""
        merged = []

        # 유사도 계산 (간단한 휴리스틱)
        abbr_list = list(abbrs.keys())

        for i, abbr1 in enumerate(abbr_list):
            if abbr1 not in abbrs:  # 이미 삭제됨
                continue

            for abbr2 in abbr_list[i + 1:]:
                if abbr2 not in abbrs:  # 이미 삭제됨
                    continue

                # 유사도 체크
                similarity = self._calculate_similarity(
                    abbrs[abbr1]['meaning'],
                    abbrs[abbr2]['meaning']
                )

                if similarity >= self.similarity_threshold:
                    # 사용 횟수 많은 것으로 통합
                    usage1 = abbrs[abbr1]['usage_count']
                    usage2 = abbrs[abbr2]['usage_count']

                    if usage1 >= usage2:
                        winner, loser = abbr1, abbr2
                    else:
                        winner, loser = abbr2, abbr1

                    # 통합
                    abbrs[winner]['usage_count'] += abbrs[loser]['usage_count']
                    abbrs[winner]['merged_from'] = abbrs[winner].get('merged_from', [])
                    abbrs[winner]['merged_from'].append(loser)

                    merged.append({
                        'winner': winner,
                        'loser': loser,
                        'similarity': similarity
                    })

                    del abbrs[loser]
                    info(f"  🔀 통합: {loser} → {winner} (유사도 {similarity * 100:.0f}%)")

        return merged

    def _calculate_similarity(self, text1, text2):
        """간단한 유사도 계산"""
        # Jaccard similarity (단어 집합)
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def _upgrade_version(self, current_version):
        """버전 메이저 업그레이드"""
        # v1.x → v2.0
        major = int(current_version.split('.')[0])
        return f"{major + 1}.0"


# 전역 인스턴스
protocol_pruner = ProtocolPruner()

# 주간 실행
if __name__ == "__main__":
    protocol_pruner.prune_protocol()