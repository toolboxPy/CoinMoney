"""
Grid Trading 전략
가격 레벨별 자동 매수/매도 (횡보장 최적)
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pyupbit
import numpy as np
from utils.logger import info, warning, debug
from utils.state_manager import state_manager
from core.position_manager import position_manager
from master.global_risk import global_risk


class GridStrategy:
    """그리드 매매 전략"""

    def __init__(self, timeframe='30m'):
        self.timeframe = timeframe
        self.name = f"Grid-{timeframe}"

        # Grid 설정
        self.grid_levels = 5  # 그리드 레벨 수
        self.grid_spacing = 0.02  # 그리드 간격 (2%)
        self.take_profit = 0.015  # 익절 (1.5%)
        self.stop_loss = 0.05  # 손절 (5%)

        # 상태 관리
        self.grid_prices = {}  # {coin: [prices]}
        self.last_action_price = {}  # {coin: price}

        info(f"📊 {self.name} 전략 초기화")
        info(f"  그리드 레벨: {self.grid_levels}개")
        info(f"  간격: {self.grid_spacing * 100:.1f}%")

    def analyze(self, coin):
        """
        Grid 분석 - 현재 가격이 그리드 레벨에 있는지 체크

        Returns:
            dict: 신호 정보
        """
        try:
            # 현재가
            current_price = pyupbit.get_current_price(coin)

            if not current_price:
                return None

            # 그리드 초기화 (필요시)
            if coin not in self.grid_prices:
                self._setup_grid(coin, current_price)

            reasons = []

            # 포지션 체크
            has_position = state_manager.is_in_position('spot', coin)

            if not has_position:
                # 하단 그리드 근처 매수
                lowest_grid = self.grid_prices[coin][0]

                if current_price <= lowest_grid * 1.01:  # 1% 오차 허용
                    reasons.append(f'Grid 하단 진입 ({current_price:,.0f}원)')
                    reasons.append(f'목표가: {lowest_grid * (1 + self.take_profit):,.0f}원')

                    return {
                        'signal': 'BUY',
                        'score': 3.0,
                        'confidence': 0.7,
                        'reasons': reasons,
                        'recommendation': 'BUY'
                    }
            else:
                # 포지션 있을 때 - 익절/손절 체크
                position = state_manager.get_spot_position(coin)

                if position:
                    avg_price = position.get('avg_price', current_price)
                    profit_ratio = (current_price - avg_price) / avg_price

                    # 익절
                    if profit_ratio >= self.take_profit:
                        reasons.append(f'Grid 익절 (+{profit_ratio * 100:.1f}%)')
                        return {
                            'signal': 'SELL',
                            'score': -3.0,
                            'confidence': 0.9,
                            'reasons': reasons,
                            'recommendation': 'SELL'
                        }

                    # 손절
                    elif profit_ratio <= -self.stop_loss:
                        reasons.append(f'Grid 손절 ({profit_ratio * 100:.1f}%)')
                        return {
                            'signal': 'SELL',
                            'score': -3.0,
                            'confidence': 0.9,
                            'reasons': reasons,
                            'recommendation': 'SELL'
                        }

            return {
                'signal': 'HOLD',
                'score': 0.0,
                'confidence': 0.0,
                'reasons': ['Grid 대기 중'],
                'recommendation': 'HOLD'
            }

        except Exception as e:
            warning(f"❌ {coin} Grid 분석 오류: {e}")
            return None

    def _setup_grid(self, coin, current_price):
        """그리드 가격 설정"""
        grid_prices = []
        levels = self.grid_levels
        spacing = self.grid_spacing

        for i in range(-levels // 2, levels // 2 + 1):
            price = current_price * (1 + spacing * i)
            grid_prices.append(price)

        self.grid_prices[coin] = sorted(grid_prices)

        info(f"📊 {coin} Grid 설정 완료:")
        info(f"  하단: {self.grid_prices[coin][0]:,.0f}원")
        info(f"  상단: {self.grid_prices[coin][-1]:,.0f}원")

    def execute(self, coin):
        """Grid 전략 실행"""
        info(f"\n{'=' * 60}")
        info(f"📊 {self.name} 전략 실행: {coin}")
        info(f"{'=' * 60}")

        # 1. 리스크 체크
        can_trade, risk_reason = global_risk.can_open_position('spot')

        if not can_trade:
            warning(f"⛔ 거래 불가: {risk_reason}")
            return {'action': 'SKIP', 'reason': risk_reason}

        # 2. 현재 포지션 확인
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

        info(f"\n🎯 Grid 매수 신호!")
        info(f"  사유: {', '.join(signal['reasons'])}")

        # 투자 금액
        from traders.spot_trader import spot_trader
        balance = spot_trader.get_balance("KRW")
        investment = balance * 0.2  # 20%씩 분할

        if investment < 5000:
            warning(f"⚠️ 잔고 부족: {balance:,.0f}원")
            return {'action': 'SKIP', 'reason': '잔고 부족'}

        # 포지션 열기
        result = position_manager.open_spot_position(
            coin,
            investment,
            f"Grid 하단 진입"
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
            info(f"\n💰 Grid 청산: {signal['reasons'][0]}")

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

        # 현재 상태
        status = position_manager.get_position_status('spot', coin)

        if status:
            info(f"\n📊 Grid 포지션:")
            info(f"  진입가: {status['entry_price']:,.0f}원")
            info(f"  현재가: {status['current_price']:,.0f}원")
            info(f"  수익률: {status['return_percent']:+.2f}%")

        return {'action': 'HOLD', 'reason': '청산 조건 미달'}


# 전역 인스턴스
grid_strategy = GridStrategy('30m')

if __name__ == "__main__":
    print("🧪 Grid 전략 테스트\n")
    test_coin = "KRW-BTC"
    signal = grid_strategy.analyze(test_coin)

    if signal:
        print("=" * 60)
        print("📈 Grid 분석 결과")
        print("=" * 60)
        print(f"신호: {signal['signal']}")
        print(f"점수: {signal['score']:+.2f}")
        print(f"신뢰도: {signal['confidence'] * 100:.0f}%")
        print("=" * 60)