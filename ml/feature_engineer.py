import numpy as np
import pandas as pd
from pyexpat import features
from ta.trend import MACD, EMAIndicator, SMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
from typing import Dict
from datetime import datetime

class FeatureEngineer:

    def extract_features(
            self,                                   #자기 자신 내에서의 변수나 이런걸 호출할때 구분하기위해서
            df: pd.DataFrame,                       #dataframe을 가져옴
            tech_analysis: Optional[Dict] = None    #
    ) -> np.ndarray:

        #dataframe이 비어있으면 에러 발생 시켜
        if df.empty:
            raise ValueError("DataFrame is empty")

        #계산을 위해 필요한 시가, 고가, 저가, 종가, 거래량 목록이 없다면 에러 발생 시켜
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"Missing required columns: {required_columns}")

        if tech_analysis is None:
            from analysis.technical import get_technical_analyzer
            analyzer = get_technical_analyzer()
            tech_analysis = analyzer.analyze(df)

            #데이터가 안넘어 왔으면 기술분석 실패 내고 오류 발생 시켜
            if not tech_analysis.get('success', False):
                raise ValueError("Technical analysis failed")

        features = []

        # ---------------------------------------------
        # 1. 기술적 지표(11개)
        # ---------------------------------------------

        # 1. RSI
        features.append(tech_analysis['rsi']['value'])

        # 2. MACD Histogram
        features.append(tech_analysis['macd']['histogram'])

        # 3-4. Sttochastic
        features.append(tech_analysis['stoch']['k'])
        features.append(tech_analysis['stoch']['d'])

        # 5-6. 볼린저 밴드
        bb = tech_analysis['bollinger']
        bb_range = bb['upper'] - bb['lower']
        bb_position = (bb['current'] - bb['lower'] / bb_range if bb_range > 0 else 0.5)
        features.append(bb_position)
        features.append(bb['bandwidth'])

        # 7-10. 이동평균선 (0 나누기 방어!)
        ma = tech_analysis['ma']

        #Price vs MA7
        features.append(
            (ma['current'] - ma['ma7']) / ma['ma7'] * 100
            if ma['ma25'] > 0 else 0.0
        )

        # MA25 vs MA99
        features.append(
            (ma['ma25'] - ma['ma99']) / ma['ma99'] * 100
            if ma['ma99'] > 0 else 0.0
        )

        # Ma Alignment
        features.append(1.0 if ma['alignment'] == 'GOLDEN' else 0.0)

        # 11. ADX
        adx = self._calcultaed_adx(df)
        features.append(adx)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1. 기술적 지표 (11개)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # 1. RSI
        features.append(tech_analysis['rsi']['value'])

        # 2. MACD Histogram
        features.append(tech_analysis['macd']['histogram'])

        # 3-4. Stochastic
        features.append(tech_analysis['stoch']['k'])
        features.append(tech_analysis['stoch']['d'])

        # 5-6. 볼린저 밴드
        bb = tech_analysis['bollinger']
        bb_range = bb['upper'] - bb['lower']
        bb_position = (bb['current'] - bb['lower']) / bb_range if bb_range > 0 else 0.5
        features.append(bb_position)
        features.append(bb['bandwidth'])

        # 7-10. 이동평균선 (🔧 0 나누기 방어!)
        ma = tech_analysis['ma']

        # Price vs MA7
        features.append(
            (ma['current'] - ma['ma7']) / ma['ma7'] * 100
            if ma['ma7'] > 0 else 0.0
        )

        # MA7 vs MA25
        features.append(
            (ma['ma7'] - ma['ma25']) / ma['ma25'] * 100
            if ma['ma25'] > 0 else 0.0
        )

        # MA25 vs MA99
        features.append(
            (ma['ma25'] - ma['ma99']) / ma['ma99'] * 100
            if ma['ma99'] > 0 else 0.0
        )

        # MA Alignment
        features.append(1.0 if ma['alignment'] == 'GOLDEN' else 0.0)

        # 11. ADX
        adx = self._calculate_adx(df)
        features.append(adx)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2. 변동성 (8개)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # 12. ATR %
        atr = tech_analysis['atr']
        features.append(atr['volatility_pct'])

        # 13-15. 다중 기간 변동성
        returns = df['close'].pct_change()

        features.append(
            returns.iloc[-5:].std() * 100
            if len(returns) >= 5 else 0.0
        )
        features.append(
            returns.iloc[-10:].std() * 100
            if len(returns) >= 10 else 0.0
        )
        features.append(
            returns.iloc[-20:].std() * 100
            if len(returns) >= 20 else 0.0
        )

        # 16-17. 고점/저점 변화 (0 나누기 방어!)
        if len(df) >= 5:
            high_5_ago = df['high'].iloc[-5]
            low_5_ago = df['low'].iloc[-5]

            high_change = (
                (df['high'].iloc[-1] - high_5_ago) / high_5_ago * 100
                if high_5_ago > 0 else 0.0
            )
            low_change = (
                (df['low'].iloc[-1] - low_5_ago) / low_5_ago * 100
                if low_5_ago > 0 else 0.0
            )
        else:
            high_change = 0.0
            low_change = 0.0

        features.append(high_change)
        features.append(low_change)

        # 18. 가격 레인지 ( 0 나누기 방어)
        if len(df) >= 20:
            range_max = df['high'].iloc[-20:].max()
            range_min = df['low'].iloc[-20:].min()
            current = df['close'].iloc[-1]

            price_range = (
                (range_max - range_min) / current * 100
                if current > 0 else 0.0
            )
        else:
            price_range = 0.0
        features.append(price_range)

        # 19. 평균 일중 변동
        if len(df) >= 20:
            safe_close = df['close'].replace(0, np.nan)
            intraday_ranges = (df['high'] - df['low']) / safe_close
            intraday_range = intraday_ranges.iloc[-20:].mean() * 100

            if pd.isna(intraday_range):
                intraday_range = 0.0
        else:
            intraday_range = 0.0
        features.append(intraday_range)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3. 추세 (5개)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        trend = tech_analysis['trend']
        
        # 20. EMA20 기울기 ( 0 나누기 방어)
        if len(df) >= 5:
            close_5_ago = df['close'].iloc[-5]
            ema20_slope = (
                (trend['ema20'] - close_5_ago) / close_5_ago * 100
                if close_5_ago > 0 else 0.0
            )
        else:
            ema20_slope = 0.0
        features.append(ema20_slope)

        # 21. EMA50 기울기 ( 0 나누기 방어)
        if len(df) >= 10:
            close_10_ago = df['close'].iloc[-10]
            ema50_slope = (
                (trend['ema50'] - close_10_ago) / close_10_ago * 100
                if close_10_ago > 0 else 0.0
            )
        else:
            ema50_slope = 0.0
        features.append(ema50_slope)

        # 22. 추세 강도
        trend_strength_map = {
            'STRONG_UPTREND': 4.0,
            'WEAK_UPTREND' : 3.0,
            'SIDEWAYS' : 2.0,
            'WEAK_DOWNTREND' : 1.0,
            'STRONG_DOWNTREND': 0.0
        }
        features.append(trend_strength_map.get(trend['trend'], 2.0))


        # 23. 연속 캔들
        consecutive = self._count_consecutive_candles(df)
        features.append(consecutive)

        # 24. 5일 수익률 ( 0 나누기 방어!)
        if len(df) >= 5:
            close_5_ago=df['close'].iloc[-5]
            returns_5d = (
                (df['close'].iloc[-1] - close_5_ago) / close_5_ago * 100
                if close_5_ago > 0 else 0.0
            )
        else:
            returns_5d = 0.0
        features.append(returns_5d)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 4. 거래량 ( 5개)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        vol = tech_analysis['volume']

        # 25. Volumn Ratio
        features.append(vol['ratio'])

        # 26. 거래량 추세( 0 나누기 방어!)
        if len(df) >= 20:
            vol_ma5 = df['volumn'].iloc[-5:].mean()
            vol_ma20 = df['volumn'].iloc[-20:].mean()
            vol_trend = vol_ma5 / vol_ma20 if vol_ma20 > 0 else 1.0
        else:
            vol_trend = 1.0
        features.append(vol_trend)

        # 27. 거래량 변화 ( 0 나누기 방어!)
        if len(df) >= 5:
            vol_5_ago = df['volumn'].iloc[-5]
            vol_change = (
                (df['volumn'].iloc[-1] - vol_5_ago) / vol_5_ago * 100
                if vol_5_ago > 0 else 0.0
            )
        else:
            vol_change = 0.0
        features.append(vol_change)

        # 28. 가격-거래량 상관관계
        if len(df) >= 20:
            try:
                corr_matrix = df[['close','volumn']].iloc[-20:].corr()
                price_vol_corr = corr_matrix.iloc[0, 1]

                if pd.isna(price_vol_corr):
                    price_vol_corr = 0.0

            except:
                price_vol_corr = 0.0
        else:
            price_vol_corr = 0.0
        features.append(price_vol_corr)

        # 29. OBV 기울기
        obv_solpe = self._calculate_obv_slope(df)
        features.append(obv_solpe)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 5. 캔들 패턴 (4개)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # 30-32. 캔들 패턴
        if len(df) >= 2:
            hammer = self._detect_hammer(df.iloc[-1])
            doji = self._detect_doji(df.iloc[-1])
            engulfing = self._detect_engulfing(df.iloc[-2:])
        else:
            hammer = False
            doji = False
            engulfing = False

        features.append(1.0 if hammer else 0.0)
        features.append(1.0 if doji else 0.0)
        features.append(1.0 if engulfing else 0.0)

        # 33. 신고가 갱신
        if len(df) >= 20:
            is_new_high = df['high'].iloc[-1] >= df['high'].iloc[-20:].max()
        else:
            is_new_high = False
        features.append(1.0 if is_new_high else 0.0)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 6. 시간 (3개)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        current_time = datetime.now()
        hour = current_time.hour

        # 34-35. 순환 표현
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        features.append(hour_sin)
        features.append(hour_cos)

        # 36. 주말 여부
        is_weekend = 1.0 if current_time.weekday() >= 5 else 0.0
        features.append(is_weekend)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 7. 뉴스 (1개)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # 37. 뉴스 시스템 나중에 연동
        news_urgency = 0.0
        features.append(news_urgency)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 8. 미세 구조 (2개) - Phase 1: 기본값
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # 38. Bid-Ask spread % (WebSocket 연동 시 구현)
        bid_ask_spread = 0.0
        features.append(bid_ask_spread)

        # 39. Order Book Imbalance (WebSocket 연동 시 구현)
        order_book_imbalance = 0.0
        features.append(order_book_imbalance)

        return np.array(features)
