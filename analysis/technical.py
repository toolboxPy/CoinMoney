"""
기술적 분석
RSI, MACD, 볼린저밴드, 이동평균선
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pandas as pd
import numpy as np
from config.master_config import TECHNICAL_INDICATORS
from utils.logger import debug


class TechnicalAnalyzer:
    """기술적 분석"""

    def __init__(self):
        self.config = TECHNICAL_INDICATORS

    def calculate_rsi(self, df, period=None):
        """
        RSI (Relative Strength Index) 계산

        Args:
            df: DataFrame with 'close' column
            period: RSI 기간 (기본값: config에서)

        Returns:
            Series: RSI 값
        """
        period = period or self.config['rsi']['period']

        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_macd(self, df, fast=None, slow=None, signal=None):
        """
        MACD (Moving Average Convergence Divergence) 계산

        Returns:
            tuple: (macd, signal, histogram)
        """
        fast = fast or self.config['macd']['fast']
        slow = slow or self.config['macd']['slow']
        signal_period = signal or self.config['macd']['signal']

        exp1 = df['close'].ewm(span=fast, adjust=False).mean()
        exp2 = df['close'].ewm(span=slow, adjust=False).mean()

        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal_period, adjust=False).mean()
        histogram = macd - signal_line

        return macd, signal_line, histogram

    def calculate_bollinger_bands(self, df, period=None, std=None):
        """
        볼린저 밴드 계산

        Returns:
            tuple: (upper, middle, lower)
        """
        period = period or self.config['bollinger']['period']
        std_multiplier = std or self.config['bollinger']['std']

        middle = df['close'].rolling(window=period).mean()
        std_dev = df['close'].rolling(window=period).std()

        upper = middle + (std_dev * std_multiplier)
        lower = middle - (std_dev * std_multiplier)

        return upper, middle, lower

    def calculate_moving_averages(self, df):
        """
        이동평균선 계산

        Returns:
            dict: {'fast': MA7, 'medium': MA25, 'slow': MA99}
        """
        return {
            'fast': df['close'].rolling(window=self.config['ma']['fast']).mean(),
            'medium': df['close'].rolling(window=self.config['ma']['medium']).mean(),
            'slow': df['close'].rolling(window=self.config['ma']['slow']).mean()
        }

    def calculate_volume_surge(self, df):
        """
        거래량 급증 감지

        Returns:
            bool: 급증 여부
        """
        period = self.config['volume']['period']
        multiplier = self.config['volume']['surge_multiplier']

        avg_volume = df['volume'].rolling(window=period).mean()
        current_volume = df['volume'].iloc[-1]
        avg_recent = avg_volume.iloc[-1]

        return current_volume > (avg_recent * multiplier)

    def analyze(self, df):
        """
        종합 기술적 분석

        Args:
            df: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']

        Returns:
            dict: 분석 결과
        """
        if len(df) < 100:
            debug("⚠️ 데이터 부족 (최소 100개 필요)")
            return None

        # 지표 계산
        rsi = self.calculate_rsi(df)
        macd, signal, histogram = self.calculate_macd(df)
        upper_bb, middle_bb, lower_bb = self.calculate_bollinger_bands(df)
        mas = self.calculate_moving_averages(df)
        volume_surge = self.calculate_volume_surge(df)

        # 현재 값
        current_price = df['close'].iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_macd = macd.iloc[-1]
        current_signal = signal.iloc[-1]
        current_histogram = histogram.iloc[-1]

        # 신호 분석
        analysis = {
            'price': current_price,
            'rsi': {
                'value': current_rsi,
                'signal': self._analyze_rsi(current_rsi),
                'oversold': current_rsi < self.config['rsi']['oversold'],
                'overbought': current_rsi > self.config['rsi']['overbought']
            },
            'macd': {
                'value': current_macd,
                'signal_line': current_signal,
                'histogram': current_histogram,
                'signal': self._analyze_macd(current_macd, current_signal, histogram),
                'bullish_cross': self._check_macd_cross(macd, signal, 'bullish'),
                'bearish_cross': self._check_macd_cross(macd, signal, 'bearish')
            },
            'bollinger': {
                'upper': upper_bb.iloc[-1],
                'middle': middle_bb.iloc[-1],
                'lower': lower_bb.iloc[-1],
                'position': self._analyze_bollinger_position(current_price, upper_bb.iloc[-1], lower_bb.iloc[-1]),
                'signal': self._analyze_bollinger(current_price, upper_bb.iloc[-1], lower_bb.iloc[-1])
            },
            'ma': {
                'fast': mas['fast'].iloc[-1],
                'medium': mas['medium'].iloc[-1],
                'slow': mas['slow'].iloc[-1],
                'trend': self._analyze_ma_trend(current_price, mas),
                'golden_cross': self._check_ma_cross(mas, 'golden'),
                'dead_cross': self._check_ma_cross(mas, 'dead')
            },
            'volume': {
                'surge': volume_surge,
                'signal': 'BUY' if volume_surge else 'NEUTRAL'
            }
        }

        # 종합 점수 계산
        analysis['score'] = self._calculate_composite_score(analysis)
        analysis['recommendation'] = self._get_recommendation(analysis['score'])

        return analysis

    def _analyze_rsi(self, rsi):
        """RSI 신호 분석"""
        if rsi < self.config['rsi']['oversold']:
            return 'STRONG_BUY'
        elif rsi < 45:
            return 'BUY'
        elif rsi > self.config['rsi']['overbought']:
            return 'STRONG_SELL'
        elif rsi > 55:
            return 'SELL'
        else:
            return 'NEUTRAL'

    def _analyze_macd(self, macd, signal, histogram):
        """MACD 신호 분석"""
        if macd > signal and histogram.iloc[-1] > histogram.iloc[-2]:
            return 'BUY'
        elif macd < signal and histogram.iloc[-1] < histogram.iloc[-2]:
            return 'SELL'
        else:
            return 'NEUTRAL'

    def _check_macd_cross(self, macd, signal, cross_type):
        """MACD 크로스 체크"""
        if len(macd) < 2:
            return False

        if cross_type == 'bullish':
            # 골든 크로스
            return macd.iloc[-2] <= signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1]
        else:  # bearish
            # 데드 크로스
            return macd.iloc[-2] >= signal.iloc[-2] and macd.iloc[-1] < signal.iloc[-1]

    def _analyze_bollinger_position(self, price, upper, lower):
        """볼린저 밴드 내 위치"""
        band_width = upper - lower
        position = (price - lower) / band_width
        return position

    def _analyze_bollinger(self, price, upper, lower):
        """볼린저 밴드 신호"""
        if price <= lower:
            return 'STRONG_BUY'
        elif price >= upper:
            return 'STRONG_SELL'
        else:
            return 'NEUTRAL'

    def _analyze_ma_trend(self, price, mas):
        """이동평균선 추세 분석"""
        fast = mas['fast'].iloc[-1]
        medium = mas['medium'].iloc[-1]
        slow = mas['slow'].iloc[-1]

        if fast > medium > slow and price > fast:
            return 'STRONG_UPTREND'
        elif fast > medium and price > fast:
            return 'UPTREND'
        elif fast < medium < slow and price < fast:
            return 'STRONG_DOWNTREND'
        elif fast < medium and price < fast:
            return 'DOWNTREND'
        else:
            return 'SIDEWAYS'

    def _check_ma_cross(self, mas, cross_type):
        """이동평균선 크로스"""
        if len(mas['fast']) < 2:
            return False

        fast_prev = mas['fast'].iloc[-2]
        fast_curr = mas['fast'].iloc[-1]
        medium_prev = mas['medium'].iloc[-2]
        medium_curr = mas['medium'].iloc[-1]

        if cross_type == 'golden':
            return fast_prev <= medium_prev and fast_curr > medium_curr
        else:  # dead
            return fast_prev >= medium_prev and fast_curr < medium_curr

    def _calculate_composite_score(self, analysis):
        """종합 점수 계산 (-5 ~ +5)"""
        score = 0

        # RSI
        if analysis['rsi']['signal'] == 'STRONG_BUY':
            score += 2
        elif analysis['rsi']['signal'] == 'BUY':
            score += 1
        elif analysis['rsi']['signal'] == 'STRONG_SELL':
            score -= 2
        elif analysis['rsi']['signal'] == 'SELL':
            score -= 1

        # MACD
        if analysis['macd']['bullish_cross']:
            score += 1.5
        elif analysis['macd']['signal'] == 'BUY':
            score += 0.5
        elif analysis['macd']['bearish_cross']:
            score -= 1.5
        elif analysis['macd']['signal'] == 'SELL':
            score -= 0.5

        # Bollinger
        if analysis['bollinger']['signal'] == 'STRONG_BUY':
            score += 1
        elif analysis['bollinger']['signal'] == 'STRONG_SELL':
            score -= 1

        # MA
        trend = analysis['ma']['trend']
        if trend == 'STRONG_UPTREND':
            score += 1.5
        elif trend == 'UPTREND':
            score += 0.5
        elif trend == 'STRONG_DOWNTREND':
            score -= 1.5
        elif trend == 'DOWNTREND':
            score -= 0.5

        if analysis['ma']['golden_cross']:
            score += 1
        elif analysis['ma']['dead_cross']:
            score -= 1

        # Volume
        if analysis['volume']['surge']:
            score += 0.5

        return round(score, 2)

    def _get_recommendation(self, score):
        """추천 행동"""
        if score >= 3:
            return 'STRONG_BUY'
        elif score >= 1.5:
            return 'BUY'
        elif score <= -3:
            return 'STRONG_SELL'
        elif score <= -1.5:
            return 'SELL'
        else:
            return 'HOLD'


# 전역 인스턴스
technical_analyzer = TechnicalAnalyzer()

# 사용 예시
if __name__ == "__main__":
    print("🧪 Technical Analyzer 테스트\n")

    # 테스트 데이터 생성
    dates = pd.date_range(start='2024-01-01', periods=200, freq='30T')

    # 상승 추세 시뮬레이션
    np.random.seed(42)
    base_price = 95000000
    trend = np.linspace(0, 5000000, 200)
    noise = np.random.normal(0, 500000, 200)
    prices = base_price + trend + noise

    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices * 0.999,
        'high': prices * 1.002,
        'low': prices * 0.998,
        'close': prices,
        'volume': np.random.uniform(100, 1000, 200)
    })

    print("📊 테스트 데이터:")
    print(f"  기간: {len(df)}개 캔들")
    print(f"  시작가: {df['close'].iloc[0]:,.0f}원")
    print(f"  종료가: {df['close'].iloc[-1]:,.0f}원")
    print(f"  변화율: {(df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100:+.2f}%\n")

    # 분석 실행
    result = technical_analyzer.analyze(df)

    if result:
        print("=" * 60)
        print("📈 기술적 분석 결과")
        print("=" * 60)

        print(f"\n💰 가격: {result['price']:,.0f}원")

        print(f"\n📊 RSI: {result['rsi']['value']:.2f}")
        print(f"  신호: {result['rsi']['signal']}")
        print(f"  과매도: {result['rsi']['oversold']}")
        print(f"  과매수: {result['rsi']['overbought']}")

        print(f"\n📈 MACD:")
        print(f"  MACD: {result['macd']['value']:.2f}")
        print(f"  Signal: {result['macd']['signal_line']:.2f}")
        print(f"  신호: {result['macd']['signal']}")
        print(f"  골든크로스: {result['macd']['bullish_cross']}")

        print(f"\n🎯 볼린저 밴드:")
        print(f"  상단: {result['bollinger']['upper']:,.0f}원")
        print(f"  중간: {result['bollinger']['middle']:,.0f}원")
        print(f"  하단: {result['bollinger']['lower']:,.0f}원")
        print(f"  위치: {result['bollinger']['position'] * 100:.1f}%")
        print(f"  신호: {result['bollinger']['signal']}")

        print(f"\n📏 이동평균선:")
        print(f"  MA7: {result['ma']['fast']:,.0f}원")
        print(f"  MA25: {result['ma']['medium']:,.0f}원")
        print(f"  MA99: {result['ma']['slow']:,.0f}원")
        print(f"  추세: {result['ma']['trend']}")
        print(f"  골든크로스: {result['ma']['golden_cross']}")

        print(f"\n📊 거래량:")
        print(f"  급증: {result['volume']['surge']}")
        print(f"  신호: {result['volume']['signal']}")

        print("\n" + "=" * 60)
        print(f"🎯 종합 점수: {result['score']:+.2f}")
        print(f"💡 추천: {result['recommendation']}")
        print("=" * 60)

    print("\n✅ 테스트 완료!")