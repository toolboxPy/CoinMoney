"""
Trailing Stop 전략
고점 추적하며 익절 (추세 추종 + 수익 극대화)
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pyupbit
from utils.logger import info, warning, debug
from utils.state_manager import state_manager
from core.position_manager import position_manager
from master.global_risk import global_risk


class TrailingStrategy:
    """추적 매도 전략"""

    def __init__(self, timeframe='1h'):
        self.timeframe = timeframe
        self.name = f"Trailing-{timeframe}"

        # Trailing 설정
        self.trailing_percent = 0.05  # 고점 대비 -5% 매도
        self.activation_profit = 0.03  # 3% 이상 수익 시 활성화
        self.stop_loss = 0.04  # 4% 손절

        # 상태 관리
        self.highest_price = {}  # {coin: price}
        self.activated = {}  # {coin: bool}

        info(f"🎯 {self.name} 전략 초기화")
        info(f"  추적 비율: {self.trailing_percent * 100:.1f}%")
        info(f"  활성화: {self.activation_profit * 100:.1f}% 수익 후")

    def analyze(self, coin):
        """
        Trailing 분석 - 고점 추적

        Returns:
            dict: 신호 정보
        """
        try:
            current_price = pyupbit.get_current_price(coin)

            if not current_price:
                return None

            reasons = []

            # 포지션 체크
            has_position = state_manager.is_in_position('spot', coin)

            if not has_position:
                # 포지션 없으면 HOLD (다른 전략으로 진입 필요)
                return {
                    'signal': 'HOLD',
                    'score': 0.0,
                    'confidence': 0.0,
                    'reasons': ['Trailing: 포지션 없음'],
                    'recommendation': 'HOLD'
                }

            # 포지션 있을 때
            position = state_manager.get_spot_position(coin)

            if position:
                avg_price = position.get('avg_price', current_price)
                profit_ratio = (current_price - avg_price) / avg_price

                # 고점 갱신
                if coin not in self.highest_price or current_price > self.highest_price[coin]:
                    self.highest_price[coin] = current_price
                    info(f"🔝 {coin} 고점 갱신: {current_price:,.0f}원")

                # 활성화 체크
                if not self.activated.get(coin, False) and profit_ratio >= self.activation_profit:
                    self.activated[coin] = True
                    info(f"✅ {coin} Trailing 활성화!")

                # Trailing 활성화 시
                if self.activated.get(coin, False):
                    drop_from_high = (self.highest_price[coin] - current_price) / self.highest_price[coin]

                    if drop_from_high >= self.trailing_percent:
                        reasons.append(f'Trailing: 고점 대비 -{drop_from_high * 100:.1f}%')
                        reasons.append(f'익절: +{profit_ratio * 100:.1f}%')

                        return {
                            'signal': 'SELL',
                            'score': -4.0,
                            'confidence': 0.95,
                            'reasons': reasons,
                            'recommendation': 'SELL'
                        }

                # 손절
                if profit_ratio <= -self.stop_loss:
                    reasons.append(f'Trailing 손절 ({profit_ratio * 100:.1f}%)')
                    return {
                        'signal': 'SELL',
                        'score': -4.0,
                        'confidence': 0.95,
                        'reasons': reasons,
                        'recommendation': 'SELL'
                    }

                # 추적 중
                reasons.append(f'고점 추적 중 ({self.highest_price[coin]:,.0f}원, +{profit_ratio * 100:.1f}%)')
                return {
                    'signal': 'HOLD',
                    'score': 0.0,
                    'confidence': 0.0,
                    'reasons': reasons,
                    'recommendation': 'HOLD'
                }

            return {
                'signal': 'HOLD',
                'score': 0.0,
                'confidence': 0.0,
                'reasons': ['Trailing 대기'],
                'recommendation': 'HOLD'
            }

        except Exception as e:
            warning(f"❌ {coin} Trailing 분석 오류: {e}")
            return None

    def execute(self, coin):
        """Trailing 전략 실행"""
        info(f"\n{'=' * 60}")
        info(f"🎯 {self.name} 전략 실행: {coin}")
        info(f"{'=' * 60}")

        has_position = state_manager.is_in_position('spot', coin)

        if not has_position:
            # Trailing은 진입 전략이 아님
            return {'action': 'HOLD', 'reason': 'Trailing은 청산 전용'}
        else:
            return self._check_exit(coin)

    def _check_exit(self, coin):
        """청산 조건 체크"""
        signal = self.analyze(coin)

        if signal and signal['signal'] == 'SELL':
            info(f"\n💰 Trailing 청산: {signal['reasons'][0]}")

            result = position_manager.close_spot_position(coin, signal['reasons'][0])

            if result['success']:
                # 상태 초기화
                self.highest_price[coin] = None
                self.activated[coin] = False

                return {
                    'action': 'SELL',
                    'pnl': result['pnl'],
                    'return_percent': result['return_percent'],
                    'reason': signal['reasons'][0]
                }
            else:
                return {'action': 'FAILED', 'reason': result.get('reason')}

        status = position_manager.get_position_status('spot', coin)

        if status:
            info(f"\n📊 Trailing 포지션:")
            info(f"  진입가: {status['entry_price']:,.0f}원")
            info(f"  현재가: {status['current_price']:,.0f}원")
            info(f"  고점: {self.highest_price.get(coin, 0):,.0f}원")
            info(f"  수익률: {status['return_percent']:+.2f}%")
            info(f"  활성화: {'✅' if self.activated.get(coin) else '❌'}")

        return {'action': 'HOLD', 'reason': '청산 조건 미달'}


# 전역 인스턴스
trailing_strategy = TrailingStrategy('1h')

if __name__ == "__main__":
    print("🧪 Trailing 전략 테스트\n")