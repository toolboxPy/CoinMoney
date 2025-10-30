"""
수수료 계산기
거래소별 수수료 정확히 계산
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.master_config import FEES


class FeeCalculator:
    """수수료 계산기"""

    def __init__(self):
        self.fees = FEES

    def calculate_spot_buy(self, investment):
        """
        현물 매수 수수료 계산 (업비트)

        Args:
            investment: 투자 금액 (원)

        Returns:
            tuple: (실제_매수금액, 수수료)
        """
        # 업비트는 매수 시 수수료 없음!
        # 전액 코인 구매 가능
        actual_amount = investment
        fee = 0

        return actual_amount, fee

    def calculate_spot_sell(self, sell_amount):
        """
        현물 매도 수수료 계산 (업비트)

        Args:
            sell_amount: 매도 금액 (원)

        Returns:
            tuple: (실제_받는금액, 수수료)
        """
        # 업비트 매도 수수료: 0.05%
        fee_rate = self.fees['spot']['taker']
        fee = sell_amount * fee_rate
        actual_received = sell_amount - fee

        return actual_received, fee

    def calculate_futures_entry(self, position_size, leverage=5):
        """
        선물 진입 수수료 계산 (바이낸스)

        Args:
            position_size: 포지션 크기 (USDT 기준)
            leverage: 레버리지

        Returns:
            tuple: (실제_포지션크기, 수수료)
        """
        # 바이낸스 선물 Taker: 0.05%
        fee_rate = self.fees['futures']['taker']

        # 레버리지 적용된 포지션 크기
        total_position = position_size * leverage

        # 수수료 (레버리지 적용된 금액 기준)
        fee = total_position * fee_rate

        return total_position, fee

    def calculate_futures_exit(self, position_size, leverage=5):
        """
        선물 청산 수수료 계산

        Args:
            position_size: 포지션 크기 (USDT 기준)
            leverage: 레버리지

        Returns:
            tuple: (실제_받는금액, 수수료)
        """
        # 청산 수수료도 동일
        fee_rate = self.fees['futures']['taker']
        total_position = position_size * leverage
        fee = total_position * fee_rate

        return total_position - fee, fee

    def calculate_round_trip_cost(self, exchange, investment, leverage=1):
        """
        왕복 거래 비용 계산 (진입 + 청산)

        Args:
            exchange: 'spot' or 'futures'
            investment: 투자 금액
            leverage: 레버리지 (선물만)

        Returns:
            dict: {
                'entry_fee': 진입 수수료,
                'exit_fee': 청산 수수료,
                'total_fee': 총 수수료,
                'break_even_percent': 손익분기점 (%)
            }
        """
        if exchange == 'spot':
            # 현물: 매수 수수료 없음, 매도만
            entry_fee = 0
            exit_fee = investment * self.fees['spot']['taker']
            total_fee = entry_fee + exit_fee

        else:  # futures
            # 선물: 진입 + 청산 모두 수수료
            position = investment * leverage
            entry_fee = position * self.fees['futures']['taker']
            exit_fee = position * self.fees['futures']['taker']
            total_fee = entry_fee + exit_fee

        # 손익분기점 계산
        break_even_percent = (total_fee / investment) * 100

        return {
            'entry_fee': entry_fee,
            'exit_fee': exit_fee,
            'total_fee': total_fee,
            'break_even_percent': break_even_percent
        }

    def calculate_net_profit(self, exchange, investment, sell_price, buy_price, leverage=1):
        """
        실제 순수익 계산 (수수료 제외)

        Args:
            exchange: 'spot' or 'futures'
            investment: 투자 금액
            sell_price: 매도가
            buy_price: 매수가
            leverage: 레버리지

        Returns:
            dict: {
                'gross_profit': 총 수익 (수수료 제외 전),
                'total_fee': 총 수수료,
                'net_profit': 순수익 (수수료 제외 후),
                'return_percent': 수익률 (%)
            }
        """
        # 총 수익 (수수료 제외 전)
        price_change_percent = (sell_price - buy_price) / buy_price

        if exchange == 'futures':
            price_change_percent *= leverage

        gross_profit = investment * price_change_percent

        # 수수료 계산
        fees = self.calculate_round_trip_cost(exchange, investment, leverage)
        total_fee = fees['total_fee']

        # 순수익
        net_profit = gross_profit - total_fee
        return_percent = (net_profit / investment) * 100

        return {
            'gross_profit': gross_profit,
            'total_fee': total_fee,
            'net_profit': net_profit,
            'return_percent': return_percent
        }

    def get_minimum_profit_target(self, exchange, investment, leverage=1):
        """
        최소 익절 목표 계산 (수수료 커버)

        Returns:
            float: 최소 익절 목표 (%)
        """
        fees = self.calculate_round_trip_cost(exchange, investment, leverage)
        return fees['break_even_percent']


# 전역 인스턴스
fee_calculator = FeeCalculator()

# 사용 예시
if __name__ == "__main__":
    print("🧪 Fee Calculator 테스트\n")

    # 테스트 1: 현물 거래
    print("=" * 60)
    print("📊 현물 거래 (업비트)")
    print("=" * 60)

    investment = 100000  # 10만원

    # 매수
    buy_amount, buy_fee = fee_calculator.calculate_spot_buy(investment)
    print(f"\n매수:")
    print(f"  투자금: {investment:,}원")
    print(f"  수수료: {buy_fee:,.0f}원")
    print(f"  실제 매수: {buy_amount:,}원")

    # 매도 (10% 상승 가정)
    sell_amount = investment * 1.10
    received, sell_fee = fee_calculator.calculate_spot_sell(sell_amount)
    print(f"\n매도:")
    print(f"  매도금액: {sell_amount:,}원")
    print(f"  수수료: {sell_fee:,.0f}원")
    print(f"  실제 수령: {received:,}원")

    # 순수익
    profit = fee_calculator.calculate_net_profit('spot', investment, 1.10, 1.0)
    print(f"\n순수익:")
    print(f"  총 수익: {profit['gross_profit']:+,.0f}원")
    print(f"  총 수수료: {profit['total_fee']:,.0f}원")
    print(f"  순수익: {profit['net_profit']:+,.0f}원")
    print(f"  수익률: {profit['return_percent']:+.2f}%")

    # 손익분기점
    breakeven = fee_calculator.get_minimum_profit_target('spot', investment)
    print(f"\n손익분기점: {breakeven:.3f}% 이상")

    # 테스트 2: 선물 거래
    print("\n" + "=" * 60)
    print("📈 선물 거래 (바이낸스, 5배 레버리지)")
    print("=" * 60)

    leverage = 5

    # 진입
    position, entry_fee = fee_calculator.calculate_futures_entry(investment, leverage)
    print(f"\n진입:")
    print(f"  투자금: {investment:,}원")
    print(f"  레버리지: {leverage}배")
    print(f"  포지션: {position:,}원")
    print(f"  수수료: {entry_fee:,.0f}원")

    # 청산 (2% 상승 = 실제 10% 수익)
    profit = fee_calculator.calculate_net_profit('futures', investment, 1.02, 1.0, leverage)
    print(f"\n청산 (가격 +2%):")
    print(f"  총 수익: {profit['gross_profit']:+,.0f}원 (레버 적용)")
    print(f"  총 수수료: {profit['total_fee']:,.0f}원")
    print(f"  순수익: {profit['net_profit']:+,.0f}원")
    print(f"  수익률: {profit['return_percent']:+.2f}%")

    # 손익분기점
    breakeven = fee_calculator.get_minimum_profit_target('futures', investment, leverage)
    print(f"\n손익분기점: {breakeven:.3f}% 이상")

    print("\n" + "=" * 60)
    print("✅ 테스트 완료!")