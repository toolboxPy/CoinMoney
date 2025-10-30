# ai/multi_ai_debate_dynamic.py

"""
동적 진화 AI 토론 시스템
AI들이 토론 중 실시간으로 새 약어 생성 + 영구 저장
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
from datetime import datetime
from pathlib import Path
from utils.logger import info, warning, error
from ai.multi_ai_analyzer import multi_ai


class DynamicProtocol:
    """동적 프로토콜 (실시간 진화 + 영구 저장)"""

    def __init__(self):
        # 저장 경로
        self.save_file = "data/dynamic_protocol.json"
        self.backup_dir = "data/protocol_backups"

        # 디렉토리 생성
        Path("data").mkdir(exist_ok=True)
        Path(self.backup_dir).mkdir(exist_ok=True)

        # 기존 프로토콜 로드 또는 초기화
        if os.path.exists(self.save_file):
            self._load_from_file()
            info(f"🧬 기존 프로토콜 로드: v{self.version} ({len(self.dynamic_abbreviations)}개 약어)")
        else:
            self._initialize_new()
            info("🧬 새 프로토콜 초기화 (v1.0)")

    def _initialize_new(self):
        """새 프로토콜 초기화"""
        self.version = "1.0"
        self.dynamic_abbreviations = {}
        self.evolution_history = []
        self.created_at = datetime.now().isoformat()

        # 초기 저장
        self._save_to_file()

    def _load_from_file(self):
        """파일에서 프로토콜 로드"""
        try:
            with open(self.save_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.version = data.get('version', '1.0')
            self.dynamic_abbreviations = data.get('dynamic_abbreviations', {})
            self.evolution_history = data.get('evolution_history', [])
            self.created_at = data.get('created_at', datetime.now().isoformat())

        except Exception as e:
            warning(f"⚠️ 프로토콜 로드 실패: {e}")
            self._initialize_new()

    def _save_to_file(self):
        """파일에 프로토콜 저장"""
        try:
            # 백업 먼저 (10개까지만)
            if os.path.exists(self.save_file):
                backup_name = f"protocol_v{self.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                backup_path = os.path.join(self.backup_dir, backup_name)

                with open(self.save_file, 'r', encoding='utf-8') as f:
                    backup_data = f.read()

                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(backup_data)

                # 백업 10개까지만 유지
                backups = sorted(Path(self.backup_dir).glob('protocol_*.json'))
                if len(backups) > 10:
                    for old_backup in backups[:-10]:
                        old_backup.unlink()

            # 현재 상태 저장
            data = {
                'version': self.version,
                'dynamic_abbreviations': self.dynamic_abbreviations,
                'evolution_history': self.evolution_history,
                'created_at': self.created_at,
                'updated_at': datetime.now().isoformat()
            }

            with open(self.save_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            info(f"💾 프로토콜 저장 완료 (v{self.version})")

        except Exception as e:
            error(f"❌ 프로토콜 저장 실패: {e}")

    def add_abbreviation(self, abbr, meaning, reason):
        """새 약어 추가 + 저장"""
        if abbr in self.dynamic_abbreviations:
            return False

        self.dynamic_abbreviations[abbr] = {
            'meaning': meaning,
            'reason': reason,
            'added_at': datetime.now().isoformat(),
            'usage_count': 0
        }

        # 버전 증가
        version_parts = self.version.split('.')
        self.version = f"{version_parts[0]}.{int(version_parts[1]) + 1}"

        # 이력 저장
        self.evolution_history.append({
            'version': self.version,
            'abbr': abbr,
            'meaning': meaning,
            'timestamp': datetime.now().isoformat()
        })

        # 파일에 저장! 🔥
        self._save_to_file()

        info(f"✨ 새 약어 추가: {abbr} = {meaning} (v{self.version})")
        return True

    def use_abbreviation(self, abbr):
        """약어 사용 통계 (10회마다 저장)"""
        if abbr in self.dynamic_abbreviations:
            self.dynamic_abbreviations[abbr]['usage_count'] += 1

            # 10회 사용마다 저장
            if self.dynamic_abbreviations[abbr]['usage_count'] % 10 == 0:
                self._save_to_file()

    def get_protocol_guide(self):
        """현재 프로토콜 가이드 (동적 약어 포함)"""

        base_guide = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 AI Compression Protocol (Dynamic Evolution)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PURPOSE: Maximize information density, minimize tokens
TARGET: 80-90% token reduction

STRUCTURE:
[Regime][Confidence]|[Indicators]|[Patterns]|[News]|[Reasoning]

REGIMES:
SU=STRONG_UPTREND, WU=WEAK_UPTREND, SW=SIDEWAYS
WD=WEAK_DOWNTREND, SD=STRONG_DOWNTREND

CONFIDENCE:
🟢=80-100%, 🟡=60-80%, 🟠=40-60%, 🔴=0-40%

INDICATORS:
R=RSI, M=MACD, BB=Bollinger, MA=Moving Avg, V=Volume, P=Price

DIRECTIONS:
↗️=bullish, ↘️=bearish, →=neutral, ↑=strong up, ↓=strong down

PATTERNS:
GC=Golden Cross, DC=Death Cross, HH=Higher High, LL=Lower Low
HL=Higher Low, LH=Lower High, DJ=Doji, HM=Hammer, SS=Shooting Star

NEWS:
N+=Bullish(score), N-=Bearish(score), N==Neutral, N!=Emergency

OPERATORS:
+ combine, | separate, x multiply, % percentage, > greater, < less
"""

        # 동적 약어 섹션
        if self.dynamic_abbreviations:
            base_guide += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 EVOLVED ABBREVIATIONS (v{self.version})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
These abbreviations were created by AI consensus during live debates.
"""
            # 사용 빈도순 정렬
            sorted_abbrs = sorted(
                self.dynamic_abbreviations.items(),
                key=lambda x: x[1]['usage_count'],
                reverse=True
            )

            for abbr, data in sorted_abbrs:
                usage = data['usage_count']
                base_guide += f"{abbr}={data['meaning']} (used {usage}x)\n"

        base_guide += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        return base_guide

    def get_stats(self):
        """통계 조회"""
        return {
            'version': self.version,
            'total_abbreviations': len(self.dynamic_abbreviations),
            'total_evolutions': len(self.evolution_history),
            'created_at': self.created_at,
            'most_used': self._get_most_used_abbreviations(5)
        }

    def _get_most_used_abbreviations(self, top_n=5):
        """가장 많이 쓰인 약어"""
        sorted_abbrs = sorted(
            self.dynamic_abbreviations.items(),
            key=lambda x: x[1]['usage_count'],
            reverse=True
        )

        return [
            {
                'abbr': abbr,
                'meaning': data['meaning'],
                'usage_count': data['usage_count']
            }
            for abbr, data in sorted_abbrs[:top_n]
        ]


# 전역 동적 프로토콜 (싱글톤)
dynamic_protocol = DynamicProtocol()


class DynamicAIDebate:
    """동적 진화 AI 토론"""

    def __init__(self, topic, market_data):
        self.topic = topic
        self.market_data = market_data
        self.rounds = []
        self.final_consensus = None
        self.protocol = dynamic_protocol  # 전역 프로토콜 사용

        self.participants = {
            'claude': {'name': 'Claude', 'color': '🟣'},
            'gpt': {'name': 'GPT-4', 'color': '🔵'},
            'gemini': {'name': 'Gemini', 'color': '🟢'}
        }

    def start_debate(self, num_rounds=5):
        """동적 진화 토론"""
        info(f"\n{'=' * 60}")
        info(f"🗣️ 동적 진화 토론: {self.topic} (v{self.protocol.version})")
        info(f"{'=' * 60}\n")

        for i in range(1, num_rounds + 1):
            if i == 1:
                round_result = self._round1_initial()
            else:
                round_result = self._round_n_debate(i)

            self.rounds.append(round_result)

            # 🔥 핵심: 라운드 후 진화 체크
            if i < num_rounds:  # 마지막 라운드 전까지
                self._check_evolution_opportunity(round_result)

        # 최종 합의
        self.final_consensus = self._reach_consensus()

        info(f"\n{'=' * 60}")
        info(f"✅ 토론 완료: {self.final_consensus['regime']}")
        info(f"🧬 프로토콜: v{self.protocol.version}")
        info(f"📚 진화 횟수: {len(self.protocol.evolution_history)}")
        info(f"{'=' * 60}\n")

        return {
            'rounds': self.rounds,
            'consensus': self.final_consensus,
            'protocol_version': self.protocol.version,
            'evolutions': self.protocol.evolution_history
        }

    def _check_evolution_opportunity(self, round_result):
        """
        🔥 진화 기회 체크 (개선)

        단순히 긴 표현만 체크하는 게 아니라:
        1. 기존 약어로 표현 가능한지 체크
        2. 새 약어가 정말 필요한지 판단
        """
        opinions = round_result.get('opinions', {}) or round_result.get('debates', {})

        # 1단계: 긴 표현 감지
        long_expressions = []
        for ai_name, data in opinions.items():
            compressed = data.get('compressed', '')
            token_count = data.get('token_count', 0)

            # 40 토큰 이상 = 너무 김
            if token_count > 40:
                # 🔥 중요: 기존 약어로 표현 가능한지 체크
                can_be_shortened, missing_pattern = self._check_if_can_use_existing_abbr(compressed)

                if can_be_shortened:
                    # AI가 기존 약어를 안 쓴 경우
                    warning(f"\n⚠️ AI 규칙 위반 감지!")
                    warning(f"   {ai_name}이(가) 기존 약어를 사용하지 않음")
                    warning(f"   표현: {compressed[:50]}...")
                    applicable = self._get_applicable_abbrs(compressed)
                    if applicable:
                        warning(f"   가능한 약어: {', '.join(applicable)}")
                    # 메타 라운드 실행 안 함!
                    continue

                # 정말 새 약어가 필요한 경우만
                long_expressions.append({
                    'ai': ai_name,
                    'expression': compressed,
                    'tokens': token_count,
                    'missing_pattern': missing_pattern
                })

        # 2단계: 정말 필요한 경우만 메타 라운드
        if long_expressions:
            info(f"\n⚠️ 새 약어 필요 ({len(long_expressions)}개)")
            self._meta_round_propose_abbreviation(long_expressions)

    def _check_if_can_use_existing_abbr(self, expression):
        """
        표현이 기존 약어로 줄일 수 있는지 체크

        Returns:
            tuple: (can_be_shortened: bool, missing_pattern: str)
        """
        # 기존 약어들
        existing_abbrs = self.protocol.dynamic_abbreviations

        # 간단한 휴리스틱
        for abbr, data in existing_abbrs.items():
            pattern = data['meaning'].lower()

            # 패턴이 표현 안에 있으면
            if self._pattern_matches(pattern, expression):
                return True, None

        # 새 패턴 발견
        missing_pattern = self._extract_pattern(expression)
        return False, missing_pattern

    def _pattern_matches(self, pattern, expression):
        """패턴 매칭"""
        # 단순 키워드 매칭
        keywords = pattern.lower().split()
        expr_lower = expression.lower()

        # 2개 이상 키워드 일치 = 매칭
        matches = sum(1 for kw in keywords if kw in expr_lower)
        return matches >= 2

    def _extract_pattern(self, expression):
        """표현에서 반복 패턴 추출"""
        # 긴 표현의 핵심 부분만
        return expression[:50]

    def _get_applicable_abbrs(self, expression):
        """사용 가능한 약어 목록"""
        applicable = []

        for abbr, data in self.protocol.dynamic_abbreviations.items():
            if self._pattern_matches(data['meaning'], expression):
                applicable.append(f"{abbr}={data['meaning']}")

        return applicable

    def _meta_round_propose_abbreviation(self, long_expressions):
        """
        🧠 메타 라운드: 약어 제안

        AI들에게 물어봄:
        "이 긴 표현을 어떻게 줄일까?"
        """
        info(f"\n{'=' * 60}")
        info(f"🧠 메타 라운드: 언어 진화 제안")
        info(f"{'=' * 60}\n")

        # 가장 긴 표현 선택
        longest = max(long_expressions, key=lambda x: x['tokens'])

        info(f"📝 대상 표현: {longest['expression'][:50]}...")
        info(f"   토큰 수: {longest['tokens']}")

        # AI들에게 약어 제안 요청
        proposals = self._ask_abbreviation_proposals(longest['expression'])

        # 합의 도출
        if len(proposals) >= 2:  # 2개 이상 동의하면
            self._apply_evolution(proposals)

    def _ask_abbreviation_proposals(self, long_expression):
        """AI들에게 약어 제안 요청"""
        proposals = []

        prompt = f"""
You are in a meta-round to evolve our compression protocol.

CURRENT PROTOCOL: v{self.protocol.version}
LONG EXPRESSION DETECTED: "{long_expression}"
TOKEN COUNT: {len(long_expression.split())}

YOUR TASK:
Propose a NEW abbreviation to replace repeated patterns in this expression.

REQUIREMENTS:
1. Must be 2-6 characters
2. Must be intuitive
3. Must save at least 10 tokens

Return JSON ONLY:
{{
    "abbreviation": "RLVW",
    "meaning": "RSI Low, Volume Weak",
    "pattern_to_replace": "R<30+V<0.8x",
    "estimated_savings": 12,
    "reason": "This pattern appears frequently when RSI is low with weak volume"
}}

If NO good abbreviation possible, return: {{"skip": true}}
"""

        for ai_name in ['claude', 'gpt', 'gemini']:
            try:
                if ai_name == 'claude':
                    result = multi_ai._ask_claude(prompt)
                elif ai_name == 'gpt':
                    result = multi_ai._ask_openai(prompt)
                elif ai_name == 'gemini':
                    result = multi_ai._ask_gemini(prompt)
                else:
                    continue

                if result and not result.get('skip'):
                    proposals.append({
                        'ai': ai_name,
                        'proposal': result
                    })

                    abbr = result.get('abbreviation', 'N/A')
                    meaning = result.get('meaning', 'N/A')
                    info(f"  {self.participants[ai_name]['color']} {ai_name}: {abbr} = {meaning}")

            except Exception as e:
                warning(f"  ❌ {ai_name} 제안 실패: {e}")

        return proposals

    def _apply_evolution(self, proposals):
        """진화 적용 (합의된 약어 추가)"""

        # 가장 많이 제안된 약어
        abbr_votes = {}
        for p in proposals:
            abbr = p['proposal']['abbreviation']
            if abbr not in abbr_votes:
                abbr_votes[abbr] = []
            abbr_votes[abbr].append(p)

        # 2표 이상 받은 약어
        for abbr, votes in abbr_votes.items():
            if len(votes) >= 2:
                # 대표 제안 선택
                winning_proposal = votes[0]['proposal']

                # 프로토콜에 추가!
                success = self.protocol.add_abbreviation(
                    abbr=abbr,
                    meaning=winning_proposal['meaning'],
                    reason=f"Consensus from {len(votes)} AIs"
                )

                if success:
                    info(f"\n🎉 진화 성공!")
                    info(f"   {abbr} = {winning_proposal['meaning']}")
                    info(f"   합의: {len(votes)}/3 AI")
                    info(f"   예상 절감: {winning_proposal.get('estimated_savings', 'N/A')} 토큰\n")

                    # 다음 라운드부터 사용 가능!
                    return True

        info(f"\n⚠️ 진화 실패 (합의 부족)\n")
        return False

    def _round1_initial(self):
        """Round 1: 초기 분석"""
        info("🗣️ Round 1: 초기 분석\n")

        opinions = {}
        prompt = self._create_initial_prompt()

        for ai_name in ['claude', 'gpt', 'gemini']:
            result = self._ask_ai(ai_name, prompt)
            if result:
                opinions[ai_name] = result
                self._print_opinion(ai_name, result)

        return {
            'round': 1,
            'type': 'initial',
            'opinions': opinions
        }

    def _round_n_debate(self, round_num):
        """Round N: 토론 (동적 프로토콜 사용)"""
        info(f"\n🔄 Round {round_num}: 토론 (v{self.protocol.version})\n")

        debates = {}
        previous = self.rounds[-1].get('opinions') or self.rounds[-1].get('debates', {})

        for ai_name in previous.keys():
            prompt = self._create_debate_prompt(ai_name, previous)
            result = self._ask_ai(ai_name, prompt)

            if result:
                debates[ai_name] = result
                self._print_opinion(ai_name, result, is_debate=True)

        return {
            'round': round_num,
            'type': 'debate',
            'debates': debates
        }

    def _create_initial_prompt(self):
        """초기 프롬프트 (동적 프로토콜 포함)"""
        protocol_guide = self.protocol.get_protocol_guide()

        return f"""
{protocol_guide}

MARKET DATA (compress this):
Coin: {self.market_data.get('coin')}
Price: {self.market_data.get('price')}
24h: {self.market_data.get('price_change_24h', 0) * 100:+.1f}%
RSI: {self.market_data.get('rsi', 50):.0f}

YOUR TASK:
Analyze using compressed protocol (including evolved abbreviations if any).
Target: <30 tokens

Return JSON:
{{
  "compressed": "WU🟢|R48↗️M↗️GC|BB50%|V1.2x",
  "regime": "WEAK_UPTREND",
  "confidence": 0.85,
  "token_count": 25
}}
"""

    def _create_debate_prompt(self, ai_name, previous):
        """토론 프롬프트 (동적 프로토콜 포함)"""
        protocol_guide = self.protocol.get_protocol_guide()

        others = ""
        for other_ai, data in previous.items():
            if other_ai == ai_name:
                continue
            others += f"{self.participants[other_ai]['color']}{other_ai}:{data.get('compressed', 'N/A')}\n"

        return f"""
{protocol_guide}

PREVIOUS OPINIONS:
{others}

YOUR TASK:
1. Review others' analyses
2. Respond using evolved protocol
3. Update your position if needed

Target: <40 tokens

Return JSON:
{{
  "compressed": "Agree🟢GPT|MyView:WU🟢|R48↗️",
  "regime": "WEAK_UPTREND",
  "confidence": 0.88,
  "changed": false,
  "token_count": 22
}}
"""

    def _ask_ai(self, ai_name, prompt):
        """AI 호출 (통합)"""
        try:
            if ai_name == 'claude':
                raw = multi_ai._ask_claude(prompt)
            elif ai_name == 'gpt':
                raw = multi_ai._ask_openai(prompt)
            elif ai_name == 'gemini':
                raw = multi_ai._ask_gemini(prompt)
            else:
                return None

            # 토큰 수 추정
            compressed = raw.get('compressed', '')
            token_count = len(compressed.split()) + len(compressed) // 4
            raw['token_count'] = token_count

            # 사용된 동적 약어 체크
            for abbr in self.protocol.dynamic_abbreviations.keys():
                if abbr in compressed:
                    self.protocol.use_abbreviation(abbr)

            return raw

        except Exception as e:
            warning(f"❌ {ai_name} 응답 실패: {e}")
            return None

    def _print_opinion(self, ai_name, result, is_debate=False):
        """의견 출력"""
        participant = self.participants[ai_name]

        info(f"{participant['color']} {participant['name']}:")
        info(f"   압축: {result.get('compressed', 'N/A')}")
        info(f"   판단: {result.get('regime', 'N/A')}")
        info(f"   토큰: {result.get('token_count', 0)}개")

        if is_debate and result.get('changed'):
            info(f"   ⚠️ 의견 변경")

        info("")

    def _reach_consensus(self):
        """합의 도출"""
        all_opinions = []

        for round_data in self.rounds:
            opinions = round_data.get('opinions', {}) or round_data.get('debates', {})
            all_opinions.extend(opinions.values())

        regime_votes = {}
        confidence_sum = {}

        for opinion in all_opinions:
            regime = opinion.get('regime', 'UNKNOWN')
            confidence = opinion.get('confidence', 0.5)

            if regime not in regime_votes:
                regime_votes[regime] = 0
                confidence_sum[regime] = 0

            regime_votes[regime] += 1
            confidence_sum[regime] += confidence

        if not regime_votes:
            return {
                'regime': 'UNKNOWN',
                'agreement_rate': 0,
                'avg_confidence': 0,
                'votes': {},
                'timestamp': datetime.now().isoformat()
            }

        consensus_regime = max(regime_votes.items(), key=lambda x: x[1])[0]
        total_votes = sum(regime_votes.values())
        agreement_rate = regime_votes[consensus_regime] / total_votes
        avg_confidence = confidence_sum[consensus_regime] / regime_votes[consensus_regime]

        return {
            'regime': consensus_regime,
            'agreement_rate': agreement_rate,
            'avg_confidence': avg_confidence,
            'votes': regime_votes,
            'timestamp': datetime.now().isoformat()
        }


# 전역 함수
def start_dynamic_debate(topic, market_data, num_rounds=5):
    """동적 진화 토론 시작"""
    debate = DynamicAIDebate(topic, market_data)
    return debate.start_debate(num_rounds)


def get_protocol_stats():
    """프로토콜 통계 조회"""
    return dynamic_protocol.get_stats()


def reset_protocol():
    """프로토콜 초기화 (주의!)"""
    if os.path.exists(dynamic_protocol.save_file):
        # 백업 후 삭제
        backup_name = f"protocol_reset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_path = os.path.join(dynamic_protocol.backup_dir, backup_name)

        os.rename(dynamic_protocol.save_file, backup_path)
        info(f"🗑️ 프로토콜 초기화 (백업: {backup_name})")

    dynamic_protocol._initialize_new()


# 테스트
if __name__ == "__main__":
    print("🧪 동적 진화 AI 토론 테스트\n")

    # 현재 프로토콜 상태
    stats = get_protocol_stats()
    print(f"📊 현재 프로토콜 상태:")
    print(f"   버전: v{stats['version']}")
    print(f"   약어 수: {stats['total_abbreviations']}개")
    print(f"   진화 횟수: {stats['total_evolutions']}회\n")

    # 테스트 토론
    market_data = {
        'coin': 'BTC',
        'price': 95000000,
        'price_change_24h': 0.015,
        'volume_change': 1.2,
        'rsi': 48
    }

    result = start_dynamic_debate("BTC 분석", market_data, num_rounds=5)

    print(f"\n✅ 토론 완료!")
    print(f"🧬 최종 버전: v{result['protocol_version']}")
    print(f"📚 이번 진화: {len(result['evolutions'])}회")

    if result['evolutions']:
        print(f"\n진화 이력:")
        for evo in result['evolutions']:
            print(f"  v{evo['version']}: {evo['abbr']} = {evo['meaning']}")