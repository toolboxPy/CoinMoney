"""
주간 유지보수 스크립트
매주 일요일 자정 실행 (크론잡)

기능:
1. 프로토콜 정리 (저사용 약어 삭제, 유사 약어 통합)
2. 로그 파일 정리
3. 통계 집계
4. 백업 관리
"""
import sys
import os
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import datetime, timedelta
from ai.protocols.protocol_pruning import protocol_pruner
from utils.logger import info, warning


def run_weekly_maintenance():
    """주간 유지보수 메인 함수"""
    info("\n" + "=" * 60)
    info("🔧 주간 유지보수 시작")
    info(f"   시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    info("=" * 60 + "\n")

    try:
        # 1. 프로토콜 정리
        info("📋 작업 1/4: 프로토콜 정리")
        protocol_pruner.prune_protocol()

        # 2. 오래된 로그 정리
        info("\n📋 작업 2/4: 로그 파일 정리")
        cleanup_old_logs(days=30)

        # 3. 오래된 백업 정리
        info("\n📋 작업 3/4: 백업 파일 정리")
        cleanup_old_backups(keep_count=50)

        # 4. 주간 통계 생성
        info("\n📋 작업 4/4: 주간 통계 생성")
        generate_weekly_stats()

        info("\n" + "=" * 60)
        info("✅ 주간 유지보수 완료")
        info("=" * 60 + "\n")

        return True

    except Exception as e:
        warning(f"\n❌ 유지보수 중 오류 발생: {e}")
        return False


def cleanup_old_logs(days=30):
    """오래된 로그 파일 정리"""
    log_dir = Path("data/logs")

    if not log_dir.exists():
        info("   로그 폴더 없음 - 스킵")
        return

    cutoff_date = datetime.now() - timedelta(days=days)
    deleted_count = 0

    for log_file in log_dir.glob("*.log"):
        # 파일 수정 시간 체크
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)

        if mtime < cutoff_date:
            log_file.unlink()
            deleted_count += 1
            info(f"   🗑️ 삭제: {log_file.name}")

    if deleted_count == 0:
        info(f"   ✅ 정리 불필요 (모든 로그가 {days}일 이내)")
    else:
        info(f"   ✅ {deleted_count}개 로그 파일 삭제")


def cleanup_old_backups(keep_count=50):
    """오래된 백업 파일 정리 (최근 N개만 유지)"""
    backup_dir = Path("data/protocol_backups")

    if not backup_dir.exists():
        info("   백업 폴더 없음 - 스킵")
        return

    # 백업 파일 목록 (시간순 정렬)
    backups = sorted(
        backup_dir.glob("*.json"),
        key=lambda x: x.stat().st_mtime,
        reverse=True  # 최신순
    )

    # 오래된 것 삭제
    deleted_count = 0
    for backup in backups[keep_count:]:
        backup.unlink()
        deleted_count += 1
        info(f"   🗑️ 삭제: {backup.name}")

    if deleted_count == 0:
        info(f"   ✅ 정리 불필요 (백업 {len(backups)}개 ≤ {keep_count}개)")
    else:
        info(f"   ✅ {deleted_count}개 백업 파일 삭제 (최근 {keep_count}개 유지)")


def generate_weekly_stats():
    """주간 통계 생성"""
    try:
        import json
        from pathlib import Path

        protocol_file = Path("data/dynamic_protocol.json")

        if not protocol_file.exists():
            info("   프로토콜 파일 없음 - 스킵")
            return

        with open(protocol_file, 'r', encoding='utf-8') as f:
            protocol = json.load(f)

        # 통계
        total_abbrs = len(protocol.get('dynamic_abbreviations', {}))
        total_evolutions = len(protocol.get('evolution_history', []))
        version = protocol.get('version', 'N/A')

        # 가장 많이 쓰인 약어
        abbrs = protocol.get('dynamic_abbreviations', {})
        top_5 = sorted(
            abbrs.items(),
            key=lambda x: x[1].get('usage_count', 0),
            reverse=True
        )[:5]

        # 출력
        info(f"\n   📊 프로토콜 통계:")
        info(f"      버전: v{version}")
        info(f"      약어 수: {total_abbrs}개")
        info(f"      진화 횟수: {total_evolutions}회")

        if top_5:
            info(f"\n   🏆 TOP 5 약어:")
            for i, (abbr, data) in enumerate(top_5, 1):
                usage = data.get('usage_count', 0)
                meaning = data.get('meaning', 'N/A')
                info(f"      {i}. {abbr} = {meaning} ({usage}회)")

        # 통계 파일 저장
        stats_dir = Path("data/weekly_stats")
        stats_dir.mkdir(exist_ok=True)

        stats_file = stats_dir / f"stats_{datetime.now().strftime('%Y%m%d')}.json"

        stats = {
            'date': datetime.now().isoformat(),
            'version': version,
            'total_abbreviations': total_abbrs,
            'total_evolutions': total_evolutions,
            'top_5_abbreviations': [
                {
                    'abbr': abbr,
                    'meaning': data.get('meaning'),
                    'usage_count': data.get('usage_count', 0)
                }
                for abbr, data in top_5
            ]
        }

        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        info(f"\n   💾 통계 저장: {stats_file.name}")

    except Exception as e:
        warning(f"   ⚠️ 통계 생성 실패: {e}")


def main():
    """메인 실행"""
    success = run_weekly_maintenance()

    if success:
        exit(0)  # 성공
    else:
        exit(1)  # 실패


if __name__ == "__main__":
    main()