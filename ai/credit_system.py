"""
AI 크레딧 시스템
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI 호출 비용 관리 (무분별한 호출 방지)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import json
import os
from datetime import datetime, timedelta
from utils.logger import info, warning, error


class CreditSystem:
    """AI 크레딧 관리"""

    def __init__(self, daily_limit=50):
        """
        Args:
            daily_limit: 일일 크레딧 한도
        """
        self.daily_limit = daily_limit
        self.credit_file = "data/ai_credits.json"

        # 크레딧 비용
        self.costs = {
            'single_ai': 1,  # 단일 AI 호출
            'debate': 2,  # AI 간 토론
            'emergency': 3  # 긴급 분석
        }

        self.load_credits()

        info(f"💳 AI 크레딧 시스템 초기화")
        info(f"   일일 한도: {self.daily_limit} 크레딧")
        info(f"   현재 잔액: {self.get_remaining()} 크레딧")

    def load_credits(self):
        """크레딧 정보 로드"""
        if os.path.exists(self.credit_file):
            try:
                with open(self.credit_file, 'r') as f:
                    data = json.load(f)

                # 날짜 체크
                last_date = datetime.fromisoformat(data.get('date', '2000-01-01'))
                today = datetime.now().date()

                if last_date.date() == today:
                    # 같은 날 → 이어서 사용
                    self.used = data.get('used', 0)
                else:
                    # 다른 날 → 초기화
                    self.used = 0
                    info("📅 새로운 날! 크레딧 초기화")

            except Exception as e:
                error(f"❌ 크레딧 로드 실패: {e}")
                self.used = 0
        else:
            self.used = 0

        self.save_credits()

    def save_credits(self):
        """크레딧 정보 저장"""
        os.makedirs('data', exist_ok=True)

        data = {
            'date': datetime.now().isoformat(),
            'used': self.used,
            'daily_limit': self.daily_limit
        }

        with open(self.credit_file, 'w') as f:
            json.dump(data, f, indent=2)

    def get_remaining(self):
        """남은 크레딧"""
        return max(0, self.daily_limit - self.used)

    def can_use(self, action='single_ai'):
        """
        크레딧 사용 가능 여부

        Args:
            action: 'single_ai', 'debate', 'emergency'
        """
        cost = self.costs.get(action, 1)
        remaining = self.get_remaining()

        return remaining >= cost

    def use_credit(self, action='single_ai', reason=''):
        """
        크레딧 사용

        Args:
            action: 'single_ai', 'debate', 'emergency'
            reason: 사용 이유

        Returns:
            bool: 성공 여부
        """
        cost = self.costs.get(action, 1)

        if not self.can_use(action):
            warning(f"⚠️ 크레딧 부족! (필요: {cost}, 잔액: {self.get_remaining()})")
            return False

        self.used += cost
        self.save_credits()

        info(f"💳 크레딧 사용: -{cost} ({reason})")
        info(f"   잔액: {self.get_remaining()}/{self.daily_limit}")

        return True

    def get_status(self):
        """크레딧 상태"""
        return {
            'remaining': self.get_remaining(),
            'used': self.used,
            'daily_limit': self.daily_limit,
            'percentage': (self.used / self.daily_limit) * 100 if self.daily_limit > 0 else 0
        }


# 전역 인스턴스
credit_system = CreditSystem(daily_limit=50)

if __name__ == "__main__":
    print("🧪 크레딧 시스템 테스트\n")

    # 상태 확인
    status = credit_system.get_status()
    print(f"잔액: {status['remaining']}/{status['daily_limit']} ({status['percentage']:.0f}% 사용)")

    # 사용 테스트
    print("\n단일 AI 호출...")
    if credit_system.use_credit('single_ai', '테스트 호출'):
        print("✅ 성공")

    print("\nAI 토론...")
    if credit_system.use_credit('debate', '포트폴리오 선택'):
        print("✅ 성공")

    # 최종 상태
    status = credit_system.get_status()
    print(f"\n최종 잔액: {status['remaining']}/{status['daily_limit']}")