import pyupbit


class Strategy:
    def __init__(self):
        self.last_decision = "HOLD"

    def check_signal(self, coin, current_price):
        """
        매수/매도 신호 판단
        - BUY: 매수해야 할 때
        - SELL: 매도해야 할 때
        - HOLD: 그대로 유지
        """
        try:
            # 예시: 간단한 이동평균 전략
            # 5분봉 데이터 가져오기
            df = pyupbit.get_ohlcv(coin, interval="minute5", count=20)

            if df is None or len(df) < 20:
                return "HOLD"

            # 단순 이동평균 계산
            ma5 = df['close'].rolling(window=5).mean().iloc[-1]
            ma20 = df['close'].rolling(window=20).mean().iloc[-1]

            # 골든크로스: 단기 평균이 장기 평균을 상향 돌파
            if ma5 > ma20 and self.last_decision != "BUY":
                self.last_decision = "BUY"
                return "BUY"

            # 데드크로스: 단기 평균이 장기 평균을 하향 돌파
            elif ma5 < ma20 and self.last_decision != "SELL":
                self.last_decision = "SELL"
                return "SELL"

            return "HOLD"

        except Exception as e:
            print(f"전략 계산 오류: {e}")
            return "HOLD"