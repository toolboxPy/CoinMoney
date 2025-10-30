class Trader:
    def __init__(self, upbit, logger):
        self.upbit = upbit
        self.log = logger

    def buy(self, coin, amount):
        """지정 금액만큼 시장가 매수"""
        try:
            if self.upbit is None:
                self.log.error("Upbit 객체가 없습니다")
                return None

            # 현재 보유 원화 확인
            krw_balance = self.upbit.get_balance("KRW")

            if krw_balance < amount:
                self.log.warning(f"잔고 부족: {krw_balance:,}원 < {amount:,}원")
                return None

            # 시장가 매수 주문
            result = self.upbit.buy_market_order(coin, amount)

            if result:
                self.log.info(f"✅ 매수 완료: {coin}, {amount:,}원")
                self._save_trade_log("BUY", coin, amount, result)
            else:
                self.log.error(f"❌ 매수 실패: {coin}")

            return result

        except Exception as e:
            self.log.error(f"매수 중 오류: {e}")
            return None

    def sell_all(self, coin):
        """보유 코인 전량 시장가 매도"""
        try:
            if self.upbit is None:
                self.log.error("Upbit 객체가 없습니다")
                return None

            # 보유량 확인
            coin_name = coin.split('-')[1]  # "KRW-BTC" -> "BTC"
            balance = self.upbit.get_balance(coin_name)

            if balance is None or balance <= 0:
                self.log.warning(f"{coin} 보유량 없음")
                return None

            # 시장가 매도 주문
            result = self.upbit.sell_market_order(coin, balance)

            if result:
                self.log.info(f"✅ 매도 완료: {coin}, {balance}개")
                self._save_trade_log("SELL", coin, balance, result)
            else:
                self.log.error(f"❌ 매도 실패: {coin}")

            return result

        except Exception as e:
            self.log.error(f"매도 중 오류: {e}")
            return None

    def _save_trade_log(self, trade_type, coin, amount, result):
        """거래 내역을 파일로 저장"""
        import json
        from datetime import datetime

        log_data = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": trade_type,
            "coin": coin,
            "amount": amount,
            "result": str(result)
        }

        try:
            with open("data/trades/trade_history.json", "a", encoding="utf-8") as f:
                f.write(json.dumps(log_data, ensure_ascii=False) + "\n")
        except Exception as e:
            self.log.error(f"거래 로그 저장 실패: {e}")