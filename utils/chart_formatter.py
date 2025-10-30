"""
차트 포맷터
캔들스틱 데이터를 AI가 이해하기 쉬운 텍스트로 변환
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pandas as pd
import numpy as np


class ChartFormatter:
    """차트 데이터를 텍스트로 포맷팅"""

    def describe_candle_pattern(self, df, candle_count=20):
        """
        캔들 패턴을 상세하게 텍스트로 설명

        Args:
            df: OHLCV DataFrame
            candle_count: 분석할 최근 캔들 개수

        Returns:
            str: AI가 이해하기 쉬운 텍스트 설명
        """
        recent = df.tail(candle_count)

        # 기본 정보
        current_price = df['close'].iloc[-1]
        recent_high = recent['high'].max()
        recent_low = recent['low'].min()
        volatility = (recent_high - recent_low) / recent_low * 100

        # 캔들 구성
        bullish_count = sum(recent['close'] > recent['open'])
        bearish_count = candle_count - bullish_count

        # 추세 분석
        ma7 = df['close'].rolling(7).mean().iloc[-1]
        ma25 = df['close'].rolling(25).mean().iloc[-1]
        ma99 = df['close'].rolling(99).mean().iloc[-1]

        # 연속 패턴
        consecutive_bullish = self._count_consecutive_bullish(recent)
        consecutive_bearish = self._count_consecutive_bearish(recent)

        # 특수 캔들 감지
        has_doji = self._detect_doji(recent)
        has_hammer = self._detect_hammer(recent)
        has_shooting_star = self._detect_shooting_star(recent)

        # 지지/저항
        support_level = self._find_support(df)
        resistance_level = self._find_resistance(df)

        # 설명 생성
        description = f"""
📊 캔들스틱 분석 (최근 {candle_count}개 캔들):

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 현재 상태
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 현재가: {current_price:,.0f}원
- 최근 고점: {recent_high:,.0f}원 ({((recent_high - current_price) / current_price * 100):+.2f}%)
- 최근 저점: {recent_low:,.0f}원 ({((recent_low - current_price) / current_price * 100):+.2f}%)
- 변동폭: {volatility:.2f}%
- 현재가 위치: {self._price_position(current_price, recent_high, recent_low)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 캔들 구성
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 양봉: {bullish_count}개 ({bullish_count / candle_count * 100:.0f}%)
- 음봉: {bearish_count}개 ({bearish_count / candle_count * 100:.0f}%)
- 추세: {self._determine_trend(bullish_count, bearish_count)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 이동평균선
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- MA7:  {ma7:,.0f}원 ({((current_price - ma7) / ma7 * 100):+.2f}%)
- MA25: {ma25:,.0f}원 ({((current_price - ma25) / ma25 * 100):+.2f}%)
- MA99: {ma99:,.0f}원 ({((current_price - ma99) / ma99 * 100):+.2f}%)
- 배열: {self._ma_arrangement(current_price, ma7, ma25, ma99)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔁 연속 패턴
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 연속 양봉: {consecutive_bullish}개
- 연속 음봉: {consecutive_bearish}개
- 모멘텀: {self._momentum_status(consecutive_bullish, consecutive_bearish)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⭐ 특수 캔들 패턴
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 도지 캔들: {'발견 (반전 신호)' if has_doji else '없음'}
- 해머: {'발견 (반등 신호)' if has_hammer else '없음'}
- 슈팅스타: {'발견 (하락 신호)' if has_shooting_star else '없음'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 지지/저항
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 지지선: {support_level:,.0f}원 ({((support_level - current_price) / current_price * 100):+.2f}%)
- 저항선: {resistance_level:,.0f}원 ({((resistance_level - current_price) / current_price * 100):+.2f}%)
- 거리: 지지선 {abs((current_price - support_level) / current_price * 100):.2f}%, 저항선 {abs((resistance_level - current_price) / current_price * 100):.2f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 최근 5개 캔들 상세
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{self._format_recent_candles(df, 5)}
"""

        return description

    def _count_consecutive_bullish(self, df):
        """연속 양봉 개수"""
        count = 0
        for i in range(len(df) - 1, -1, -1):
            if df['close'].iloc[i] > df['open'].iloc[i]:
                count += 1
            else:
                break
        return count

    def _count_consecutive_bearish(self, df):
        """연속 음봉 개수"""
        count = 0
        for i in range(len(df) - 1, -1, -1):
            if df['close'].iloc[i] < df['open'].iloc[i]:
                count += 1
            else:
                break
        return count

    def _detect_doji(self, df):
        """도지 캔들 감지 (시가 ≈ 종가)"""
        last = df.iloc[-1]
        body = abs(last['close'] - last['open'])
        total = last['high'] - last['low']

        if total == 0:
            return False

        # 몸통이 전체의 5% 이하면 도지
        return (body / total) < 0.05

    def _detect_hammer(self, df):
        """해머 패턴 감지 (긴 아래 꼬리)"""
        last = df.iloc[-1]
        body = abs(last['close'] - last['open'])
        lower_shadow = min(last['open'], last['close']) - last['low']
        upper_shadow = last['high'] - max(last['open'], last['close'])

        # 아래 꼬리가 몸통의 2배 이상이고, 위 꼬리가 작으면 해머
        return lower_shadow > body * 2 and upper_shadow < body * 0.5

    def _detect_shooting_star(self, df):
        """슈팅스타 패턴 감지 (긴 위 꼬리)"""
        last = df.iloc[-1]
        body = abs(last['close'] - last['open'])
        lower_shadow = min(last['open'], last['close']) - last['low']
        upper_shadow = last['high'] - max(last['open'], last['close'])

        # 위 꼬리가 몸통의 2배 이상이고, 아래 꼬리가 작으면 슈팅스타
        return upper_shadow > body * 2 and lower_shadow < body * 0.5

    def _find_support(self, df):
        """지지선 찾기 (최근 저점들의 평균)"""
        recent = df.tail(50)
        lows = recent['low'].nsmallest(5)
        return lows.mean()

    def _find_resistance(self, df):
        """저항선 찾기 (최근 고점들의 평균)"""
        recent = df.tail(50)
        highs = recent['high'].nlargest(5)
        return highs.mean()

    def _price_position(self, price, high, low):
        """현재가 위치"""
        position = (price - low) / (high - low) * 100

        if position > 80:
            return f"상단 ({position:.0f}%)"
        elif position > 60:
            return f"중상단 ({position:.0f}%)"
        elif position > 40:
            return f"중앙 ({position:.0f}%)"
        elif position > 20:
            return f"중하단 ({position:.0f}%)"
        else:
            return f"하단 ({position:.0f}%)"

    def _determine_trend(self, bullish, bearish):
        """추세 판단"""
        ratio = bullish / (bullish + bearish)

        if ratio > 0.7:
            return "강한 상승"
        elif ratio > 0.55:
            return "약한 상승"
        elif ratio > 0.45:
            return "횡보"
        elif ratio > 0.3:
            return "약한 하락"
        else:
            return "강한 하락"

    def _ma_arrangement(self, price, ma7, ma25, ma99):
        """이동평균선 배열"""
        if price > ma7 > ma25 > ma99:
            return "완벽한 정배열 (강한 상승)"
        elif price > ma7 > ma25:
            return "정배열 (상승)"
        elif ma99 > ma25 > ma7 > price:
            return "완벽한 역배열 (강한 하락)"
        elif ma25 > ma7 > price:
            return "역배열 (하락)"
        else:
            return "혼조세"

    def _momentum_status(self, bullish, bearish):
        """모멘텀 상태"""
        if bullish >= 3:
            return f"상승 모멘텀 강함 ({bullish}연속)"
        elif bearish >= 3:
            return f"하락 모멘텀 강함 ({bearish}연속)"
        elif bullish == 2:
            return "상승 모멘텀 형성 중"
        elif bearish == 2:
            return "하락 모멘텀 형성 중"
        else:
            return "방향성 없음"

    def _format_recent_candles(self, df, count):
        """최근 캔들 상세 포맷팅"""
        recent = df.tail(count)

        lines = []
        for i, (idx, row) in enumerate(recent.iterrows(), 1):
            change = ((row['close'] - row['open']) / row['open']) * 100
            candle_type = '🟢 양봉' if row['close'] > row['open'] else '🔴 음봉'

            body_size = abs(row['close'] - row['open'])
            total_size = row['high'] - row['low']
            body_ratio = (body_size / total_size * 100) if total_size > 0 else 0

            line = f"""
{i}. {candle_type} | 변화: {change:+.2f}%
   시가: {row['open']:,.0f} → 종가: {row['close']:,.0f}
   고가: {row['high']:,.0f} / 저가: {row['low']:,.0f}
   몸통비율: {body_ratio:.0f}% | 거래량: {row['volume']:,.0f}
"""
            lines.append(line)

        return '\n'.join(lines)


# 전역 인스턴스
chart_formatter = ChartFormatter()

# 사용 예시
if __name__ == "__main__":
    import pyupbit

    print("🧪 Chart Formatter 테스트\n")

    # 비트코인 데이터
    df = pyupbit.get_ohlcv("KRW-BTC", interval="minute30", count=200)

    if df is not None:
        # 패턴 설명 생성
        description = chart_formatter.describe_candle_pattern(df, 20)

        print(description)
    else:
        print("❌ 데이터 조회 실패")