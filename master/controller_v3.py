"""
마스터 컨트롤러 v3.1 - 변동성 기반 전략 선택
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
이벤트 드리븐 AI 호출 + 변동성 기반 전략 선택

핵심 개념:
1. 매 주기마다 로컬 분석 (기술적 지표, 무료)
2. AI 호출 필요성 점수 계산
3. 임계값 초과 시에만 AI 토론
4. 🔥 변동성 기반 전략 자동 선택
5. 비용 70~80% 절감

변동성 고려:
- 저변동성 (<5%): DCA, Grid
- 중변동성 (5~10%): Multi-Indicator
- 고변동성 (>10%): Momentum, Trailing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import datetime, timedelta
from enum import Enum
from config.master_config import AI_CONFIG, ENABLED_STRATEGIES
from utils.logger import info, warning, error
from master.global_risk import global_risk
from analysis.technical import technical_analyzer

# AI 시스템
try:
    from ai.multi_ai_debate_v2 import debate_system
    from ai_call_trigger import ai_trigger
    AI_AVAILABLE = True
    info("✅ 이벤트 드리븐 AI 시스템 로드")
except ImportError:
    AI_AVAILABLE = False
    warning("⚠️ AI 시스템 없음")


class MarketRegime(Enum):
    """시장 국면"""
    STRONG_UPTREND = "강한 상승장"
    WEAK_UPTREND = "약한 상승장"
    SIDEWAYS = "횡보장"
    WEAK_DOWNTREND = "약한 하락장"
    STRONG_DOWNTREND = "강한 하락장"
    UNKNOWN = "판단 불가"


class SmartMasterController:
    """
    스마트 마스터 컨트롤러 v3.1
    이벤트 드리븐 AI 호출 + 변동성 기반 전략 선택
    """

    def __init__(self):
        self.current_regime = MarketRegime.UNKNOWN
        self.ai_enabled = AI_CONFIG['enabled'] and AI_AVAILABLE

        # 의사결정 상태
        self.decision_guide = 'BALANCED'
        self.news_urgency = 5.0
        self.confidence = 0.5

        # 활성 전략
        self.active_strategies = {
            'spot': ENABLED_STRATEGIES['spot'].copy(),
            'futures': ENABLED_STRATEGIES['futures'].copy()
        }

        # 통계
        self.analysis_count = 0
        self.local_analysis_count = 0  # 로컬만 사용
        self.ai_call_count = 0  # AI 호출

        # 마지막 AI 결과 캐시
        self.last_ai_result = None
        self.last_ai_time = None

        info("🧠 스마트 마스터 컨트롤러 v3.1 초기화")
        info(f"  AI 시스템: {'✅ 이벤트 드리븐' if self.ai_enabled else '❌ 비활성'}")
        info(f"  로컬 분석: ✅ 항상 실행")
        info(f"  AI 호출: 필요 시에만")
        info(f"  전략 선택: ✅ 변동성 기반")
        info(f"  현물 전략: {', '.join(self.active_strategies['spot'])}")
        info(f"  선물 전략: {', '.join(self.active_strategies['futures'])}")

    def analyze_and_adjust(self, market_data, news_data=None, position_data=None):
        """
        스마트 시장 분석 + 전략 조정

        Flow:
        1. 리스크 체크 (필수)
        2. 로컬 분석 (항상, 무료)
        3. AI 호출 필요성 판단
        4. 필요 시에만 AI 토론
        5. 결과 통합 및 전략 조정

        Args:
            market_data: 시장 데이터
            news_data: 뉴스 데이터 (선택)
            position_data: 포지션 데이터 (선택)

        Returns:
            dict: 분석 결과 + 전략
        """
        self.analysis_count += 1

        info(f"\n{'='*60}")
        info(f"🔍 스마트 분석 #{self.analysis_count}")
        info(f"{'='*60}")

        # 1. 리스크 체크
        risk_check = global_risk.check_risk_limits()
        if not risk_check.get('trading_allowed', True):
            error("🚫 리스크 한도 초과")
            return self._create_blocked_result('리스크 한도')

        # 2. 로컬 분석 (항상 실행, 무료!)
        local_result = self._local_analysis(market_data)
        self.local_analysis_count += 1

        info(f"📊 로컬 분석:")
        info(f"  국면: {local_result['regime']}")
        info(f"  점수: {local_result['score']:.1f}/5")
        info(f"  변동성: {local_result['volatility']*100:.1f}%")  # 🔥 추가!
        info(f"  추천: {local_result['recommendation']}")

        # 3. AI 호출 필요성 판단
        if self.ai_enabled:
            trigger_result = ai_trigger.should_call_ai(
                market_data,
                news_data,
                position_data
            )

            info(f"\n🤖 AI 호출 판단:")
            info(f"  필요성 점수: {trigger_result['score']:.1f}/{trigger_result['threshold']:.1f}")
            info(f"  판단: {'✅ 호출' if trigger_result['should_call'] else '❌ 로컬만'}")

            if trigger_result['should_call']:
                # AI 토론 실행!
                ai_result = self._ai_debate(market_data, news_data, trigger_result)

                if ai_result:
                    self.ai_call_count += 1
                    self.last_ai_result = ai_result
                    self.last_ai_time = datetime.now()

                    # AI 결과 사용
                    final_result = self._merge_results(local_result, ai_result, 'ai_primary')
                else:
                    # AI 실패 → 로컬 사용
                    warning("⚠️ AI 실패 - 로컬 결과 사용")
                    final_result = local_result

            else:
                # 로컬 결과만 사용
                info(f"  이유: {trigger_result['reason']}")

                # 최근 AI 결과가 있으면 참고
                if self.last_ai_result and self.last_ai_time:
                    elapsed = (datetime.now() - self.last_ai_time).seconds
                    if elapsed < 600:  # 10분 이내
                        info(f"  💡 최근 AI 결과 참고 ({elapsed//60}분 전)")
                        final_result = self._merge_results(
                            local_result,
                            self.last_ai_result,
                            'local_primary'
                        )
                    else:
                        final_result = local_result
                else:
                    final_result = local_result

        else:
            # AI 비활성 → 로컬만
            final_result = local_result

        # 4. 긴급 상황 체크
        if final_result.get('emergency', False):
            error("🚨 긴급 상황!")
            return self._create_emergency_result()

        # 5. 전략 조정 (🔥 변동성 기반!)
        self._adjust_strategies(final_result)

        # 6. 로그
        self._log_analysis(final_result)

        info("="*60)
        info(f"✅ 분석 완료!")
        info(f"  방식: {final_result['source']}")
        info(f"  국면: {self.current_regime.value}")
        info(f"  신뢰도: {self.confidence*100:.0f}%")
        if final_result.get('news_urgency'):
            info(f"  뉴스 중요도: {self.news_urgency:.1f}/10")
        info(f"  의사결정: {self.decision_guide}")
        info(f"  현물: {', '.join(self.active_strategies['spot']) or '없음'}")
        info(f"  선물: {', '.join(self.active_strategies['futures']) or '없음'}")
        info("="*60 + "\n")

        return {
            'regime': self.current_regime,
            'confidence': self.confidence,
            'decision_guide': self.decision_guide,
            'news_urgency': self.news_urgency,
            'strategies': self.active_strategies.copy(),
            'trading_allowed': True,
            'source': final_result['source'],
            'analysis': final_result
        }

    def _local_analysis(self, market_data):
        """
        로컬 분석 (기술적 지표만, 무료!)

        Returns:
            dict: {
                'regime': str,
                'score': float,
                'confidence': float,
                'volatility': float,  # 🔥 추가!
                'recommendation': str,
                'indicators': {...},
                'source': 'local'
            }
        """
        try:
            df = market_data.get('df')
            if df is None or len(df) < 20:
                return self._create_unknown_result('local')

            # 기술적 분석
            analysis = technical_analyzer.analyze(df)

            # 🔥 변동성 계산 (표준편차 기반)
            volatility = self._calculate_volatility(df)

            # 국면 매핑
            score = analysis.get('score', 0)
            if score >= 3:
                regime = 'STRONG_UPTREND'
            elif score >= 1:
                regime = 'WEAK_UPTREND'
            elif score <= -3:
                regime = 'STRONG_DOWNTREND'
            elif score <= -1:
                regime = 'WEAK_DOWNTREND'
            else:
                regime = 'SIDEWAYS'

            # 신뢰도 (기술적 분석만이므로 중간)
            confidence = min(abs(score) / 5 * 0.7, 0.7)

            return {
                'regime': regime,
                'score': score,
                'confidence': confidence,
                'volatility': volatility,  # 🔥 추가!
                'recommendation': analysis.get('recommendation', 'HOLD'),
                'indicators': {
                    'rsi': analysis.get('rsi'),
                    'macd': analysis.get('macd'),
                    'bollinger': analysis.get('bollinger'),
                    'ma': analysis.get('ma'),
                    'volume': analysis.get('volume')
                },
                'news_sentiment': 'NEUTRAL',
                'news_urgency': 0.0,
                'decision_guide': 'CHART_PRIORITY',
                'source': 'local'
            }

        except Exception as e:
            error(f"❌ 로컬 분석 오류: {e}")
            return self._create_unknown_result('local_error')

    def _calculate_volatility(self, df):
        """
        변동성 계산 (표준편차 기반)

        Args:
            df: OHLCV 데이터프레임

        Returns:
            float: 변동성 (0.0~1.0)
        """
        try:
            # 최근 20개 봉의 수익률 표준편차
            if len(df) < 20:
                return 0.05  # 기본값

            recent_df = df.tail(20)

            # 일일 수익률 계산
            returns = recent_df['close'].pct_change().dropna()

            # 표준편차 (변동성)
            volatility = returns.std()

            # NaN 체크
            if volatility is None or volatility != volatility:  # NaN check
                return 0.05

            return float(volatility)

        except Exception as e:
            warning(f"⚠️ 변동성 계산 오류: {e}")
            return 0.05  # 기본값 (5%)

    def _ai_debate(self, market_data, news_data, trigger_info):
        """AI 토론 실행"""
        try:
            info(f"\n🎭 AI 토론 시작...")
            info(f"  긴급도: {trigger_info['urgency']}")
            info(f"  트리거: {trigger_info['reason']}")

            # AI 토론
            result = debate_system.analyze(
                market_data,
                include_news=(news_data is not None)
            )

            if result:
                info(f"✅ AI 토론 완료")
                info(f"  라운드: {result.get('rounds_count', 0)}")
                info(f"  합의도: {result.get('final_agreement', 0)*100:.0f}%")
                result['source'] = 'ai_debate'
                result['trigger_info'] = trigger_info
                return result
            else:
                warning("⚠️ AI 토론 실패")
                return None

        except Exception as e:
            error(f"❌ AI 토론 오류: {e}")
            return None

    def _merge_results(self, local_result, ai_result, mode='ai_primary'):
        """로컬 + AI 결과 통합"""

        if mode == 'ai_primary':
            # AI 결과 우선, 로컬은 보조
            base = ai_result.copy()
            base['local_indicators'] = local_result.get('indicators')
            base['volatility'] = local_result.get('volatility', 0.05)  # 🔥 추가!
            base['source'] = 'ai_debate_primary'
            return base

        elif mode == 'local_primary':
            # 로컬 결과 우선, AI는 참고
            base = local_result.copy()

            # AI의 뉴스 정보만 추가
            if ai_result:
                base['news_sentiment'] = ai_result.get('news_sentiment', 'NEUTRAL')
                base['news_urgency'] = ai_result.get('news_urgency', 0.0)

                # AI 국면과 차이가 크면 신뢰도 낮춤
                if ai_result.get('regime') != base['regime']:
                    base['confidence'] *= 0.8
                    base['conflict'] = {
                        'local': base['regime'],
                        'ai': ai_result.get('regime')
                    }

            base['source'] = 'local_with_ai_context'
            return base

        else:
            # 균형 (평균)
            return self._average_results(local_result, ai_result)

    def _average_results(self, local_result, ai_result):
        """두 결과 평균"""
        # 간단 구현: AI 결과 우선하되 신뢰도 보정
        result = ai_result.copy()
        result['confidence'] = (
            local_result['confidence'] * 0.3 +
            ai_result['confidence'] * 0.7
        )
        result['volatility'] = local_result.get('volatility', 0.05)  # 🔥 추가!
        result['source'] = 'merged'
        result['local_indicators'] = local_result.get('indicators')
        return result

    def _adjust_strategies(self, analysis):
        """
        전략 조정 (🔥 변동성 기반!)

        변동성 분류:
        - 저변동: < 5%   → DCA, Grid
        - 중변동: 5~10%  → Multi-Indicator
        - 고변동: > 10%  → Momentum, Trailing
        """
        regime = analysis.get('regime', 'SIDEWAYS')
        self.current_regime = MarketRegime[regime]

        self.confidence = analysis.get('confidence', 0.5)
        self.decision_guide = analysis.get('decision_guide', 'BALANCED')
        self.news_urgency = analysis.get('news_urgency', 0.0)

        # 🔥 변동성 가져오기
        volatility = analysis.get('volatility', 0.05)

        # 변동성 분류
        if volatility < 0.05:
            vol_level = 'LOW'  # 저변동
        elif volatility < 0.10:
            vol_level = 'MED'  # 중변동
        else:
            vol_level = 'HIGH'  # 고변동

        info(f"📊 변동성 분류: {vol_level} ({volatility*100:.1f}%)")

        # 🔥 국면 + 변동성 조합 전략 선택
        if regime == 'STRONG_DOWNTREND':
            # 강한 하락장 → 모든 거래 중단
            self.active_strategies['spot'] = []
            self.active_strategies['futures'] = []

        elif regime == 'WEAK_DOWNTREND':
            # 약한 하락장 → 변동성 따라 다르게
            if vol_level == 'HIGH':
                # 고변동 → 모멘텀 (단기 반등 노림)
                self.active_strategies['spot'] = ['momentum']
                self.active_strategies['futures'] = []
            elif vol_level == 'MED':
                # 중변동 → Multi-Indicator (신중)
                self.active_strategies['spot'] = ['multi_indicator']
                self.active_strategies['futures'] = []
            else:
                # 저변동 → DCA (분할 매수)
                self.active_strategies['spot'] = ['dca']
                self.active_strategies['futures'] = []

        elif regime == 'SIDEWAYS':
            # 횡보장 → Grid 기본, 고변동이면 Scalping
            if vol_level == 'HIGH':
                self.active_strategies['spot'] = ['scalping']
                self.active_strategies['futures'] = ['scalping']
            else:
                self.active_strategies['spot'] = ['grid']
                self.active_strategies['futures'] = ['scalping']

        elif regime == 'WEAK_UPTREND':
            # 약한 상승장
            if vol_level == 'HIGH':
                # 고변동 → Momentum + Trailing
                self.active_strategies['spot'] = ['momentum', 'trailing']
                self.active_strategies['futures'] = ['long_short']
            else:
                # 저/중변동 → Multi-Indicator
                self.active_strategies['spot'] = ['multi_indicator']
                self.active_strategies['futures'] = ['long_short']

        elif regime == 'STRONG_UPTREND':
            # 강한 상승장
            if vol_level == 'HIGH':
                # 고변동 → Momentum (공격적)
                self.active_strategies['spot'] = ['momentum', 'breakout']
                self.active_strategies['futures'] = ['long_short']
            else:
                # 저/중변동 → Multi-Indicator + Breakout
                self.active_strategies['spot'] = ['multi_indicator', 'breakout']
                self.active_strategies['futures'] = ['long_short']

        # 🔥 뉴스 우선이면 보수적 조정 (임계값 낮춤!)
        if self.decision_guide == 'NEWS_PRIORITY' and self.news_urgency >= 7.0:  # 8.0 → 7.0
            warning("⚠️ 뉴스 중요도 높음 - 보수적 전략")
            self.active_strategies['futures'] = []

            if regime in ['WEAK_UPTREND', 'STRONG_UPTREND']:
                # 상승장이어도 신중하게
                if vol_level == 'HIGH':
                    self.active_strategies['spot'] = ['trailing']  # 안전하게
                else:
                    self.active_strategies['spot'] = ['multi_indicator']
            else:
                # 하락/횡보는 거래 중단
                self.active_strategies['spot'] = []

    def _create_blocked_result(self, reason):
        """차단 결과"""
        return {
            'regime': MarketRegime.UNKNOWN,
            'confidence': 0.0,
            'decision_guide': 'BLOCKED',
            'news_urgency': 0.0,
            'strategies': {'spot': [], 'futures': []},
            'trading_allowed': False,
            'reason': reason,
            'source': 'blocked'
        }

    def _create_emergency_result(self):
        """긴급 결과"""
        return {
            'regime': MarketRegime.STRONG_DOWNTREND,
            'confidence': 1.0,
            'decision_guide': 'NEWS_PRIORITY',
            'news_urgency': 10.0,
            'emergency': True,
            'strategies': {'spot': [], 'futures': []},
            'trading_allowed': False,
            'reason': '긴급 상황',
            'source': 'emergency'
        }

    def _create_unknown_result(self, source):
        """알 수 없음"""
        return {
            'regime': 'SIDEWAYS',
            'score': 0,
            'confidence': 0.3,
            'volatility': 0.05,  # 🔥 추가!
            'recommendation': 'HOLD',
            'news_sentiment': 'NEUTRAL',
            'news_urgency': 0.0,
            'decision_guide': 'BALANCED',
            'source': source
        }

    def _log_analysis(self, analysis):
        """분석 로그"""
        # 간단 로그 (추후 확장)
        pass

    def get_statistics(self):
        """통계"""
        total = self.analysis_count
        local_only = self.local_analysis_count - self.ai_call_count
        ai_rate = self.ai_call_count / total * 100 if total > 0 else 0

        # AI 트리거 통계
        trigger_stats = {}
        if AI_AVAILABLE:
            try:
                trigger_stats = ai_trigger.get_statistics()
            except:
                pass

        return {
            'version': 'v3.1_volatility_based',
            'total_analysis': self.analysis_count,
            'local_only': local_only,
            'ai_calls': self.ai_call_count,
            'ai_call_rate': ai_rate,
            'savings_rate': 100 - ai_rate,
            'current_regime': self.current_regime.value,
            'confidence': self.confidence,
            'decision_guide': self.decision_guide,
            'trigger_stats': trigger_stats
        }


# 전역 인스턴스
smart_controller = SmartMasterController()


# 테스트
if __name__ == "__main__":
    import pandas as pd
    import numpy as np

    print("🧪 스마트 마스터 컨트롤러 v3.1 테스트 (변동성 기반)\n")

    # 테스트 데이터 1: 저변동
    print("="*60)
    print("테스트 1: 저변동성 + 약한 하락장")
    print("="*60)

    test_df_low = pd.DataFrame({
        'open': np.linspace(100000, 99000, 100),
        'high': np.linspace(101000, 100000, 100),
        'low': np.linspace(99000, 98000, 100),
        'close': np.linspace(100000, 99000, 100),
        'volume': [1000] * 100
    })

    result = smart_controller.analyze_and_adjust({
        'coin': 'BTC',
        'price': 99000,
        'df': test_df_low
    })

    print(f"→ 전략: {result['strategies']['spot']}")
    print(f"   예상: ['dca']")

    # 테스트 데이터 2: 고변동
    print("\n" + "="*60)
    print("테스트 2: 고변동성 + 약한 하락장")
    print("="*60)

    test_df_high = pd.DataFrame({
        'open': [100000 + np.random.randint(-10000, 10000) for _ in range(100)],
        'high': [101000 + np.random.randint(-10000, 10000) for _ in range(100)],
        'low': [99000 + np.random.randint(-10000, 10000) for _ in range(100)],
        'close': [100000 + np.random.randint(-10000, 10000) for _ in range(100)],
        'volume': [1000] * 100
    })

    result2 = smart_controller.analyze_and_adjust({
        'coin': 'AERO',
        'price': 100000,
        'df': test_df_high
    })

    print(f"→ 전략: {result2['strategies']['spot']}")
    print(f"   예상: ['momentum']")

    # 통계
    print("\n" + "="*60)
    print("📊 통계")
    print("="*60)
    stats = smart_controller.get_statistics()
    print(f"버전: {stats['version']}")
    print(f"총 분석: {stats['total_analysis']}회")
    print(f"로컬만: {stats['local_only']}회")
    print(f"AI 호출: {stats['ai_calls']}회")