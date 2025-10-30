"""
현물 트레이더 (업비트)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[핵심 수정]
1. 주문 성공/실패 정확한 판단
2. 체결 대기 로직 개선
3. 디버그 로그 강화
4. 예외 처리 개선
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pyupbit
import time
from datetime import datetime
from config.master_config import (
    UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY,
    PROFIT_TARGETS, POSITION_SIZING
)
from utils.logger import info, warning, error, trade_log
from utils.state_manager import state_manager
from utils.fee_calculator import fee_calculator
from utils.connection_manager import with_retry


class SpotTrader:
    """현물 트레이더 (업비트)"""

    def __init__(self):
        # 업비트 클라이언트
        if UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY:
            self.upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
            self.connected = True
            info("✅ 업비트 현물 트레이더 초기화 완료")
        else:
            self.upbit = None
            self.connected = False
            warning("⚠️ 업비트 API 키 없음 - 조회만 가능")

        self.targets = PROFIT_TARGETS['spot_minute30']
        self.sizing = POSITION_SIZING['spot']

    @with_retry
    def get_balance(self, ticker="KRW"):
        """
        잔고 조회

        Args:
            ticker: "KRW" 또는 "KRW-BTC"

        Returns:
            float: 잔고
        """
        if not self.connected:
            return 0

        balance = self.upbit.get_balance(ticker)
        return float(balance) if balance else 0

    @with_retry
    def get_current_price(self, coin):
        """
        현재가 조회

        Args:
            coin: "KRW-BTC"

        Returns:
            float: 현재가
        """
        price = pyupbit.get_current_price(coin)
        return float(price) if price else 0

    @with_retry
    def get_orderbook(self, coin):
        """
        호가 조회

        Returns:
            dict: 호가 정보
        """
        orderbook = pyupbit.get_orderbook(coin)
        return orderbook[0] if orderbook else None

    def calculate_position_size(self, available_balance):
        """
        포지션 크기 계산

        Args:
            available_balance: 사용 가능한 잔고

        Returns:
            float: 투자 금액
        """
        # 설정된 비율로 계산
        position = available_balance * self.sizing['percent_per_trade']

        # 최소/최대 제한
        position = max(position, self.sizing['min_investment'])
        position = min(position, self.sizing['max_investment'])

        return position

    def buy(self, coin, investment=None, reason="매수"):
        """
        매수 실행 (🔥 완전 수정!)

        Args:
            coin: "KRW-BTC"
            investment: 투자 금액 (None이면 자동 계산)
            reason: 매수 사유

        Returns:
            dict: {
                'success': bool,
                'order_id': str,
                'price': float,
                'quantity': float,
                'investment': float
            }
        """
        if not self.connected:
            error("❌ API 키 없음 - 매수 불가")
            return {'success': False, 'reason': 'No API key'}

        # 이미 보유 중인지 확인
        if state_manager.is_in_position('spot', coin):
            warning(f"⚠️ {coin} 이미 보유 중")
            return {'success': False, 'reason': 'Already in position'}

        try:
            # 잔고 확인
            balance = self.get_balance("KRW")

            if balance < self.sizing['min_investment']:
                error(f"❌ 잔고 부족: {balance:,.0f}원")
                return {'success': False, 'reason': 'Insufficient balance'}

            # 투자 금액 결정
            if investment is None:
                investment = self.calculate_position_size(balance)

            investment = min(investment, balance)

            # 현재가
            current_price = self.get_current_price(coin)

            # 수수료 계산
            actual_amount, fee = fee_calculator.calculate_spot_buy(investment)

            # 수량 계산
            quantity = actual_amount / current_price

            info(f"\n📈 매수 실행:")
            info(f"  코인: {coin}")
            info(f"  투자금: {investment:,.0f}원")
            info(f"  예상가: {current_price:,.0f}원")
            info(f"  예상 수량: {quantity:.8f}")
            info(f"  사유: {reason}")

            # 🔥 실제 매수 주문
            order = self.upbit.buy_market_order(coin, investment)

            # 🔥 주문 응답 체크
            if order is None:
                error("❌ 주문 실패 (order=None)")
                return {'success': False, 'reason': 'Order response is None'}

            # 🔥 에러 체크
            if 'error' in order:
                error(f"❌ 주문 실패: {order['error'].get('message', 'Unknown error')}")
                return {'success': False, 'reason': order['error'].get('message', 'Unknown')}

            # 🔥 UUID 체크 (핵심!)
            if 'uuid' not in order:
                error(f"❌ 주문 응답에 uuid 없음: {order}")
                return {'success': False, 'reason': 'No uuid in order response'}

            order_uuid = order['uuid']
            info(f"✅ 주문 접수 완료!")
            info(f"  주문 ID: {order_uuid}")
            info(f"  주문 상태: {order.get('state', 'N/A')}")

            # 🔥 체결 대기 (최대 5초, 0.5초 간격)
            info("⏳ 체결 확인 중...")
            filled = None
            for attempt in range(10):  # 10번 시도 (5초)
                time.sleep(0.5)

                filled = self._get_order_details(order_uuid)

                if filled:
                    break

                # 디버그: 중간 상태 로그
                if attempt == 2 or attempt == 5:
                    info(f"  체결 대기 중... ({attempt * 0.5:.1f}초)")

            # 🔥 체결 확인
            if filled:
                avg_price = float(filled['price'])
                filled_qty = float(filled['executed_volume'])

                info(f"✅ 체결 완료!")
                info(f"  체결가: {avg_price:,.0f}원")
                info(f"  체결 수량: {filled_qty:.8f}")
                info(f"  실제 투자: {avg_price * filled_qty:,.0f}원")

                # 상태 저장
                position_data = {
                    'entry_price': avg_price,
                    'quantity': filled_qty,
                    'investment': investment,
                    'entry_time': datetime.now().isoformat(),
                    'order_id': order_uuid,
                    'reason': reason
                }

                state_manager.update_position('spot', coin, position_data)

                # 로그
                trade_log('BUY', coin, avg_price, filled_qty, reason)

                info("=" * 60)

                return {
                    'success': True,
                    'order_id': order_uuid,
                    'price': avg_price,
                    'quantity': filled_qty,
                    'investment': investment
                }
            else:
                # 🔥 체결 안 됐지만 주문은 성공
                warning("⚠️ 주문은 접수되었으나 체결 확인 실패")
                warning(f"   주문 ID: {order_uuid}")
                warning("   나중에 수동으로 확인 필요!")

                # 일단 성공으로 처리 (실제 주문은 됨)
                return {
                    'success': True,
                    'order_id': order_uuid,
                    'price': current_price,  # 예상가
                    'quantity': quantity,    # 예상 수량
                    'investment': investment,
                    'pending': True  # 체결 확인 대기 중
                }

        except Exception as e:
            error(f"❌ 매수 오류: {e}")
            import traceback
            error(traceback.format_exc())
            return {'success': False, 'reason': str(e)}

    def sell(self, coin, reason='익절/손절'):
        """
        매도 실행 (🔥 buy와 동일하게 수정)

        Args:
            coin: "KRW-BTC"
            reason: 매도 사유

        Returns:
            dict: {
                'success': bool,
                'pnl': float,
                'return_percent': float
            }
        """
        if not self.connected:
            error("❌ API 키 없음 - 매도 불가")
            return {'success': False}

        # 포지션 확인
        position = state_manager.get_position('spot', coin)

        if not position:
            warning(f"⚠️ {coin} 포지션 없음")
            return {'success': False, 'reason': 'No position'}

        try:
            # 보유 수량
            quantity = position['quantity']
            entry_price = position['entry_price']

            # 현재가
            current_price = self.get_current_price(coin)

            info(f"\n💰 매도 실행:")
            info(f"  코인: {coin}")
            info(f"  수량: {quantity:.8f}")
            info(f"  진입가: {entry_price:,.0f}원")
            info(f"  현재가: {current_price:,.0f}원")
            info(f"  사유: {reason}")

            # 🔥 매도 주문
            order = self.upbit.sell_market_order(coin, quantity)

            # 🔥 주문 응답 체크
            if order is None:
                error("❌ 매도 주문 실패 (order=None)")
                return {'success': False, 'reason': 'Order response is None'}

            if 'error' in order:
                error(f"❌ 매도 주문 실패: {order['error'].get('message', 'Unknown')}")
                return {'success': False, 'reason': order['error'].get('message')}

            if 'uuid' not in order:
                error(f"❌ 주문 응답에 uuid 없음: {order}")
                return {'success': False, 'reason': 'No uuid'}

            order_uuid = order['uuid']
            info(f"✅ 매도 주문 접수!")
            info(f"  주문 ID: {order_uuid}")

            # 🔥 체결 대기
            info("⏳ 체결 확인 중...")
            filled = None
            for attempt in range(10):
                time.sleep(0.5)

                filled = self._get_order_details(order_uuid)

                if filled:
                    break

            # 🔥 체결 확인
            if filled:
                avg_price = float(filled['price'])
                sell_amount = avg_price * quantity

                # 수수료 계산
                received, fee = fee_calculator.calculate_spot_sell(sell_amount)

                # 손익 계산
                cost = entry_price * quantity
                pnl = received - cost
                return_percent = (pnl / cost) * 100

                is_win = pnl > 0

                info(f"✅ 체결 완료!")
                info(f"  체결가: {avg_price:,.0f}원")
                info(f"  수수료: {fee:,.0f}원")
                info(f"  수령액: {received:,.0f}원")
                info(f"  {'💰 수익' if is_win else '📉 손실'}: {pnl:+,.0f}원 ({return_percent:+.2f}%)")

                # 거래 기록
                state_manager.record_trade('spot', pnl, is_win)

                # 포지션 제거
                state_manager.update_position('spot', coin, None)

                # 로그
                action = 'TAKE_PROFIT' if is_win else 'STOP_LOSS'
                trade_log(action, coin, avg_price, quantity, reason)

                info("=" * 60)

                return {
                    'success': True,
                    'pnl': pnl,
                    'return_percent': return_percent,
                    'received': received,
                    'fee': fee
                }
            else:
                warning("⚠️ 매도 주문은 접수되었으나 체결 확인 실패")
                warning(f"   주문 ID: {order_uuid}")

                # 일단 성공으로 처리
                return {
                    'success': True,
                    'order_id': order_uuid,
                    'pending': True
                }

        except Exception as e:
            error(f"❌ 매도 오류: {e}")
            import traceback
            error(traceback.format_exc())
            return {'success': False, 'reason': str(e)}

    def sell_all(self, coin, reason='전량 매도'):
        """
        전량 매도 (별칭)

        Args:
            coin: "KRW-BTC"
            reason: 매도 사유
        """
        return self.sell(coin, reason)

    def check_exit_condition(self, coin):
        """
        청산 조건 체크

        Returns:
            tuple: (should_exit: bool, reason: str)
        """
        position = state_manager.get_position('spot', coin)

        if not position:
            return False, None

        entry_price = position['entry_price']
        current_price = self.get_current_price(coin)

        # 수익률
        return_percent = (current_price - entry_price) / entry_price

        # 손절
        if return_percent <= self.targets['stop_loss']:
            return True, f"손절 {return_percent * 100:.2f}%"

        # 1차 익절
        if return_percent >= self.targets['take_profit_1']:
            return True, f"1차 익절 {return_percent * 100:.2f}%"

        # 2차 익절
        if return_percent >= self.targets['take_profit_2']:
            return True, f"2차 익절 {return_percent * 100:.2f}%"

        # 트레일링 스톱 (최고점 추적)
        if 'highest_price' in position:
            highest = position['highest_price']

            if current_price > highest:
                # 최고점 갱신
                position['highest_price'] = current_price
                state_manager.update_position('spot', coin, position)
            else:
                # 최고점에서 하락
                drop_from_high = (highest - current_price) / highest

                if drop_from_high >= self.targets['trailing_stop']:
                    return True, f"트레일링 스톱 {drop_from_high * 100:.2f}%"
        else:
            # 첫 체크 - 최고점 설정
            position['highest_price'] = current_price
            state_manager.update_position('spot', coin, position)

        return False, None

    @with_retry
    def _get_order_details(self, order_id):
        """
        주문 상세 조회 (🔥 개선!)

        Args:
            order_id: 주문 UUID

        Returns:
            dict or None: 체결된 주문 정보
        """
        try:
            order = self.upbit.get_order(order_id)

            if not order:
                return None

            # 🔥 'done' 상태만 체결 완료로 인정
            if order.get('state') == 'done':
                return order

            # 디버그: 중간 상태 로그
            current_state = order.get('state', 'unknown')
            if current_state != 'done':
                # 상태 변화 추적 (선택사항)
                pass

            return None

        except Exception as e:
            warning(f"⚠️ 주문 조회 실패: {e}")
            return None

    def get_all_balances(self):
        """모든 잔고 조회"""
        if not self.connected:
            return []

        try:
            balances = self.upbit.get_balances()
            return balances if balances else []
        except Exception as e:
            error(f"❌ 잔고 조회 오류: {e}")
            return []


# 전역 인스턴스
spot_trader = SpotTrader()

# 사용 예시
if __name__ == "__main__":
    print("🧪 Spot Trader 테스트\n")

    # 잔고 조회
    print("💰 잔고 조회:")
    krw_balance = spot_trader.get_balance("KRW")
    print(f"  KRW: {krw_balance:,.0f}원")

    # 비트코인 현재가
    print("\n📊 현재가 조회:")
    btc_price = spot_trader.get_current_price("KRW-BTC")
    print(f"  BTC: {btc_price:,.0f}원")

    # 포지션 크기 계산
    if krw_balance > 0:
        position_size = spot_trader.calculate_position_size(krw_balance)
        print(f"\n📈 권장 포지션 크기: {position_size:,.0f}원")

    # 현재 포지션 확인
    print("\n📦 현재 포지션:")
    positions = state_manager.get_all_positions('spot')
    if positions:
        for coin, pos in positions.items():
            print(f"  {coin}: {pos['quantity']:.8f} @ {pos['entry_price']:,.0f}원")
    else:
        print("  없음")

    print("\n" + "=" * 60)
    print("💡 실제 거래는 API 키 설정 후 가능합니다!")
    print("   .env 파일에 UPBIT_ACCESS_KEY와 UPBIT_SECRET_KEY를 입력하세요.")
    print("=" * 60)