"""
DCA (Dollar Cost Averaging) 전략
분할 매수로 변동성 헤지
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pyupbit
from datetime import datetime, timedelta
from utils.logger import info, warning, debug
from utils.state_manager import state_manager
from core.position_manager import position_manager
from master.global_risk import global_risk


class DCAStrategy:
    """분할 매수 전략"""

    def __init__(self, timeframe='1h'):
        self.timeframe = timeframe
        self.name = f"DCA-{timeframe}"

        # DCA 설정
        self.intervals = 4  # 4회 분할
        self.interval_hours = 6  # 6시간마다
        self.min_buy_amount = 5000  # 최소 매수 금액

        # 상태 관리
        self.last_buy_time = {}  # {coin: datetime}
        self.buy_count = {}  # {coin: count}

        info(f"💰 {self.name} 전략 초기화")
        info(f"  분할 횟수: {self.intervals}회")
        info(f"  매수 간격: {self.interval_hours}시간")

    def analyze(self, coin):
        """
        DCA 분석 - 항상 매수 신호 (조건 충족 시)

        Returns:
            dict: {
                'signal': 'BUY' / 'HOLD',
                'score': float,
                'confidence': float,
                'reasons': []
            }
        """
        try:
            reasons = []

            # 현재 상태
            buy_count = self.buy_count.get(coin, 0)
            last_buy = self.last_buy_time.get(coin)

            # 분할 완료 체크
            if buy_count >= self.intervals:
                return {
                    'signal': 'HOLD',
                    'score': 0.0,
                    'confidence': 0.0,
                    'reasons': ['DCA 분할 매수 완료'],
                    'recommendation': 'HOLD'
                }

            # 시간 간격 체크
            if last_buy:
                elapsed = datetime.now() - last_buy
                if elapsed < timedelta(hours=self.interval_hours):
                    hours_left = self.interval_hours - (elapsed.seconds // 3600)
                    return {
                        'signal': 'HOLD',
                        'score': 0.0,
                        'confidence': 0.0,
                        'reasons': [f'대기 중 (남은 시간: {hours_left}시간)'],
                        'recommendation': 'HOLD'
                    }

            # 매수 신호
            reasons.append(f'DCA {buy_count + 1}/{self.intervals}회 매수')
            reasons.append(f'분할 매수로 리스크 분산')

            return {
                'signal': 'BUY',
                'score': 2.5,  # 중간 점수
                'confidence': 0.8,
                'reasons': reasons,
                'recommendation': 'BUY'
            }

        except Exception as e:
            warning(f"❌ {coin} DCA 분석 오류: {e}")
            return None

    def execute(self, coin):
        """DCA 전략 실행"""
        info(f"\n{'=' * 60}")
        info(f"💰 {self.name} 전략 실행: {coin}")
        info(f"{'=' * 60}")

        # 1. 리스크 체크
        can_trade, risk_reason = global_risk.can_open_position('spot')

        if not can_trade:
            warning(f"⛔ 거래 불가: {risk_reason}")
            return {'action': 'SKIP', 'reason': risk_reason}

        # 2. 현재 포지션 확인
        has_position = state_manager.is_in_position('spot', coin)

        if has_position:
            # 보유 중 - 청산 체크
            return self._check_exit(coin)
        else:
            # 미보유 - 진입 체크
            return self._check_entry(coin)

    def _check_entry(self, coin):
        """진입 조건 체크"""
        # 분석
        signal = self.analyze(coin)

        if not signal:
            return {'action': 'HOLD', 'reason': '분석 실패'}

        # 매수 신호 확인
        if signal['signal'] != 'BUY':
            info(f"⏸️ 대기: {signal['reasons'][0]}")
            return {'action': 'HOLD', 'reason': signal['reasons'][0]}

        # 매수 실행
        info(f"\n🎯 DCA 매수 신호!")
        info(f"  회차: {self.buy_count.get(coin, 0) + 1}/{self.intervals}")
        info(f"  사유: {', '.join(signal['reasons'])}")

        # 투자 금액 계산
        from traders.spot_trader import spot_trader
        balance = spot_trader.get_balance("KRW")

        # 전체 예산을 N등분
        split_amount = balance / self.intervals
        investment = max(split_amount, self.min_buy_amount)

        if investment < self.min_buy_amount:
            warning(f"⚠️ 잔고 부족: {balance:,.0f}원")
            return {'action': 'SKIP', 'reason': '잔고 부족'}

        # 포지션 열기
        result = position_manager.open_spot_position(
            coin,
            investment,
            f"DCA {self.buy_count.get(coin, 0) + 1}/{self.intervals}회 매수"
        )

        if result['success']:
            # 상태 업데이트
            self.last_buy_time[coin] = datetime.now()
            self.buy_count[coin] = self.buy_count.get(coin, 0) + 1

            return {
                'action': 'BUY',
                'price': result['price'],
                'quantity': result['quantity'],
                'investment': result['investment'],
                'signal': signal
            }
        else:
            return {'action': 'FAILED', 'reason': result.get('reason')}

    def _check_exit(self, coin):
        """청산 조건 체크"""
        # DCA는 단순 손익 기준으로만 청산
        should_exit, reason = position_manager.check_spot_exit(coin)

        if should_exit:
            info(f"\n💰 청산 신호: {reason}")

            # 포지션 닫기
            result = position_manager.close_spot_position(coin, reason)

            if result['success']:
                # 상태 초기화
                self.buy_count[coin] = 0
                self.last_buy_time[coin] = None

                return {
                    'action': 'SELL',
                    'pnl': result['pnl'],
                    'return_percent': result['return_percent'],
                    'reason': reason
                }
            else:
                return {'action': 'FAILED', 'reason': result.get('reason')}

        # 현재 상태 출력
        status = position_manager.get_position_status('spot', coin)

        if status:
            info(f"\n📊 DCA 포지션 유지:")
            info(f"  진입가: {status['entry_price']:,.0f}원")
            info(f"  현재가: {status['current_price']:,.0f}원")
            info(f"  수익률: {status['return_percent']:+.2f}%")
            info(f"  매수 회차: {self.buy_count.get(coin, 0)}/{self.intervals}")

        return {'action': 'HOLD', 'reason': '청산 조건 미달'}


# 전역 인스턴스
dca_strategy = DCAStrategy('1h')

if __name__ == "__main__":
    print("🧪 DCA 전략 테스트\n")

    test_coin = "KRW-BTC"

    print(f"💰 {test_coin} DCA 분석...\n")

    signal = dca_strategy.analyze(test_coin)

    if signal:
        print("=" * 60)
        print("📈 DCA 분석 결과")
        print("=" * 60)
        print(f"\n신호: {signal['signal']}")
        print(f"점수: {signal['score']:+.2f}")
        print(f"신뢰도: {signal['confidence'] * 100:.0f}%")

        if signal['reasons']:
            print(f"\n📋 근거:")
            for reason in signal['reasons']:
                print(f"  • {reason}")

        print("\n" + "=" * 60)
    else:
        print("❌ 분석 실패")