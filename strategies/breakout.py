"""
Breakout 전략
저항선 돌파 시 추세 추종
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


class BreakoutStrategy:
    """돌파 매매 전략"""

    def __init__(self, timeframe='1h'):
        self.timeframe = timeframe
        self.name = f"Breakout-{timeframe}"

        # Breakout 설정
        self.lookback_period = 20  # 20봉 기준
        self.breakout_threshold = 0.02  # 2% 돌파
        self.volume_confirm = 1.5  # 거래량 1.5배 확인
        self.take_profit = 0.08  # 8% 익절
        self.stop_loss = 0.04  # 4% 손절

        info(f"🚀 {self.name} 전략 초기화")
        info(f"  기준 기간: {self.lookback_period}봉")
        info(f"  돌파 기준: {self.breakout_threshold * 100:.1f}%")

    def analyze(self, coin):
        """
        Breakout 분석 - 고점 돌파 + 거래량 확인

        Returns:
            dict: 신호 정보
        """
        try:
            # 데이터 가져오기
            if self.timeframe == '1h':
                interval = 'minute60'
            else:
                interval = 'minute30'

            df = pyupbit.get_ohlcv(coin, interval=interval, count=self.lookback_period + 10)

            if df is None or len(df) < self.lookback_period:
                return None

            # 최근 N봉 고점
            recent_high = df['high'].iloc[-self.lookback_period:].max()
            current_price = df['close'].iloc[-1]

            # 거래량 확인
            avg_volume = df['volume'].iloc[-self.lookback_period:-1].mean()
            current_volume = df['volume'].iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

            reasons = []

            # 포지션 체크
            has_position = state_manager.is_in_position('spot', coin)

            if not has_position:
                # 고점 돌파 체크
                breakout_price = recent_high * (1 + self.breakout_threshold)

                if current_price >= breakout_price and volume_ratio >= self.volume_confirm:
                    reasons.append(f'고점 돌파 ({recent_high:,.0f}원 → {current_price:,.0f}원)')
                    reasons.append(f'거래량 {volume_ratio:.1f}배 급증')

                    return {
                        'signal': 'BUY',
                        'score': 4.0,
                        'confidence': 0.9,
                        'reasons': reasons,
                        'recommendation': 'BUY'
                    }
            else:
                # 포지션 있을 때 - 익절/손절
                position = state_manager.get_spot_position(coin)

                if position:
                    avg_price = position.get('avg_price', current_price)
                    profit_ratio = (current_price - avg_price) / avg_price

                    # 익절
                    if profit_ratio >= self.take_profit:
                        reasons.append(f'Breakout 익절 (+{profit_ratio * 100:.1f}%)')
                        return {
                            'signal': 'SELL',
                            'score': -4.0,
                            'confidence': 0.95,
                            'reasons': reasons,
                            'recommendation': 'SELL'
                        }

                    # 손절
                    elif profit_ratio <= -self.stop_loss:
                        reasons.append(f'Breakout 손절 ({profit_ratio * 100:.1f}%)')
                        return {
                            'signal': 'SELL',
                            'score': -4.0,
                            'confidence': 0.95,
                            'reasons': reasons,
                            'recommendation': 'SELL'
                        }

            return {
                'signal': 'HOLD',
                'score': 0.0,
                'confidence': 0.0,
                'reasons': [f'돌파 대기 (고점: {recent_high:,.0f}원)'],
                'recommendation': 'HOLD'
            }

        except Exception as e:
            warning(f"❌ {coin} Breakout 분석 오류: {e}")
            return None

    def execute(self, coin):
        """Breakout 전략 실행"""
        info(f"\n{'=' * 60}")
        info(f"🚀 {self.name} 전략 실행: {coin}")
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

        info(f"\n🎯 Breakout 매수 신호!")
        info(f"  사유: {', '.join(signal['reasons'])}")

        from traders.spot_trader import spot_trader
        balance = spot_trader.get_balance("KRW")
        investment = balance * 0.7  # 70% 공격적 진입

        if investment < 5000:
            return {'action': 'SKIP', 'reason': '잔고 부족'}

        result = position_manager.open_spot_position(
            coin,
            investment,
            f"Breakout 돌파 진입"
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
            info(f"\n💰 Breakout 청산: {signal['reasons'][0]}")

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

        status = position_manager.get_position_status('spot', coin)

        if status:
            info(f"\n📊 Breakout 포지션:")
            info(f"  진입가: {status['entry_price']:,.0f}원")
            info(f"  현재가: {status['current_price']:,.0f}원")
            info(f"  수익률: {status['return_percent']:+.2f}%")

        return {'action': 'HOLD', 'reason': '청산 조건 미달'}


# 전역 인스턴스
breakout_strategy = BreakoutStrategy('1h')

if __name__ == "__main__":
    print("🧪 Breakout 전략 테스트\n")
    test_coin = "KRW-BTC"
    signal = breakout_strategy.analyze(test_coin)

    if signal:
        print("=" * 60)
        print("📈 Breakout 분석 결과")
        print("=" * 60)
        print(f"신호: {signal['signal']}")
        print(f"점수: {signal['score']:+.2f}")
        print("=" * 60)