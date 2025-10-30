"""
마스터 컨트롤러 v3.0 - 이벤트 드리븐 AI 호출
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
시간 기반 → 이벤트 기반 AI 호출

핵심 개념:
1. 매 주기마다 로컬 분석 (기술적 지표, 무료)
2. AI 호출 필요성 점수 계산
3. 임계값 초과 시에만 AI 토론
4. 비용 70~80% 절감

예상 비용: $40~$60/월 (vs $200~$700)
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
    스마트 마스터 컨트롤러 v3.0
    이벤트 드리븐 AI 호출 시스템 적용
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
        
        info("🧠 스마트 마스터 컨트롤러 v3.0 초기화")
        info(f"  AI 시스템: {'✅ 이벤트 드리븐' if self.ai_enabled else '❌ 비활성'}")
        info(f"  로컬 분석: ✅ 항상 실행")
        info(f"  AI 호출: 필요 시에만")
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
        if not global_risk.check_risk_limits():
            error("🚫 리스크 한도 초과")
            return self._create_blocked_result('리스크 한도')
        
        # 2. 로컬 분석 (항상 실행, 무료!)
        local_result = self._local_analysis(market_data)
        self.local_analysis_count += 1
        
        info(f"📊 로컬 분석:")
        info(f"  국면: {local_result['regime']}")
        info(f"  점수: {local_result['score']:.1f}/5")
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
        
        # 5. 전략 조정
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
        result['source'] = 'merged'
        result['local_indicators'] = local_result.get('indicators')
        return result
    
    def _adjust_strategies(self, analysis):
        """전략 조정"""
        regime = analysis.get('regime', 'SIDEWAYS')
        self.current_regime = MarketRegime[regime]
        
        self.confidence = analysis.get('confidence', 0.5)
        self.decision_guide = analysis.get('decision_guide', 'BALANCED')
        self.news_urgency = analysis.get('news_urgency', 0.0)
        
        # 국면별 전략 (기존 로직)
        if regime == 'STRONG_DOWNTREND':
            self.active_strategies['spot'] = []
            self.active_strategies['futures'] = []
        
        elif regime == 'WEAK_DOWNTREND':
            self.active_strategies['spot'] = ['dca']
            self.active_strategies['futures'] = []
        
        elif regime == 'SIDEWAYS':
            self.active_strategies['spot'] = ['grid']
            self.active_strategies['futures'] = ['scalping']
        
        elif regime == 'WEAK_UPTREND':
            self.active_strategies['spot'] = ['multi_indicator']
            self.active_strategies['futures'] = ['long_short']
        
        elif regime == 'STRONG_UPTREND':
            self.active_strategies['spot'] = ['multi_indicator', 'breakout']
            self.active_strategies['futures'] = ['long_short']
        
        # 뉴스 우선이면 보수적 조정
        if self.decision_guide == 'NEWS_PRIORITY' and self.news_urgency >= 8.0:
            self.active_strategies['futures'] = []
            if regime in ['WEAK_UPTREND', 'STRONG_UPTREND']:
                self.active_strategies['spot'] = ['multi_indicator']
            else:
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
        trigger_stats = ai_trigger.get_statistics() if AI_AVAILABLE else {}
        
        return {
            'version': 'v3.0_event_driven',
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
    
    print("🧪 스마트 마스터 컨트롤러 v3.0 테스트\n")
    
    # 테스트 데이터
    test_df = pd.DataFrame({
        'open': [94000000] * 100,
        'high': [95000000] * 100,
        'low': [93000000] * 100,
        'close': [94000000] * 100,
        'volume': [1000] * 100
    })
    
    test_data = {
        'coin': 'BTC',
        'price': 94000000,
        'df': test_df
    }
    
    # 분석 실행 (여러 번)
    for i in range(5):
        print(f"\n{'='*60}")
        print(f"분석 #{i+1}")
        print(f"{'='*60}")
        
        result = smart_controller.analyze_and_adjust(test_data)
        
        print(f"국면: {result['regime'].value}")
        print(f"신뢰도: {result['confidence']*100:.0f}%")
        print(f"방식: {result['source']}")
        
        import time
        time.sleep(2)
    
    # 통계
    print("\n" + "="*60)
    print("📊 통계")
    print("="*60)
    stats = smart_controller.get_statistics()
    print(f"총 분석: {stats['total_analysis']}회")
    print(f"로컬만: {stats['local_only']}회")
    print(f"AI 호출: {stats['ai_calls']}회")
    print(f"AI 호출률: {stats['ai_call_rate']:.1f}%")
    print(f"비용 절감률: {stats['savings_rate']:.1f}%")