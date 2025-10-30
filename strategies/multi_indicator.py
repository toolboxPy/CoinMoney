"""
Multi-Indicator 전략
RSI + MACD + 볼린저밴드 + 이동평균선 종합 판단
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pyupbit
import pandas as pd
from datetime import datetime
from config.master_config import TECHNICAL_INDICATORS
from utils.logger import info, warning, debug
from utils.state_manager import state_manager
from analysis.technical import technical_analyzer
from core.position_manager import position_manager
from master.global_risk import global_risk


class MultiIndicatorStrategy:
    """복합 지표 전략"""

    def __init__(self, timeframe='30m'):
        self.timeframe = timeframe
        self.name = f"Multi-Indicator-{timeframe}"
        self.min_score = 2.0  # 최소 매수 점수

        info(f"📊 {self.name} 전략 초기화")
        info(f"  최소 매수 점수: {self.min_score}")

    def analyze(self, coin):
        """
        시장 분석 및 신호 생성

        Args:
            coin: "KRW-BTC"

        Returns:
            dict: {
                'signal': 'BUY' / 'SELL' / 'HOLD',
                'score': float,
                'confidence': float,
                'reasons': []
            }
        """
        try:
            # 데이터 가져오기
            if self.timeframe == '30m':
                interval = 'minute30'
                count = 200
            elif self.timeframe == '1h':
                interval = 'minute60'
                count = 200
            else:
                interval = 'day'
                count = 200

            df = pyupbit.get_ohlcv(coin, interval=interval, count=count)

            if df is None or len(df) < 100:
                warning(f"⚠️ {coin} 데이터 부족")
                return None

            # 기술적 분석 실행
            analysis = technical_analyzer.analyze(df)

            if not analysis:
                warning(f"⚠️ {coin} 분석 실패")
                return None

            # 신호 생성
            signal = self._generate_signal(analysis)

            debug(f"\n{coin} 분석 결과:")
            debug(f"  신호: {signal['signal']}")
            debug(f"  점수: {signal['score']}")
            debug(f"  신뢰도: {signal['confidence']}")

            return signal

        except Exception as e:
            warning(f"❌ {coin} 분석 오류: {e}")
            return None

    def _generate_signal(self, analysis):
        """
        분석 결과를 신호로 변환

        Returns:
            dict: 신호 정보
        """
        score = analysis['score']
        reasons = []

        # RSI 신호
        rsi = analysis['rsi']
        if rsi['oversold']:
            reasons.append(f"RSI 과매도 ({rsi['value']:.1f})")
        elif rsi['overbought']:
            reasons.append(f"RSI 과매수 ({rsi['value']:.1f})")

        # MACD 신호
        macd = analysis['macd']
        if macd['bullish_cross']:
            reasons.append("MACD 골든크로스")
        elif macd['bearish_cross']:
            reasons.append("MACD 데드크로스")

        # 볼린저 밴드
        bb = analysis['bollinger']
        if bb['signal'] == 'STRONG_BUY':
            reasons.append(f"볼린저 하단 터치 ({bb['position'] * 100:.0f}%)")
        elif bb['signal'] == 'STRONG_SELL':
            reasons.append(f"볼린저 상단 터치 ({bb['position'] * 100:.0f}%)")

        # 이동평균선
        ma = analysis['ma']
        if ma['golden_cross']:
            reasons.append("MA 골든크로스")
        elif ma['dead_cross']:
            reasons.append("MA 데드크로스")

        # 거래량
        if analysis['volume']['surge']:
            reasons.append("거래량 급증")

        # 신호 결정
        if score >= self.min_score:
            signal = 'BUY'
            confidence = min(score / 5.0, 1.0)
        elif score <= -self.min_score:
            signal = 'SELL'
            confidence = min(abs(score) / 5.0, 1.0)
        else:
            signal = 'HOLD'
            confidence = 0.5

        return {
            'signal': signal,
            'score': score,
            'confidence': confidence,
            'reasons': reasons,
            'recommendation': analysis['recommendation']
        }

    def execute(self, coin):
        """
        전략 실행

        Args:
            coin: "KRW-BTC"

        Returns:
            dict: 실행 결과
        """
        info(f"\n{'=' * 60}")
        info(f"🎯 {self.name} 전략 실행: {coin}")
        info(f"{'=' * 60}")

        # 1. 리스크 체크
        can_trade, risk_reason = global_risk.can_open_position('spot')

        if not can_trade:
            warning(f"⛔ 거래 불가: {risk_reason}")
            return {'action': 'SKIP', 'reason': risk_reason}

        # 2. 현재 포지션 확인
        has_position = state_manager.is_in_position('spot', coin)

        if has_position:
            # 보유 중 - 청산 체크
            return self._check_exit(coin)
        else:
            # 미보유 - 진입 체크
            return self._check_entry(coin)

    def _check_entry(self, coin):
        """진입 조건 체크"""
        # 시장 분석
        signal = self.analyze(coin)

        if not signal:
            return {'action': 'HOLD', 'reason': '분석 실패'}

        # 매수 신호 확인
        if signal['signal'] != 'BUY':
            info(f"⏸️ 대기: 신호 {signal['signal']} (점수: {signal['score']:+.2f})")
            return {'action': 'HOLD', 'reason': f"신호 {signal['signal']}"}

        if signal['score'] < self.min_score:
            info(f"⏸️ 대기: 점수 부족 ({signal['score']:+.2f} < {self.min_score})")
            return {'action': 'HOLD', 'reason': f"점수 부족"}

        # 매수 실행
        info(f"\n🎯 매수 신호 발생!")
        info(f"  점수: {signal['score']:+.2f}")
        info(f"  신뢰도: {signal['confidence'] * 100:.0f}%")
        info(f"  사유: {', '.join(signal['reasons'])}")

        # 투자 금액 계산
        from traders.spot_trader import spot_trader
        balance = spot_trader.get_balance("KRW")
        investment = spot_trader.calculate_position_size(balance)

        if investment < 5000:
            warning(f"⚠️ 잔고 부족: {balance:,.0f}원")
            return {'action': 'SKIP', 'reason': '잔고 부족'}

        # 포지션 열기
        result = position_manager.open_spot_position(
            coin,
            investment,
            f"Multi-Indicator 매수 (점수: {signal['score']:+.2f})"
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
        # 청산 신호 확인
        should_exit, reason = position_manager.check_spot_exit(coin)

        if should_exit:
            info(f"\n💰 청산 신호: {reason}")

            # 포지션 닫기
            result = position_manager.close_spot_position(coin, reason)

            if result['success']:
                return {
                    'action': 'SELL',
                    'pnl': result['pnl'],
                    'return_percent': result['return_percent'],
                    'reason': reason
                }
            else:
                return {'action': 'FAILED', 'reason': result.get('reason')}

        # 청산 신호 없음 - 현재 상태 출력
        status = position_manager.get_position_status('spot', coin)

        if status:
            info(f"\n📊 포지션 유지 중:")
            info(f"  진입가: {status['entry_price']:,.0f}원")
            info(f"  현재가: {status['current_price']:,.0f}원")
            info(f"  수익률: {status['return_percent']:+.2f}%")

            if status['trailing_active']:
                info(f"  🎯 Trailing Stop 활성화!")
                info(f"     최고점: {status['highest_price']:,.0f}원")

        return {'action': 'HOLD', 'reason': '청산 조건 미달'}


# 전역 인스턴스
multi_indicator_30m = MultiIndicatorStrategy('30m')
multi_indicator_1h = MultiIndicatorStrategy('1h')

# 사용 예시
if __name__ == "__main__":
    print("🧪 Multi-Indicator 전략 테스트\n")

    # 테스트 코인
    test_coin = "KRW-BTC"

    print(f"📊 {test_coin} 분석 중...\n")

    # 분석 실행
    signal = multi_indicator_30m.analyze(test_coin)

    if signal:
        print("=" * 60)
        print("📈 분석 결과")
        print("=" * 60)
        print(f"\n신호: {signal['signal']}")
        print(f"점수: {signal['score']:+.2f}")
        print(f"신뢰도: {signal['confidence'] * 100:.0f}%")
        print(f"추천: {signal['recommendation']}")

        if signal['reasons']:
            print(f"\n📋 근거:")
            for reason in signal['reasons']:
                print(f"  • {reason}")

        print("\n" + "=" * 60)

        # 전략 실행 (실제로는 실행 안 함 - 테스트)
        print("\n💡 실제 거래를 원하면 execute() 메서드를 호출하세요.")
        print("   예: multi_indicator_30m.execute('KRW-BTC')")

    else:
        print("❌ 분석 실패")

    print("\n✅ 테스트 완료!")