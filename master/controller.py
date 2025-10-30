"""
마스터 컨트롤러
시스템의 두뇌 - 시장 분석 + 뉴스 기반 의사결정 + 전략 관리 + AI 동적 토론
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import time
from datetime import datetime, timedelta
from enum import Enum
from config.master_config import AI_CONFIG, ENABLED_STRATEGIES
from utils.logger import info, warning, error
from utils.performance_tracker import performance_tracker
from master.global_risk import global_risk
from analysis.technical import technical_analyzer
from ai.multi_ai_analyzer import multi_ai
from ai.multi_ai_debate_dynamic import start_dynamic_debate, get_protocol_stats


class MarketRegime(Enum):
    """시장 국면"""
    STRONG_UPTREND = "강한 상승장"
    WEAK_UPTREND = "약한 상승장"
    SIDEWAYS = "횡보장"
    WEAK_DOWNTREND = "약한 하락장"
    STRONG_DOWNTREND = "강한 하락장"
    UNKNOWN = "판단 불가"


class MasterController:
    """마스터 컨트롤러 (뉴스 기반 의사결정 + AI 동적 토론)"""

    def __init__(self):
        self.current_regime = MarketRegime.UNKNOWN
        self.ai_enabled = AI_CONFIG['enabled']
        self.ai_available = True
        self.ai_failure_count = 0

        # 의사결정 가이드
        self.decision_guide = 'BALANCED'
        self.news_urgency = 5.0

        # 🔥 NEW: AI 동적 토론 설정
        self.debate_config = {
            'interval': timedelta(minutes=30),  # 30분 주기
            'rounds': 5,                        # 5라운드
            'enable_evolution': True            # 동적 진화
        }
        self.last_debate_time = None

        # 활성 전략
        self.active_strategies = {
            'spot': ENABLED_STRATEGIES['spot'].copy(),
            'futures': ENABLED_STRATEGIES['futures'].copy()
        }

        info("🎯 마스터 컨트롤러 초기화")
        info(f"  AI 분석: {'✅ 활성화' if self.ai_enabled else '❌ 비활성화'}")
        info(f"  AI 토론: 30분 주기, 5라운드")

        # 프로토콜 상태
        try:
            stats = get_protocol_stats()
            info(f"  프로토콜: v{stats['version']} ({stats['total_abbreviations']}개 약어)")
        except:
            pass

        info(f"  현물 전략: {', '.join(self.active_strategies['spot'])}")
        info(f"  선물 전략: {', '.join(self.active_strategies['futures'])}")

    def should_run_debate(self):
        """
        AI 토론 실행 여부 판단

        Returns:
            bool: 토론 실행 필요 시 True
        """
        # 첫 실행
        if self.last_debate_time is None:
            return True

        # 30분 경과 체크
        elapsed = datetime.now() - self.last_debate_time
        return elapsed >= self.debate_config['interval']

    def analyze_and_adjust(self, market_data, include_news=True):
        """
        시장 분석 + 뉴스 기반 의사결정 + AI 토론 + 전략 조정

        Args:
            market_data: {
                'coin': 'BTC',
                'df': DataFrame (OHLCV),
                'price': current_price,
                ...
            }
            include_news: 뉴스 분석 포함 여부

        Returns:
            dict: {
                'regime': MarketRegime,
                'confidence': float,
                'decision_guide': 'NEWS_PRIORITY' / 'CHART_PRIORITY' / 'BALANCED',
                'news_urgency': float,
                'strategies': {...},
                'trading_allowed': bool
            }
        """
        info("\n" + "="*60)
        info("🎯 마스터 컨트롤러: 시장 분석 시작")
        info("="*60)

        # 1. 글로벌 리스크 체크
        risk_status = global_risk.check_risk_limits()

        if not risk_status['trading_allowed']:
            error(f"🚨 거래 중단: {risk_status['reason']}")
            return {
                'regime': MarketRegime.STRONG_DOWNTREND,
                'confidence': 1.0,
                'decision_guide': 'CHART_PRIORITY',
                'news_urgency': 0.0,
                'strategies': {'spot': [], 'futures': []},
                'trading_allowed': False,
                'reason': risk_status['reason']
            }

        # 경고가 있으면 표시
        if risk_status['warnings']:
            for w in risk_status['warnings']:
                warning(f"⚠️ {w}")

        # 2. 시장 국면 분석 (뉴스 + AI 토론)
        regime_analysis = self._analyze_market_regime(market_data, include_news)

        if regime_analysis is None:
            # Fallback: 기술적 분석만 사용
            warning("⚠️ AI 분석 실패 - Fallback 모드")
            regime_analysis = self._fallback_analysis(market_data)

        self.current_regime = regime_analysis['regime']
        self.decision_guide = regime_analysis.get('decision_guide', 'BALANCED')
        self.news_urgency = regime_analysis.get('news_urgency', 5.0)

        # 긴급 상황 체크
        if regime_analysis.get('emergency', False):
            error("🚨 긴급 상황 감지 - 모든 거래 중단!")
            return {
                'regime': MarketRegime.STRONG_DOWNTREND,
                'confidence': 1.0,
                'decision_guide': 'NEWS_PRIORITY',
                'news_urgency': 10.0,
                'emergency': True,
                'strategies': {'spot': [], 'futures': []},
                'trading_allowed': False,
                'reason': '뉴스: 긴급 상황'
            }

        # 3. 전략 조정 (의사결정 가이드 반영)
        self._adjust_strategies(regime_analysis)

        info("="*60)
        info(f"📊 최종 판단: {self.current_regime.value}")
        info(f"💪 신뢰도: {regime_analysis['confidence']*100:.0f}%")
        info(f"📰 뉴스 중요도: {self.news_urgency:.1f}/10")
        info(f"🎯 의사결정: {self.decision_guide}")
        info(f"📈 현물 전략: {', '.join(self.active_strategies['spot']) or '없음'}")
        info(f"📉 선물 전략: {', '.join(self.active_strategies['futures']) or '없음'}")
        info("="*60 + "\n")

        return {
            'regime': self.current_regime,
            'confidence': regime_analysis['confidence'],
            'decision_guide': self.decision_guide,
            'news_urgency': self.news_urgency,
            'news_sentiment': regime_analysis.get('news_sentiment', 'NEUTRAL'),
            'strategies': self.active_strategies.copy(),
            'trading_allowed': True,
            'analysis': regime_analysis
        }

    def _analyze_market_regime(self, market_data, include_news=True):
        """시장 국면 분석 (기술 + 뉴스 + AI 토론)"""

        # 1. 기술적 분석 (항상 실행)
        technical_result = self._technical_analysis(market_data['df'])

        # 2. AI 분석 시도 (뉴스 + 동적 토론)
        ai_result = None
        if self.ai_enabled and self.ai_available:
            # 🔥 NEW: 30분마다 AI 동적 토론
            if self.should_run_debate():
                ai_result = self._run_ai_debate(market_data, include_news)
                self.last_debate_time = datetime.now()
            else:
                # 이전 결과 사용 + 빠른 분석
                ai_result = self._try_ai_analysis(market_data, include_news)

                if self.last_debate_time:
                    elapsed = datetime.now() - self.last_debate_time
                    remaining = self.debate_config['interval'] - elapsed
                    info(f"⏰ 다음 토론까지: {remaining.seconds // 60}분 {remaining.seconds % 60}초")

            if ai_result:
                self.ai_failure_count = 0
            else:
                self.ai_failure_count += 1

                if self.ai_failure_count >= 3:
                    self.ai_available = False
                    warning("⚠️ AI 연속 실패 - Fallback 모드 전환")

        # 3. 종합 판단
        if ai_result and technical_result:
            # AI + 기술적 분석 결합
            return self._combine_analysis(ai_result, technical_result)
        elif technical_result:
            # 기술적 분석만
            return technical_result
        else:
            # 최악의 경우
            return {
                'regime': MarketRegime.UNKNOWN,
                'confidence': 0.3,
                'decision_guide': 'BALANCED',
                'news_urgency': 5.0,
                'source': 'none'
            }

    def _run_ai_debate(self, market_data, include_news=True):
        """
        🔥 NEW: AI 동적 토론 실행 (30분마다)

        - 3개 AI 참여 (Claude, GPT, Gemini)
        - 5라운드 압축 토론
        - 자동 약어 진화
        """
        info("🗣️ AI 동적 토론 시작 (30분 주기)\n")

        try:
            # 동적 진화 토론 실행
            result = start_dynamic_debate(
                topic=f"{market_data.get('coin', 'BTC')} 시장 분석",
                market_data=market_data,
                num_rounds=self.debate_config['rounds']
            )

            # 결과 변환
            consensus = result['consensus']
            regime_str = consensus['regime']

            regime_map = {
                'STRONG_UPTREND': MarketRegime.STRONG_UPTREND,
                'WEAK_UPTREND': MarketRegime.WEAK_UPTREND,
                'SIDEWAYS': MarketRegime.SIDEWAYS,
                'WEAK_DOWNTREND': MarketRegime.WEAK_DOWNTREND,
                'STRONG_DOWNTREND': MarketRegime.STRONG_DOWNTREND
            }

            regime = regime_map.get(regime_str, MarketRegime.UNKNOWN)

            info(f"\n✅ AI 합의: {regime.value}")
            info(f"   합의율: {consensus['agreement_rate']*100:.1f}%")
            info(f"   신뢰도: {consensus['avg_confidence']*100:.1f}%")

            # 진화 발생 시 알림
            if result['evolutions']:
                info(f"\n🧬 프로토콜 진화 발생!")
                for evo in result['evolutions']:
                    info(f"   v{evo['version']}: {evo['abbr']} = {evo['meaning']}")

            return {
                'regime': regime,
                'confidence': consensus['avg_confidence'],
                'agreement_rate': consensus['agreement_rate'],
                'protocol_version': result['protocol_version'],
                'evolutions': len(result['evolutions']),
                'decision_guide': 'BALANCED',  # 토론은 균형적
                'news_urgency': 5.0,
                'source': 'ai_debate'
            }

        except Exception as e:
            warning(f"⚠️ AI 토론 실패: {e}")
            return None

    def _technical_analysis(self, df):
        """기술적 분석"""
        try:
            result = technical_analyzer.analyze(df)

            if not result:
                return None

            # 점수를 시장 국면으로 변환
            score = result['score']

            if score >= 3:
                regime = MarketRegime.STRONG_UPTREND
                confidence = 0.8
            elif score >= 1.5:
                regime = MarketRegime.WEAK_UPTREND
                confidence = 0.7
            elif score <= -3:
                regime = MarketRegime.STRONG_DOWNTREND
                confidence = 0.8
            elif score <= -1.5:
                regime = MarketRegime.WEAK_DOWNTREND
                confidence = 0.7
            else:
                regime = MarketRegime.SIDEWAYS
                confidence = 0.6

            info(f"📊 기술적 분석: {regime.value} (점수: {score:+.2f})")

            return {
                'regime': regime,
                'confidence': confidence,
                'score': score,
                'decision_guide': 'CHART_PRIORITY',  # 기술적 분석만 있으면 차트 우선
                'news_urgency': 0.0,
                'source': 'technical'
            }

        except Exception as e:
            error(f"❌ 기술적 분석 오류: {e}")
            return None

    def _try_ai_analysis(self, market_data, include_news=True):
        """AI 분석 시도 (뉴스 포함, 빠른 분석)"""
        try:
            # AI 분석 (뉴스 포함)
            result = multi_ai.analyze_market_regime(market_data, include_news=include_news)

            if result:
                regime_str = result['regime']
                regime_map = {
                    'STRONG_UPTREND': MarketRegime.STRONG_UPTREND,
                    'WEAK_UPTREND': MarketRegime.WEAK_UPTREND,
                    'SIDEWAYS': MarketRegime.SIDEWAYS,
                    'WEAK_DOWNTREND': MarketRegime.WEAK_DOWNTREND,
                    'STRONG_DOWNTREND': MarketRegime.STRONG_DOWNTREND
                }

                regime = regime_map.get(regime_str, MarketRegime.UNKNOWN)

                return {
                    'regime': regime,
                    'confidence': result['confidence'],
                    'decision_guide': result.get('decision_guide', 'BALANCED'),
                    'news_urgency': result.get('news_urgency', 5.0),
                    'news_sentiment': result.get('news_sentiment', 'NEUTRAL'),
                    'emergency': result.get('emergency', False),
                    'source': 'ai',
                    'votes': result.get('votes', {})
                }

            return None

        except Exception as e:
            warning(f"⚠️ AI 분석 오류: {e}")
            return None

    def _combine_analysis(self, ai_result, technical_result):
        """AI + 기술적 분석 결합"""

        # 의사결정 가이드 확인
        decision_guide = ai_result.get('decision_guide', 'BALANCED')
        news_urgency = ai_result.get('news_urgency', 5.0)

        info(f"🎯 의사결정 가이드: {decision_guide} (뉴스 중요도: {news_urgency:.1f}/10)")

        # 뉴스 우선 판단
        if decision_guide == 'NEWS_PRIORITY':
            info("📰 뉴스 우선 판단 채택")
            return ai_result

        # 차트 우선 판단
        elif decision_guide == 'CHART_PRIORITY':
            info("📊 차트 우선 판단 채택")
            # 기술적 분석에 뉴스 정보 추가
            technical_result['news_urgency'] = news_urgency
            technical_result['news_sentiment'] = ai_result.get('news_sentiment', 'NEUTRAL')
            technical_result['decision_guide'] = 'CHART_PRIORITY'
            return technical_result

        # 균형 판단
        else:
            # 둘이 일치하면 신뢰도 높음
            if ai_result['regime'] == technical_result['regime']:
                info("✅ AI와 기술적 분석 일치!")
                ai_result['confidence'] = min(ai_result['confidence'] * 1.2, 0.95)
                return ai_result

            # 불일치하면 신뢰도 높은 쪽 선택
            if ai_result['confidence'] > technical_result['confidence']:
                info(f"🤖 AI 분석 채택 (신뢰도: {ai_result['confidence']*100:.0f}%)")
                return ai_result
            else:
                info(f"📊 기술적 분석 채택 (신뢰도: {technical_result['confidence']*100:.0f}%)")
                # 기술적 분석에 뉴스 정보 추가
                technical_result['news_urgency'] = news_urgency
                technical_result['news_sentiment'] = ai_result.get('news_sentiment', 'NEUTRAL')
                technical_result['decision_guide'] = 'BALANCED'
                return technical_result

    def _fallback_analysis(self, market_data):
        """Fallback: 기술적 분석만"""
        result = self._technical_analysis(market_data['df'])

        if result:
            return result

        # 최악의 경우: 횡보로 간주
        warning("⚠️ 모든 분석 실패 - 횡보장으로 간주")
        return {
            'regime': MarketRegime.SIDEWAYS,
            'confidence': 0.4,
            'decision_guide': 'BALANCED',
            'news_urgency': 5.0,
            'source': 'fallback'
        }

    def _adjust_strategies(self, analysis):
        """전략 조정 (의사결정 가이드 반영)"""
        regime = analysis['regime']
        decision_guide = analysis.get('decision_guide', 'BALANCED')
        news_urgency = analysis.get('news_urgency', 5.0)

        info(f"\n🔧 전략 조정: {regime.value}")

        if regime == MarketRegime.STRONG_DOWNTREND:
            # 모든 거래 중단
            self.active_strategies['spot'] = []
            self.active_strategies['futures'] = []
            warning("  ⛔ 모든 거래 중단!")

        elif regime == MarketRegime.WEAK_DOWNTREND:
            # 뉴스 우선 → 더 보수적
            if decision_guide == 'NEWS_PRIORITY':
                self.active_strategies['spot'] = []
                self.active_strategies['futures'] = []
                warning("  📰 뉴스 우선: 모든 거래 중단")
            else:
                # DCA만 활성화 (현물)
                self.active_strategies['spot'] = ['dca']
                self.active_strategies['futures'] = []
                info("  📉 현물: DCA만 | 선물: 중단")

        elif regime == MarketRegime.SIDEWAYS:
            # 그리드, 트레일링 (현물)
            self.active_strategies['spot'] = ['grid', 'trailing']
            self.active_strategies['futures'] = []
            info("  ↔️ 현물: Grid, Trailing | 선물: 중단")

        elif regime == MarketRegime.WEAK_UPTREND:
            # 보수적 전략
            self.active_strategies['spot'] = ['multi_indicator']
            self.active_strategies['futures'] = ['long_short']
            info("  📈 현물: Multi-Indicator | 선물: Long/Short")

        elif regime == MarketRegime.STRONG_UPTREND:
            # 뉴스 우선 → 더 공격적
            if decision_guide == 'NEWS_PRIORITY' and news_urgency >= 7.0:
                self.active_strategies['spot'] = ['multi_indicator', 'trailing', 'breakout']
                self.active_strategies['futures'] = ['long_short']
                info("  📰🚀 뉴스 우선: 공격적 전략!")
            else:
                # 일반 공격적 전략
                self.active_strategies['spot'] = ['multi_indicator', 'trailing']
                self.active_strategies['futures'] = ['long_short']
                info("  🚀 현물: Multi + Trailing | 선물: Long/Short")

        else:  # UNKNOWN
            # 가장 안전한 전략
            self.active_strategies['spot'] = ['trailing']
            self.active_strategies['futures'] = []
            warning("  ❓ 현물: Trailing만 | 선물: 중단")

    def record_trade_result(self, exchange, coin, action, entry_price, exit_price,
                           quantity, pnl, reason, entry_time=None):
        """
        거래 결과 기록 (뉴스 정보 포함)

        Args:
            exchange: 'spot' or 'futures'
            coin: 코인
            action: 'BUY' or 'SELL'
            entry_price: 진입가
            exit_price: 청산가
            quantity: 수량
            pnl: 손익
            reason: 진입/청산 사유
            entry_time: 진입 시간
        """
        performance_tracker.record_actual_trade(
            exchange=exchange,
            coin=coin,
            action=action,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            pnl=pnl,
            reason=reason,
            entry_time=entry_time,
            news_decision=self.decision_guide,
            news_urgency=self.news_urgency
        )

    def get_active_strategies(self, exchange):
        """활성 전략 조회"""
        return self.active_strategies.get(exchange, [])

    def get_current_regime(self):
        """현재 시장 국면"""
        return self.current_regime

    def get_decision_guide(self):
        """현재 의사결정 가이드"""
        return self.decision_guide

    def get_status(self):
        """현재 상태 조회"""
        try:
            stats = get_protocol_stats()
        except:
            stats = {'version': '1.0', 'total_abbreviations': 0, 'total_evolutions': 0}

        return {
            'current_regime': self.current_regime.value if self.current_regime else 'UNKNOWN',
            'decision_guide': self.decision_guide,
            'news_urgency': self.news_urgency,
            'last_debate': self.last_debate_time.isoformat() if self.last_debate_time else None,
            'next_debate': (self.last_debate_time + self.debate_config['interval']).isoformat() if self.last_debate_time else None,
            'protocol_version': stats['version'],
            'total_abbreviations': stats['total_abbreviations'],
            'total_evolutions': stats['total_evolutions']
        }

    def reset_ai(self):
        """AI 시스템 리셋 (수동)"""
        info("🔄 AI 시스템 리셋")
        self.ai_available = True
        self.ai_failure_count = 0


# 전역 인스턴스
master_controller = MasterController()


# 사용 예시
if __name__ == "__main__":
    import pandas as pd
    import numpy as np

    print("🧪 Master Controller 테스트 (뉴스 + AI 동적 토론)\n")

    # 테스트 데이터 생성
    dates = pd.date_range(start='2024-01-01', periods=200, freq='30min')

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

    # 시장 데이터
    market_data = {
        'coin': 'BTC',
        'df': df,
        'price': prices[-1],
        'price_change_24h': 0.05,
        'volume_change': 1.8,
        'rsi': 68,
        'recent_prices': list(prices[-20:])
    }

    # 분석 실행 (뉴스 + AI 토론 포함)
    result = master_controller.analyze_and_adjust(market_data, include_news=True)

    print("\n" + "="*60)
    print("📊 마스터 컨트롤러 결과")
    print("="*60)
    print(f"\n시장 국면: {result['regime'].value}")
    print(f"신뢰도: {result['confidence']*100:.0f}%")
    print(f"뉴스 중요도: {result.get('news_urgency', 0):.1f}/10")
    print(f"의사결정: {result.get('decision_guide', 'N/A')}")
    print(f"뉴스 감성: {result.get('news_sentiment', 'N/A')}")
    print(f"거래 가능: {'✅' if result['trading_allowed'] else '❌'}")

    print(f"\n📈 활성 전략:")
    print(f"  현물: {', '.join(result['strategies']['spot']) or '없음'}")
    print(f"  선물: {', '.join(result['strategies']['futures']) or '없음'}")

    # 현재 상태
    print(f"\n📊 시스템 상태:")
    status = master_controller.get_status()
    print(f"  프로토콜: v{status['protocol_version']}")
    print(f"  약어 수: {status['total_abbreviations']}개")
    print(f"  진화 횟수: {status['total_evolutions']}회")

    # 거래 결과 기록 예시
    print("\n📝 거래 결과 기록 테스트:")
    master_controller.record_trade_result(
        exchange='spot',
        coin='KRW-BTC',
        action='BUY',
        entry_price=95000000,
        exit_price=97000000,
        quantity=0.001,
        pnl=50000,
        reason='Multi-Indicator'
    )

    print("\n✅ 테스트 완료!")