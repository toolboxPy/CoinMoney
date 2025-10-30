"""
이벤트 드리븐 AI 호출 시스템
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
시간 기반 → 이벤트 기반 전환

핵심 개념:
- 로컬 분석으로 대부분 처리 (무료)
- AI 필요성 점수 계산
- 임계값 초과 시에만 AI 호출 (비용 효율)

예상 절감: 70~80%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import info, warning, error
from analysis.technical import technical_analyzer


class AICallTrigger:
    """AI 호출 트리거 시스템"""
    
    def __init__(self):
        # 트리거 임계값
        self.thresholds = {
            # 시장 급변
            'price_change_5m': 3.0,      # 5분간 3% 이상
            'price_change_1h': 5.0,      # 1시간 5% 이상
            'volume_surge': 2.5,         # 평균 대비 2.5배
            'volatility': 5.0,           # 변동성 5%
            
            # 기술적 이벤트
            'pattern_score': 7.0,        # 패턴 중요도
            'support_resistance': 0.02,  # 2% 이내
            'indicator_conflict': 3.0,   # 지표 충돌 점수
            
            # 뉴스
            'news_urgency': 6.5,         # 뉴스 중요도
            'news_count_1h': 5,          # 1시간 5개 이상

            # 포지션
            'position_risk': 0.8,        # 리스크 80%
            'pnl_critical': 0.02,        # 손익 ±2%

            # AI 호출 점수
            'call_threshold': 50.0       # 50점 이상이면 호출
        }

        # 상태 추적
        self.last_ai_call = None
        self.ai_call_count = 0
        self.prevented_calls = 0  # 절약한 호출 횟수

        # 최소 간격 (과도한 호출 방지)
        self.min_interval = timedelta(minutes=3)
        self.normal_interval = timedelta(minutes=10)

        # 최근 데이터 캐시
        self.cache = {
            'last_price': None,
            'price_history': [],
            'volume_avg': None,
            'last_pattern': None,
            'last_news_check': None
        }

        info("🎯 이벤트 드리븐 AI 호출 시스템 초기화")
        info(f"  AI 호출 임계값: {self.thresholds['call_threshold']}점")
        info(f"  최소 호출 간격: {self.min_interval.seconds//60}분")

    def should_call_ai(self, market_data, news_data=None, position_data=None):
        """
        AI 호출 필요 여부 판단

        Args:
            market_data: 시장 데이터 (가격, 차트, 지표)
            news_data: 뉴스 데이터
            position_data: 포지션 데이터

        Returns:
            dict: {
                'should_call': bool,
                'score': float,
                'reason': str,
                'urgency': str,  # 'low', 'normal', 'high', 'emergency'
                'triggers': [...]
            }
        """
        # 1. 최소 간격 체크 (긴급 제외)
        if self.last_ai_call:
            elapsed = datetime.now() - self.last_ai_call
            if elapsed < self.min_interval:
                # 긴급 상황 아니면 대기
                if not self._is_emergency(market_data, news_data):
                    self.prevented_calls += 1
                    return {
                        'should_call': False,
                        'score': 0,
                        'reason': f'최소 간격 미달 ({elapsed.seconds}초)',
                        'urgency': 'blocked',
                        'triggers': []
                    }

        # 2. 트리거 점수 계산
        triggers = []
        total_score = 0

        # 2-1. 시장 급변 체크
        market_triggers, market_score = self._check_market_events(market_data)
        triggers.extend(market_triggers)
        total_score += market_score

        # 2-2. 기술적 이벤트 체크
        technical_triggers, technical_score = self._check_technical_events(market_data)
        triggers.extend(technical_triggers)
        total_score += technical_score

        # 2-3. 뉴스 이벤트 체크
        if news_data:
            news_triggers, news_score = self._check_news_events(news_data)
            triggers.extend(news_triggers)
            total_score += news_score

        # 2-4. 포지션 이벤트 체크
        if position_data:
            position_triggers, position_score = self._check_position_events(position_data)
            triggers.extend(position_triggers)
            total_score += position_score

        # 2-5. 지표 충돌 체크
        conflict_triggers, conflict_score = self._check_indicator_conflicts(market_data)
        triggers.extend(conflict_triggers)
        total_score += conflict_score

        # 3. 긴급도 판단
        urgency = self._determine_urgency(total_score, triggers)

        # 4. 호출 여부 결정
        threshold = self.thresholds['call_threshold']
        should_call = total_score >= threshold

        if should_call:
            self.last_ai_call = datetime.now()
            self.ai_call_count += 1
            info(f"🤖 AI 호출 트리거! (점수: {total_score:.1f}, 긴급도: {urgency})")
            for trigger in triggers:
                info(f"  - {trigger['reason']} (+{trigger['score']:.1f}점)")
        else:
            self.prevented_calls += 1

        # 5. 결과 반환
        result = {
            'should_call': should_call,
            'score': total_score,
            'reason': self._compile_reason(triggers),
            'urgency': urgency,
            'triggers': triggers,
            'threshold': threshold,
            'time_since_last': elapsed.seconds if self.last_ai_call else 0
        }

        return result

    def _check_market_events(self, market_data):
        """시장 급변 이벤트 체크"""
        triggers = []
        score = 0

        current_price = market_data.get('price', 0)
        df = market_data.get('df')

        if df is None or len(df) < 2:
            return triggers, score

        # 가격 변화율 (5분, 1시간)
        try:
            # 5분 변화
            if len(df) >= 5:
                price_5m_ago = df['close'].iloc[-5]
                change_5m = abs((current_price - price_5m_ago) / price_5m_ago * 100)

                if change_5m >= self.thresholds['price_change_5m']:
                    direction = "급등" if current_price > price_5m_ago else "급락"
                    triggers.append({
                        'type': 'market',
                        'event': 'price_change_5m',
                        'value': change_5m,
                        'reason': f"5분간 {direction} ({change_5m:.1f}%)",
                        'score': min(change_5m * 5, 30)  # 최대 30점
                    })
                    score += triggers[-1]['score']

            # 1시간 변화
            if len(df) >= 60:
                price_1h_ago = df['close'].iloc[-60]
                change_1h = abs((current_price - price_1h_ago) / price_1h_ago * 100)

                if change_1h >= self.thresholds['price_change_1h']:
                    direction = "상승" if current_price > price_1h_ago else "하락"
                    triggers.append({
                        'type': 'market',
                        'event': 'price_change_1h',
                        'value': change_1h,
                        'reason': f"1시간 {direction} ({change_1h:.1f}%)",
                        'score': min(change_1h * 3, 25)  # 최대 25점
                    })
                    score += triggers[-1]['score']

            # 거래량 급증
            if len(df) >= 20:
                recent_volume = df['volume'].iloc[-1]
                avg_volume = df['volume'].iloc[-20:-1].mean()

                if avg_volume > 0:
                    volume_ratio = recent_volume / avg_volume

                    if volume_ratio >= self.thresholds['volume_surge']:
                        triggers.append({
                            'type': 'market',
                            'event': 'volume_surge',
                            'value': volume_ratio,
                            'reason': f"거래량 폭증 ({volume_ratio:.1f}배)",
                            'score': min((volume_ratio - 1) * 10, 20)  # 최대 20점
                        })
                        score += triggers[-1]['score']

            # 변동성 급증
            if len(df) >= 24:
                recent_high = df['high'].tail(24).max()
                recent_low = df['low'].tail(24).min()
                volatility = (recent_high - recent_low) / current_price * 100

                if volatility >= self.thresholds['volatility']:
                    triggers.append({
                        'type': 'market',
                        'event': 'volatility',
                        'value': volatility,
                        'reason': f"변동성 급증 ({volatility:.1f}%)",
                        'score': min(volatility * 2, 15)  # 최대 15점
                    })
                    score += triggers[-1]['score']

        except Exception as e:
            warning(f"⚠️ 시장 이벤트 체크 오류: {e}")

        return triggers, score

    def _check_technical_events(self, market_data):
        """기술적 이벤트 체크"""
        triggers = []
        score = 0

        df = market_data.get('df')
        current_price = market_data.get('price', 0)

        if df is None or len(df) < 20:
            return triggers, score

        try:
            # 기술적 분석
            analysis = technical_analyzer.analyze(df)

            # RSI 극단
            rsi = analysis.get('rsi', {}).get('value', 50)
            if rsi <= 25:
                triggers.append({
                    'type': 'technical',
                    'event': 'rsi_oversold',
                    'value': rsi,
                    'reason': f"RSI 극단 과매도 ({rsi:.0f})",
                    'score': (30 - rsi) * 0.5  # 최대 12.5점
                })
                score += triggers[-1]['score']
            elif rsi >= 75:
                triggers.append({
                    'type': 'technical',
                    'event': 'rsi_overbought',
                    'value': rsi,
                    'reason': f"RSI 극단 과매수 ({rsi:.0f})",
                    'score': (rsi - 70) * 0.5  # 최대 15점
                })
                score += triggers[-1]['score']

            # MACD 크로스 (최근 발생)
            macd_data = analysis.get('macd', {})
            if macd_data.get('bullish_cross_recent'):
                triggers.append({
                    'type': 'technical',
                    'event': 'golden_cross',
                    'value': True,
                    'reason': "MACD 골든크로스",
                    'score': 15
                })
                score += 15
            elif macd_data.get('bearish_cross_recent'):
                triggers.append({
                    'type': 'technical',
                    'event': 'death_cross',
                    'value': True,
                    'reason': "MACD 데드크로스",
                    'score': 15
                })
                score += 15

            # 볼린저 밴드 터치
            bollinger = analysis.get('bollinger', {})
            bb_position = bollinger.get('position', 0.5)
            if bb_position <= 0.1:
                triggers.append({
                    'type': 'technical',
                    'event': 'bb_lower',
                    'value': bb_position,
                    'reason': "볼린저 밴드 하단 터치",
                    'score': 10
                })
                score += 10
            elif bb_position >= 0.9:
                triggers.append({
                    'type': 'technical',
                    'event': 'bb_upper',
                    'value': bb_position,
                    'reason': "볼린저 밴드 상단 터치",
                    'score': 10
                })
                score += 10

            # 이동평균선 정/역배열 전환
            ma_data = analysis.get('ma', {})
            ma_trend = ma_data.get('trend', 'UNKNOWN')
            if ma_trend in ['STRONG_UPTREND', 'STRONG_DOWNTREND']:
                triggers.append({
                    'type': 'technical',
                    'event': 'ma_alignment',
                    'value': ma_trend,
                    'reason': f"이동평균선 {ma_trend}",
                    'score': 12
                })
                score += 12

        except Exception as e:
            warning(f"⚠️ 기술적 이벤트 체크 오류: {e}")

        return triggers, score

    def _check_news_events(self, news_data):
        """뉴스 이벤트 체크"""
        triggers = []
        score = 0

        try:
            # 뉴스 중요도
            news_urgency = news_data.get('urgency', 0)
            if news_urgency >= self.thresholds['news_urgency']:
                triggers.append({
                    'type': 'news',
                    'event': 'important_news',
                    'value': news_urgency,
                    'reason': f"중요 뉴스 ({news_urgency:.1f}/10)",
                    'score': news_urgency * 4  # 최대 40점
                })
                score += triggers[-1]['score']

            # 긴급 뉴스
            if news_data.get('emergency', False):
                triggers.append({
                    'type': 'news',
                    'event': 'emergency',
                    'value': True,
                    'reason': "긴급 뉴스 발생",
                    'score': 50  # 즉시 호출
                })
                score += 50

            # 뉴스 개수 급증
            news_count = news_data.get('count_1h', 0)
            if news_count >= self.thresholds['news_count_1h']:
                triggers.append({
                    'type': 'news',
                    'event': 'news_surge',
                    'value': news_count,
                    'reason': f"1시간 뉴스 {news_count}개",
                    'score': min(news_count * 2, 15)  # 최대 15점
                })
                score += triggers[-1]['score']

        except Exception as e:
            warning(f"⚠️ 뉴스 이벤트 체크 오류: {e}")

        return triggers, score

    def _check_position_events(self, position_data):
        """포지션 이벤트 체크"""
        triggers = []
        score = 0

        try:
            # 손익률
            pnl_ratio = position_data.get('pnl_ratio', 0)

            # 손절/익절 근처
            stop_loss = position_data.get('stop_loss', -0.03)
            take_profit = position_data.get('take_profit', 0.05)

            if abs(pnl_ratio - stop_loss) <= self.thresholds['pnl_critical']:
                triggers.append({
                    'type': 'position',
                    'event': 'near_stop_loss',
                    'value': pnl_ratio,
                    'reason': f"손절 근처 ({pnl_ratio*100:.1f}%)",
                    'score': 20
                })
                score += 20

            elif abs(pnl_ratio - take_profit) <= self.thresholds['pnl_critical']:
                triggers.append({
                    'type': 'position',
                    'event': 'near_take_profit',
                    'value': pnl_ratio,
                    'reason': f"익절 근처 ({pnl_ratio*100:.1f}%)",
                    'score': 18
                })
                score += 18

            # Trailing Stop 위기
            if position_data.get('trailing_stop_risk', False):
                triggers.append({
                    'type': 'position',
                    'event': 'trailing_risk',
                    'value': True,
                    'reason': "Trailing Stop 위기",
                    'score': 15
                })
                score += 15

            # 포지션 리스크
            risk_score = position_data.get('risk_score', 0)
            if risk_score >= self.thresholds['position_risk']:
                triggers.append({
                    'type': 'position',
                    'event': 'high_risk',
                    'value': risk_score,
                    'reason': f"포지션 리스크 높음 ({risk_score*100:.0f}%)",
                    'score': min(risk_score * 25, 20)  # 최대 20점
                })
                score += triggers[-1]['score']

        except Exception as e:
            warning(f"⚠️ 포지션 이벤트 체크 오류: {e}")

        return triggers, score

    def _check_indicator_conflicts(self, market_data):
        """지표 간 충돌 체크"""
        triggers = []
        score = 0

        df = market_data.get('df')
        if df is None or len(df) < 20:
            return triggers, score

        try:
            analysis = technical_analyzer.analyze(df)

            # RSI vs MACD 충돌
            rsi_signal = analysis.get('rsi', {}).get('signal', 'NEUTRAL')
            macd_signal = analysis.get('macd', {}).get('signal', 'NEUTRAL')

            if (rsi_signal == 'OVERSOLD' and macd_signal == 'BEARISH') or \
               (rsi_signal == 'OVERBOUGHT' and macd_signal == 'BULLISH'):
                triggers.append({
                    'type': 'conflict',
                    'event': 'rsi_macd_conflict',
                    'value': f"{rsi_signal} vs {macd_signal}",
                    'reason': f"RSI-MACD 충돌 ({rsi_signal} vs {macd_signal})",
                    'score': 15
                })
                score += 15

            # 가격 vs 볼린저 충돌
            bb_position = analysis.get('bollinger', {}).get('position', 0.5)
            ma_trend = analysis.get('ma', {}).get('trend', 'UNKNOWN')

            if (bb_position <= 0.2 and ma_trend == 'DOWNTREND') or \
               (bb_position >= 0.8 and ma_trend == 'UPTREND'):
                triggers.append({
                    'type': 'conflict',
                    'event': 'price_trend_conflict',
                    'value': f"{bb_position:.2f} vs {ma_trend}",
                    'reason': "가격-추세 충돌",
                    'score': 12
                })
                score += 12

        except Exception as e:
            warning(f"⚠️ 지표 충돌 체크 오류: {e}")

        return triggers, score

    def _is_emergency(self, market_data, news_data):
        """긴급 상황 체크"""
        # 뉴스 긴급
        if news_data and news_data.get('emergency', False):
            return True

        # 가격 급락 (5분 5% 이상)
        current_price = market_data.get('price', 0)
        df = market_data.get('df')

        if df is not None and len(df) >= 5:
            try:
                price_5m_ago = df['close'].iloc[-5]
                change = (current_price - price_5m_ago) / price_5m_ago * 100

                if change <= -5:  # 5% 급락
                    return True
            except:
                pass

        return False

    def _determine_urgency(self, score, triggers):
        """긴급도 판단"""
        # 긴급 트리거 확인
        emergency_events = ['emergency', 'price_crash']
        for trigger in triggers:
            if trigger['event'] in emergency_events:
                return 'emergency'

        # 점수 기반
        if score >= 80:
            return 'emergency'
        elif score >= 60:
            return 'high'
        elif score >= 40:
            return 'normal'
        else:
            return 'low'

    def _compile_reason(self, triggers):
        """트리거 이유 요약"""
        if not triggers:
            return "트리거 없음"

        # 상위 3개만
        top_triggers = sorted(triggers, key=lambda x: x['score'], reverse=True)[:3]
        reasons = [t['reason'] for t in top_triggers]

        return " | ".join(reasons)

    def get_statistics(self):
        """통계 조회"""
        total_checks = self.ai_call_count + self.prevented_calls
        savings_rate = self.prevented_calls / total_checks * 100 if total_checks > 0 else 0

        return {
            'ai_calls': self.ai_call_count,
            'prevented_calls': self.prevented_calls,
            'total_checks': total_checks,
            'savings_rate': savings_rate,
            'last_call': self.last_ai_call.isoformat() if self.last_ai_call else None
        }


# 전역 인스턴스
ai_trigger = AICallTrigger()


# 테스트 코드
if __name__ == "__main__":
    import pandas as pd

    print("🧪 이벤트 드리븐 AI 호출 시스템 테스트\n")

    # 테스트 1: 평상시 (호출 안 함)
    print("=" * 60)
    print("테스트 1: 평상시")
    print("=" * 60)

    normal_data = {
        'price': 95000000,
        'df': pd.DataFrame({
            'open': [94000000] * 100,
            'high': [94500000] * 100,
            'low': [93500000] * 100,
            'close': [94000000] * 100,
            'volume': [1000] * 100
        })
    }

    result = ai_trigger.should_call_ai(normal_data)
    print(f"호출 여부: {'✅ 호출' if result['should_call'] else '❌ 대기'}")
    print(f"점수: {result['score']:.1f}/{result['threshold']:.1f}")
    print(f"이유: {result['reason']}")

    # 테스트 2: 급등 (호출!)
    print("\n" + "=" * 60)
    print("테스트 2: 5분간 5% 급등")
    print("=" * 60)

    surge_df = pd.DataFrame({
        'open': [90000000] * 95 + [94000000] * 5,
        'high': [90500000] * 95 + [95000000] * 5,
        'low': [89500000] * 95 + [93500000] * 5,
        'close': [90000000] * 95 + [94500000] * 5,
        'volume': [1000] * 100
    })

    surge_data = {
        'price': 94500000,
        'df': surge_df
    }

    result = ai_trigger.should_call_ai(surge_data)
    print(f"호출 여부: {'✅ 호출' if result['should_call'] else '❌ 대기'}")
    print(f"점수: {result['score']:.1f}/{result['threshold']:.1f}")
    print(f"긴급도: {result['urgency']}")
    print(f"트리거:")
    for trigger in result['triggers']:
        print(f"  - {trigger['reason']} (+{trigger['score']:.1f}점)")

    # 테스트 3: 긴급 뉴스 (즉시 호출!)
    print("\n" + "=" * 60)
    print("테스트 3: 긴급 뉴스")
    print("=" * 60)

    news_data = {
        'urgency': 9.5,
        'emergency': True
    }

    result = ai_trigger.should_call_ai(normal_data, news_data=news_data)
    print(f"호출 여부: {'✅ 호출' if result['should_call'] else '❌ 대기'}")
    print(f"점수: {result['score']:.1f}/{result['threshold']:.1f}")
    print(f"긴급도: {result['urgency']}")

    # 통계
    print("\n" + "=" * 60)
    print("📊 통계")
    print("=" * 60)
    stats = ai_trigger.get_statistics()
    print(f"AI 호출: {stats['ai_calls']}회")
    print(f"절약: {stats['prevented_calls']}회")
    print(f"절감률: {stats['savings_rate']:.1f}%")