"""
Scalping 전략
빠른 매매로 작은 수익 반복 (Grid와 유사하지만 더 공격적)
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


class ScalpingStrategy:
    """스캘핑 전략"""

    def __init__(self, timeframe='5m'):
        self.timeframe = timeframe
        self.name = f"Scalping-{timeframe}"

        # Scalping 설정 (Grid보다 빠르고 작은 수익)
        self.quick_profit = 0.01  # 1% 빠른 익절
        self.quick_loss = 0.005  # 0.5% 빠른 손절
        self.rsi_oversold = 35  # RSI 과매도
        self.rsi_overbought = 65  # RSI 과매수

        info(f"⚡ {self.name} 전략 초기화")
        info(f"  목표 수익: {self.quick_profit * 100:.1f}%")
        info(f"  손절: {self.quick_loss * 100:.2f}%")

    def analyze(self, coin):
        """
        Scalping 분석 - RSI + 빠른 익절/손절

        Returns:
            dict: 신호 정보
        """
        try:
            # 데이터 (짧은 봉)
            df = pyupbit.get_ohlcv(coin, interval='minute5', count=50)

            if df is None or len(df) < 20:
                return None

            # RSI 계산
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]

            current_price = df['close'].iloc[-1]
            reasons = []

            # 포지션 체크
            has_position = state_manager.is_in_position('spot', coin)

            if not has_position:
                # RSI 과매도 → 매수
                if current_rsi <= self.rsi_oversold:
                    reasons.append(f'RSI 과매도 ({current_rsi:.1f})')
                    reasons.append('빠른 반등 기대')

                    return {
                        'signal': 'BUY',
                        'score': 3.5,
                        'confidence': 0.75,
                        'reasons': reasons,
                        'recommendation': 'BUY'
                    }
            else:
                # 포지션 있을 때 - 빠른 익절/손절
                position = state_manager.get_spot_position(coin)

                if position:
                    avg_price = position.get('avg_price', current_price)
                    profit_ratio = (current_price - avg_price) / avg_price

                    # 빠른 익절
                    if profit_ratio >= self.quick_profit:
                        reasons.append(f'Scalping 익절 (+{profit_ratio * 100:.1f}%)')
                        return {
                            'signal': 'SELL',
                            'score': -3.5,
                            'confidence': 0.95,
                            'reasons': reasons,
                            'recommendation': 'SELL'
                        }

                    # 빠른 손절
                    elif profit_ratio <= -self.quick_loss:
                        reasons.append(f'Scalping 손절 ({profit_ratio * 100:.2f}%)')
                        return {
                            'signal': 'SELL',
                            'score': -3.5,
                            'confidence': 0.95,
                            'reasons': reasons,
                            'recommendation': 'SELL'
                        }

                    # RSI 과매수 → 청산
                    elif current_rsi >= self.rsi_overbought:
                        reasons.append(f'RSI 과매수 청산 ({current_rsi:.1f})')
                        return {
                            'signal': 'SELL',
                            'score': -3.0,
                            'confidence': 0.8,
                            'reasons': reasons,
                            'recommendation': 'SELL'
                        }

            return {
                'signal': 'HOLD',
                'score': 0.0,
                'confidence': 0.0,
                'reasons': [f'Scalping 대기 (RSI: {current_rsi:.1f})'],
                'recommendation': 'HOLD'
            }

        except Exception as e:
            warning(f"❌ {coin} Scalping 분석 오류: {e}")
            return None

    def execute(self, coin):
        """Scalping 전략 실행"""
        info(f"\n{'=' * 60}")
        info(f"⚡ {self.name} 전략 실행: {coin}")
        info(f"{'=' * 60}")

        can_trade, risk_reason = global_risk.can_open_position('spot')

        if not can_trade:
            warning(f"⛔ 거래 불가: {risk_reason}")
            return {'action': 'SKIP', 'reason': risk_reason}

        has_position = state_manager.is_in_position('spot', coin)

        if has_position:
            return self._check_exit(coin)
        else:
            return self._check_entry(coin)

    def _check_entry(self, coin):
        """진입 조건 체크"""
        signal = self.analyze(coin)

        if not signal or signal['signal'] != 'BUY':
            return {'action': 'HOLD', 'reason': signal['reasons'][0] if signal else '분석 실패'}

        info(f"\n🎯 Scalping 매수 신호!")
        info(f"  사유: {', '.join(signal['reasons'])}")

        from traders.spot_trader import spot_trader
        balance = spot_trader.get_balance("KRW")
        investment = balance * 0.3  # 30% (빠른 회전)

        if investment < 5000:
            return {'action': 'SKIP', 'reason': '잔고 부족'}

        result = position_manager.open_spot_position(
            coin,
            investment,
            f"Scalping 진입"
        )

        if result['success']:
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
        signal = self.analyze(coin)

        if signal and signal['signal'] == 'SELL':
            info(f"\n💰 Scalping 청산: {signal['reasons'][0]}")

            result = position_manager.close_spot_position(coin, signal['reasons'][0])

            if result['success']:
                return {
                    'action': 'SELL',
                    'pnl': result['pnl'],
                    'return_percent': result['return_percent'],
                    'reason': signal['reasons'][0]
                }
            else:
                return {'action': 'FAILED', 'reason': result.get('reason')}

        return {'action': 'HOLD', 'reason': '청산 조건 미달'}


# 전역 인스턴스
scalping_strategy = ScalpingStrategy('5m')

if __name__ == "__main__":
    print("🧪 Scalping 전략 테스트\n")