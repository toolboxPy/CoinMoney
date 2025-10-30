"""
포지션 관리자
모든 전략이 사용하는 공통 포지션 관리 + Trailing Stop
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import datetime
from config.master_config import PROFIT_TARGETS
from utils.logger import info, warning, trade_log
from utils.state_manager import state_manager
from traders.spot_trader import spot_trader
from traders.futures_trader import futures_trader


class PositionManager:
    """포지션 관리자"""

    def __init__(self):
        self.spot_targets = PROFIT_TARGETS['spot_minute30']
        self.futures_targets = PROFIT_TARGETS['futures_minute60']

    def open_spot_position(self, coin, investment, reason='전략 신호'):
        """
        현물 포지션 열기

        Args:
            coin: "KRW-BTC"
            investment: 투자 금액
            reason: 진입 사유

        Returns:
            dict: 결과
        """
        info(f"\n🔓 현물 포지션 열기 시도")
        info(f"  코인: {coin}")
        info(f"  금액: {investment:,.0f}원")
        info(f"  사유: {reason}")

        # 매수 실행
        result = spot_trader.buy(coin, investment)

        if result['success']:
            info(f"✅ 포지션 열기 성공!")

            # Trailing Stop 초기화
            self._init_trailing_stop('spot', coin, result['price'])

        return result

    def close_spot_position(self, coin, reason='청산'):
        """
        현물 포지션 닫기

        Args:
            coin: "KRW-BTC"
            reason: 청산 사유

        Returns:
            dict: 결과
        """
        info(f"\n🔒 현물 포지션 닫기")
        info(f"  코인: {coin}")
        info(f"  사유: {reason}")

        result = spot_trader.sell(coin, reason)

        if result['success']:
            info(f"✅ 포지션 닫기 성공!")
            info(f"  손익: {result['pnl']:+,.0f}원")
            info(f"  수익률: {result['return_percent']:+.2f}%")

        return result

    def open_futures_position(self, symbol, side, investment, reason='전략 신호'):
        """
        선물 포지션 열기

        Args:
            symbol: "BTCUSDT"
            side: 'LONG' or 'SHORT'
            investment: 투자 금액 (USDT)
            reason: 진입 사유

        Returns:
            dict: 결과
        """
        info(f"\n🔓 선물 포지션 열기 시도")
        info(f"  심볼: {symbol}")
        info(f"  방향: {side}")
        info(f"  금액: {investment:.2f} USDT")
        info(f"  사유: {reason}")

        # 포지션 열기
        result = futures_trader.open_position(symbol, side, investment)

        if result['success']:
            info(f"✅ 포지션 열기 성공!")

            # Trailing Stop 초기화
            self._init_trailing_stop('futures', symbol, result['price'])

        return result

    def close_futures_position(self, symbol, reason='청산'):
        """
        선물 포지션 닫기

        Args:
            symbol: "BTCUSDT"
            reason: 청산 사유

        Returns:
            dict: 결과
        """
        info(f"\n🔒 선물 포지션 닫기")
        info(f"  심볼: {symbol}")
        info(f"  사유: {reason}")

        result = futures_trader.close_position(symbol, reason)

        if result['success']:
            info(f"✅ 포지션 닫기 성공!")
            info(f"  손익: {result['pnl']:+,.0f}원")
            info(f"  수익률: {result['pnl_percent']:+.2f}%")

        return result

    def check_spot_exit(self, coin):
        """
        현물 청산 조건 체크 (Trailing Stop 포함)

        Returns:
            tuple: (should_exit: bool, reason: str)
        """
        position = state_manager.get_position('spot', coin)

        if not position:
            return False, None

        entry_price = position['entry_price']
        current_price = spot_trader.get_current_price(coin)

        # 수익률
        return_percent = (current_price - entry_price) / entry_price

        # 1. 손절 체크
        if return_percent <= self.spot_targets['stop_loss']:
            return True, f"손절 {return_percent * 100:.2f}%"

        # 2. 고정 익절 체크
        if return_percent >= self.spot_targets['take_profit_2']:
            return True, f"2차 익절 {return_percent * 100:.2f}%"

        if return_percent >= self.spot_targets['take_profit_1']:
            return True, f"1차 익절 {return_percent * 100:.2f}%"

        # 3. Trailing Stop 체크
        should_exit, trail_reason = self._check_trailing_stop(
            'spot', coin, current_price, self.spot_targets['trailing_stop']
        )

        if should_exit:
            return True, trail_reason

        return False, None

    def check_futures_exit(self, symbol):
        """
        선물 청산 조건 체크 (Trailing Stop 포함)

        Returns:
            tuple: (should_exit: bool, reason: str)
        """
        position = state_manager.get_position('futures', symbol)

        if not position:
            return False, None

        entry_price = position['entry_price']
        current_price = futures_trader.get_current_price(symbol)
        side = position['side']
        leverage = position.get('leverage', 5)

        # 수익률 계산
        if side == 'LONG':
            return_percent = (current_price - entry_price) / entry_price
        else:  # SHORT
            return_percent = (entry_price - current_price) / entry_price

        # 1. 손절 체크
        if return_percent <= self.futures_targets['stop_loss']:
            actual_loss = return_percent * leverage * 100
            return True, f"손절 {return_percent * 100:.2f}% (실제 {actual_loss:.2f}%)"

        # 2. 고정 익절 체크
        if return_percent >= self.futures_targets['take_profit_2']:
            actual_profit = return_percent * leverage * 100
            return True, f"2차 익절 {return_percent * 100:.2f}% (실제 {actual_profit:.2f}%)"

        if return_percent >= self.futures_targets['take_profit_1']:
            actual_profit = return_percent * leverage * 100
            return True, f"1차 익절 {return_percent * 100:.2f}% (실제 {actual_profit:.2f}%)"

        # 3. Trailing Stop 체크
        should_exit, trail_reason = self._check_trailing_stop(
            'futures', symbol, current_price, self.futures_targets['trailing_stop']
        )

        if should_exit:
            return True, trail_reason

        return False, None

    def _init_trailing_stop(self, exchange, coin, entry_price):
        """Trailing Stop 초기화"""
        position = state_manager.get_position(exchange, coin)

        if position:
            position['highest_price'] = entry_price
            position['trailing_active'] = False
            state_manager.update_position(exchange, coin, position)

            info(f"📍 Trailing Stop 초기화: {entry_price:,.2f}")

    def _check_trailing_stop(self, exchange, coin, current_price, trailing_percent):
        """
        Trailing Stop 체크

        Args:
            exchange: 'spot' or 'futures'
            coin: 코인/심볼
            current_price: 현재가
            trailing_percent: 추적 하락 비율

        Returns:
            tuple: (should_exit: bool, reason: str)
        """
        position = state_manager.get_position(exchange, coin)

        if not position:
            return False, None

        entry_price = position['entry_price']
        highest_price = position.get('highest_price', entry_price)

        # 수익 중인지 체크 (손실 구간에서는 Trailing 안 함)
        profit_percent = (current_price - entry_price) / entry_price

        if profit_percent <= 0:
            # 아직 손실 구간
            return False, None

        # 최고점 갱신
        if current_price > highest_price:
            position['highest_price'] = current_price
            position['trailing_active'] = True
            state_manager.update_position(exchange, coin, position)

            info(f"📈 최고점 갱신: {current_price:,.2f}")
            return False, None

        # Trailing 활성화 상태인지
        if not position.get('trailing_active', False):
            return False, None

        # 최고점에서 하락률 계산
        drop_from_high = (highest_price - current_price) / highest_price

        # Trailing Stop 발동
        if drop_from_high >= trailing_percent:
            total_profit = (current_price - entry_price) / entry_price
            return True, f"트레일링 스톱 (최고점 -{drop_from_high * 100:.2f}%, 총수익 {total_profit * 100:+.2f}%)"

        return False, None

    def get_position_status(self, exchange, coin):
        """
        포지션 상태 조회

        Returns:
            dict or None: 포지션 정보
        """
        position = state_manager.get_position(exchange, coin)

        if not position:
            return None

        # 현재가
        if exchange == 'spot':
            current_price = spot_trader.get_current_price(coin)
        else:
            current_price = futures_trader.get_current_price(coin)

        entry_price = position['entry_price']

        # 수익률 계산
        if exchange == 'futures' and position.get('side') == 'SHORT':
            return_percent = (entry_price - current_price) / entry_price
        else:
            return_percent = (current_price - entry_price) / entry_price

        # 레버리지 적용 (선물)
        if exchange == 'futures':
            leverage = position.get('leverage', 1)
            actual_return = return_percent * leverage
        else:
            actual_return = return_percent

        return {
            'coin': coin,
            'entry_price': entry_price,
            'current_price': current_price,
            'quantity': position['quantity'],
            'return_percent': return_percent * 100,
            'actual_return': actual_return * 100,
            'highest_price': position.get('highest_price', entry_price),
            'trailing_active': position.get('trailing_active', False),
            'entry_time': position.get('entry_time')
        }


# 전역 인스턴스
position_manager = PositionManager()

# 사용 예시
if __name__ == "__main__":
    print("🧪 Position Manager 테스트\n")

    # 현물 포지션 상태
    print("📊 현물 포지션:")
    spot_positions = state_manager.get_all_positions('spot')

    if spot_positions:
        for coin in spot_positions.keys():
            status = position_manager.get_position_status('spot', coin)
            if status:
                print(f"\n  {coin}:")
                print(f"    진입가: {status['entry_price']:,.0f}원")
                print(f"    현재가: {status['current_price']:,.0f}원")
                print(f"    수익률: {status['return_percent']:+.2f}%")
                print(f"    최고점: {status['highest_price']:,.0f}원")
                print(f"    추적 중: {'✅' if status['trailing_active'] else '❌'}")

                # 청산 체크
                should_exit, reason = position_manager.check_spot_exit(coin)
                if should_exit:
                    print(f"    ⚠️ 청산 신호: {reason}")
    else:
        print("  없음")

    # 선물 포지션 상태
    print("\n📊 선물 포지션:")
    futures_positions = state_manager.get_all_positions('futures')

    if futures_positions:
        for symbol in futures_positions.keys():
            status = position_manager.get_position_status('futures', symbol)
            if status:
                print(f"\n  {symbol}:")
                print(f"    진입가: ${status['entry_price']:,.2f}")
                print(f"    현재가: ${status['current_price']:,.2f}")
                print(f"    수익률: {status['return_percent']:+.2f}%")
                print(f"    실제 수익: {status['actual_return']:+.2f}%")
                print(f"    추적 중: {'✅' if status['trailing_active'] else '❌'}")

                # 청산 체크
                should_exit, reason = position_manager.check_futures_exit(symbol)
                if should_exit:
                    print(f"    ⚠️ 청산 신호: {reason}")
    else:
        print("  없음")

    print("\n✅ 테스트 완료!")
