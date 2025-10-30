"""
선물 트레이더 (바이낸스)
레버리지 5배 + ISOLATED 마진
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from binance.client import Client
from binance.exceptions import BinanceAPIException
import time
from datetime import datetime
from config.master_config import (
    BINANCE_API_KEY, BINANCE_API_SECRET,
    FUTURES_LEVERAGE, FUTURES_MARGIN_MODE,
    PROFIT_TARGETS, POSITION_SIZING
)
from utils.logger import info, warning, error, trade_log
from utils.state_manager import state_manager
from utils.fee_calculator import fee_calculator
from utils.connection_manager import with_retry


class FuturesTrader:
    """선물 트레이더 (바이낸스)"""

    def __init__(self):
        # 바이낸스 클라이언트
        if BINANCE_API_KEY and BINANCE_API_SECRET:
            self.client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
            self.connected = True
            info("✅ 바이낸스 선물 트레이더 초기화 완료")

            # 레버리지 및 마진 모드 설정
            self._setup_futures()
        else:
            self.client = None
            self.connected = False
            warning("⚠️ 바이낸스 API 키 없음 - 조회만 가능")

        self.leverage = FUTURES_LEVERAGE
        self.targets = PROFIT_TARGETS['futures_minute60']
        self.sizing = POSITION_SIZING['futures']

    def _setup_futures(self):
        """선물 설정 (레버리지, 마진 모드)"""
        try:
            # 주요 코인들 설정
            symbols = ['BTCUSDT', 'ETHUSDT']

            for symbol in symbols:
                try:
                    # 레버리지 설정
                    self.client.futures_change_leverage(
                        symbol=symbol,
                        leverage=self.leverage
                    )

                    # 마진 모드 설정 (ISOLATED)
                    self.client.futures_change_margin_type(
                        symbol=symbol,
                        marginType=FUTURES_MARGIN_MODE
                    )

                    info(f"  ✅ {symbol}: {self.leverage}배 레버리지, {FUTURES_MARGIN_MODE} 마진")

                except BinanceAPIException as e:
                    if e.code == -4046:
                        # 이미 설정됨
                        pass
                    else:
                        warning(f"  ⚠️ {symbol} 설정 실패: {e}")

        except Exception as e:
            warning(f"⚠️ 선물 설정 오류: {e}")

    @with_retry
    def get_balance(self):
        """
        USDT 잔고 조회

        Returns:
            float: 사용 가능한 USDT
        """
        if not self.connected:
            return 0

        try:
            account = self.client.futures_account()

            for asset in account['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['availableBalance'])

            return 0

        except Exception as e:
            error(f"❌ 잔고 조회 오류: {e}")
            return 0

    @with_retry
    def get_current_price(self, symbol):
        """
        현재가 조회

        Args:
            symbol: "BTCUSDT"

        Returns:
            float: 현재가 (USDT)
        """
        if not self.connected:
            # API 없어도 현재가는 조회 가능
            try:
                ticker = self.client.futures_symbol_ticker(symbol=symbol)
                return float(ticker['price'])
            except:
                return 0

        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            error(f"❌ 현재가 조회 오류: {e}")
            return 0

    @with_retry
    def get_position(self, symbol):
        """
        포지션 조회

        Returns:
            dict or None: 포지션 정보
        """
        if not self.connected:
            return None

        try:
            positions = self.client.futures_position_information(symbol=symbol)

            for pos in positions:
                qty = float(pos['positionAmt'])

                if qty != 0:
                    return {
                        'symbol': symbol,
                        'side': 'LONG' if qty > 0 else 'SHORT',
                        'quantity': abs(qty),
                        'entry_price': float(pos['entryPrice']),
                        'unrealized_pnl': float(pos['unRealizedProfit']),
                        'leverage': int(pos['leverage'])
                    }

            return None

        except Exception as e:
            error(f"❌ 포지션 조회 오류: {e}")
            return None

    def calculate_position_size(self, available_balance):
        """
        포지션 크기 계산

        Args:
            available_balance: 사용 가능한 USDT

        Returns:
            float: 투자 금액 (USDT)
        """
        # 설정된 비율로 계산
        position = available_balance * self.sizing['percent_per_trade']

        # 최소/최대 제한 (원화를 USDT로 환산, 임시로 1400원)
        min_usdt = self.sizing['min_investment'] / 1400
        max_usdt = self.sizing['max_investment'] / 1400

        position = max(position, min_usdt)
        position = min(position, max_usdt)

        return position

    def open_position(self, symbol, side='LONG', investment=None):
        """
        포지션 열기

        Args:
            symbol: "BTCUSDT"
            side: 'LONG' or 'SHORT'
            investment: 투자 금액 (USDT)

        Returns:
            dict: 결과
        """
        if not self.connected:
            error("❌ API 키 없음 - 거래 불가")
            return {'success': False, 'reason': 'No API key'}

        # 이미 포지션 있는지 확인
        if state_manager.is_in_position('futures', symbol):
            warning(f"⚠️ {symbol} 이미 포지션 보유 중")
            return {'success': False, 'reason': 'Already in position'}

        try:
            # 잔고 확인
            balance = self.get_balance()

            min_usdt = self.sizing['min_investment'] / 1400

            if balance < min_usdt:
                error(f"❌ 잔고 부족: {balance:.2f} USDT")
                return {'success': False, 'reason': 'Insufficient balance'}

            # 투자 금액 결정
            if investment is None:
                investment = self.calculate_position_size(balance)

            investment = min(investment, balance)

            # 현재가
            current_price = self.get_current_price(symbol)

            # 레버리지 적용된 포지션 크기
            position_size = investment * self.leverage

            # 수량 계산
            quantity = position_size / current_price

            # 수량 정밀도 조정 (바이낸스 규칙)
            quantity = self._adjust_quantity(symbol, quantity)

            info(f"\n🚀 {'롱' if side == 'LONG' else '숏'} 포지션 열기:")
            info(f"  심볼: {symbol}")
            info(f"  투자금: {investment:.2f} USDT")
            info(f"  레버리지: {self.leverage}배")
            info(f"  포지션 크기: {position_size:.2f} USDT")
            info(f"  가격: {current_price:,.2f} USDT")
            info(f"  수량: {quantity:.6f}")

            # 주문 실행
            order_side = Client.SIDE_BUY if side == 'LONG' else Client.SIDE_SELL

            order = self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=quantity
            )

            if order:
                # 주문 완료 대기
                time.sleep(1)

                # 포지션 확인
                position = self.get_position(symbol)

                if position:
                    # 상태 저장
                    position_data = {
                        'entry_price': position['entry_price'],
                        'quantity': position['quantity'],
                        'side': side,
                        'investment': investment,
                        'leverage': self.leverage,
                        'entry_time': datetime.now().isoformat(),
                        'order_id': order['orderId']
                    }

                    state_manager.update_position('futures', symbol, position_data)

                    # 로그
                    trade_log('BUY', symbol, position['entry_price'], quantity,
                              f"{side} {self.leverage}X")

                    return {
                        'success': True,
                        'order_id': order['orderId'],
                        'price': position['entry_price'],
                        'quantity': quantity,
                        'side': side
                    }

            error("❌ 주문 실패")
            return {'success': False, 'reason': 'Order failed'}

        except Exception as e:
            error(f"❌ 포지션 열기 오류: {e}")
            return {'success': False, 'reason': str(e)}

    def close_position(self, symbol, reason='익절/손절'):
        """
        포지션 청산

        Args:
            symbol: "BTCUSDT"
            reason: 청산 사유

        Returns:
            dict: 결과
        """
        if not self.connected:
            error("❌ API 키 없음 - 청산 불가")
            return {'success': False}

        # 포지션 확인
        saved_position = state_manager.get_position('futures', symbol)

        if not saved_position:
            warning(f"⚠️ {symbol} 포지션 없음")
            return {'success': False, 'reason': 'No position'}

        try:
            # 현재 포지션 조회
            current_position = self.get_position(symbol)

            if not current_position:
                warning(f"⚠️ {symbol} 실제 포지션 없음")
                state_manager.update_position('futures', symbol, None)
                return {'success': False, 'reason': 'No actual position'}

            side = current_position['side']
            quantity = current_position['quantity']
            entry_price = saved_position['entry_price']

            # 현재가
            current_price = self.get_current_price(symbol)

            info(f"\n💰 포지션 청산:")
            info(f"  심볼: {symbol}")
            info(f"  방향: {side}")
            info(f"  수량: {quantity:.6f}")
            info(f"  진입가: {entry_price:,.2f} USDT")
            info(f"  현재가: {current_price:,.2f} USDT")

            # 청산 주문 (반대 방향)
            close_side = Client.SIDE_SELL if side == 'LONG' else Client.SIDE_BUY

            order = self.client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=quantity
            )

            if order:
                # 주문 완료 대기
                time.sleep(1)

                # 손익 계산
                if side == 'LONG':
                    pnl_percent = (current_price - entry_price) / entry_price
                else:  # SHORT
                    pnl_percent = (entry_price - current_price) / entry_price

                # 레버리지 적용
                pnl_percent *= self.leverage

                # 실제 손익 (USDT)
                investment = saved_position['investment']
                pnl_usdt = investment * pnl_percent

                # 수수료 계산
                fees = fee_calculator.calculate_round_trip_cost(
                    'futures', investment, self.leverage
                )
                pnl_usdt -= fees['total_fee'] / 1400  # 원화 → USDT

                # 원화로 환산 (임시로 1400원)
                pnl_krw = pnl_usdt * 1400

                is_win = pnl_krw > 0

                info(f"  청산가: {current_price:,.2f} USDT")
                info(f"  손익: {pnl_usdt:+.2f} USDT ({pnl_krw:+,.0f}원)")
                info(f"  수익률: {pnl_percent * 100:+.2f}%")

                # 거래 기록
                state_manager.record_trade('futures', pnl_krw, is_win)

                # 포지션 제거
                state_manager.update_position('futures', symbol, None)

                # 로그
                action = 'TAKE_PROFIT' if is_win else 'STOP_LOSS'
                trade_log(action, symbol, current_price, quantity, reason)

                return {
                    'success': True,
                    'pnl': pnl_krw,
                    'pnl_percent': pnl_percent * 100,
                    'pnl_usdt': pnl_usdt
                }

            error("❌ 청산 실패")
            return {'success': False}

        except Exception as e:
            error(f"❌ 청산 오류: {e}")
            return {'success': False, 'reason': str(e)}

    def check_exit_condition(self, symbol):
        """
        청산 조건 체크

        Returns:
            tuple: (should_exit: bool, reason: str)
        """
        saved_position = state_manager.get_position('futures', symbol)

        if not saved_position:
            return False, None

        current_position = self.get_position(symbol)

        if not current_position:
            return False, None

        entry_price = saved_position['entry_price']
        current_price = self.get_current_price(symbol)
        side = saved_position['side']

        # 수익률 계산
        if side == 'LONG':
            return_percent = (current_price - entry_price) / entry_price
        else:  # SHORT
            return_percent = (entry_price - current_price) / entry_price

        # 손절
        if return_percent <= self.targets['stop_loss']:
            return True, f"손절 {return_percent * 100:.2f}% (실제 {return_percent * self.leverage * 100:.2f}%)"

        # 1차 익절
        if return_percent >= self.targets['take_profit_1']:
            return True, f"1차 익절 {return_percent * 100:.2f}% (실제 {return_percent * self.leverage * 100:.2f}%)"

        # 2차 익절
        if return_percent >= self.targets['take_profit_2']:
            return True, f"2차 익절 {return_percent * 100:.2f}% (실제 {return_percent * self.leverage * 100:.2f}%)"

        return False, None

    def _adjust_quantity(self, symbol, quantity):
        """수량 정밀도 조정"""
        try:
            info_data = self.client.futures_exchange_info()

            for s in info_data['symbols']:
                if s['symbol'] == symbol:
                    for f in s['filters']:
                        if f['filterType'] == 'LOT_SIZE':
                            step_size = float(f['stepSize'])
                            precision = len(str(step_size).split('.')[-1].rstrip('0'))
                            return round(quantity, precision)

            return round(quantity, 3)

        except:
            return round(quantity, 3)


# 전역 인스턴스
futures_trader = FuturesTrader()

# 사용 예시
if __name__ == "__main__":
    print("🧪 Futures Trader 테스트\n")

    # 잔고 조회
    print("💰 USDT 잔고:")
    balance = futures_trader.get_balance()
    print(f"  {balance:.2f} USDT")

    # 비트코인 현재가
    print("\n📊 현재가 조회:")
    btc_price = futures_trader.get_current_price("BTCUSDT")
    print(f"  BTCUSDT: ${btc_price:,.2f}")

    eth_price = futures_trader.get_current_price("ETHUSDT")
    print(f"  ETHUSDT: ${eth_price:,.2f}")

    # 포지션 크기 계산
    if balance > 0:
        position_size = futures_trader.calculate_position_size(balance)
        print(f"\n📈 권장 포지션: {position_size:.2f} USDT")
        print(f"   레버리지 적용: {position_size * FUTURES_LEVERAGE:.2f} USDT")

    # 현재 포지션 확인
    print("\n📦 현재 포지션:")
    positions = state_manager.get_all_positions('futures')
    if positions:
        for symbol, pos in positions.items():
            print(f"  {symbol} [{pos['side']}]: {pos['quantity']:.6f} @ ${pos['entry_price']:,.2f}")
    else:
        print("  없음")

    print("\n" + "=" * 60)
    print("💡 실제 거래는 API 키 설정 후 가능합니다!")
    print("   .env 파일에 BINANCE_API_KEY와 BINANCE_API_SECRET을 입력하세요.")
    print("=" * 60)