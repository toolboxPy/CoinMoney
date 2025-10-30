"""
AI 토론 전용 분석 시스템 (v2.0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
기존 투표 제거, 모든 판단을 토론으로 통합
10분마다 2라운드 토론으로 뉴스 + 차트 종합 판단

특징:
1. 투표 시스템 제거 (always debate!)
2. 10분 간격 2라운드 토론
3. 뉴스 + 차트 통합 분석
4. 압축 프로토콜 적극 활용
5. 조건부 간격 조정 옵션

비용: ~$263/월 (10분 간격 기준)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import info, warning, error, ai_log
from config.master_config import AI_CONFIG
from ai.protocol_pruning import protocol_pruner

# API 클라이언트
try:
    from anthropic import Anthropic
    claude_client = Anthropic(api_key=os.getenv('CLAUDE_API_KEY'))
    CLAUDE_AVAILABLE = True
except:
    CLAUDE_AVAILABLE = False

try:
    from openai import OpenAI
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    OPENAI_AVAILABLE = True
except:
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    gemini_model = genai.GenerativeModel('gemini-1.5-pro')
    GEMINI_AVAILABLE = True
except:
    GEMINI_AVAILABLE = False

# 뉴스 수집기
try:
    from utils.news_analyzer import NewsCollector
    news_collector = NewsCollector()
    NEWS_AVAILABLE = bool(os.getenv('NEWS_API_KEY'))
except:
    NEWS_AVAILABLE = False

# 차트 포맷터
try:
    from utils.chart_formatter import ChartFormatter
    chart_formatter = ChartFormatter()
    CHART_FORMATTER_AVAILABLE = True
except:
    CHART_FORMATTER_AVAILABLE = False


class AIDebateSystem:
    """AI 토론 전용 분석 시스템"""
    
    def __init__(self):
        self.debate_config = {
            'interval': 600,  # 10분 (초 단위)
            'rounds': 2,
            'min_agreement': 0.7,
            'compression': True,
            'adaptive_interval': True  # 조건부 간격 조정
        }
        
        self.last_debate_time = None
        self.debate_count = 0
        
        # AI 가용성 체크
        self.available_ais = []
        if CLAUDE_AVAILABLE:
            self.available_ais.append('claude')
        if OPENAI_AVAILABLE:
            self.available_ais.append('openai')
        if GEMINI_AVAILABLE:
            self.available_ais.append('gemini')
        
        info(f"🤖 AI 토론 시스템 v2.0 초기화")
        info(f"  사용 가능 AI: {', '.join(self.available_ais)}")
        info(f"  기본 주기: {self.debate_config['interval']//60}분")
        info(f"  라운드 수: {self.debate_config['rounds']}")
        info(f"  뉴스 수집: {'✅' if NEWS_AVAILABLE else '❌'}")
        info(f"  차트 포맷터: {'✅' if CHART_FORMATTER_AVAILABLE else '❌'}")
    
    def should_run_debate(self, market_condition=None):
        """토론 실행 여부 판단 (간격 체크)"""
        if self.last_debate_time is None:
            return True
        
        # 조건부 간격 조정
        if self.debate_config['adaptive_interval'] and market_condition:
            interval = self._get_adaptive_interval(market_condition)
        else:
            interval = self.debate_config['interval']
        
        elapsed = (datetime.now() - self.last_debate_time).seconds
        return elapsed >= interval
    
    def _get_adaptive_interval(self, market_condition):
        """상황별 토론 주기 조정"""
        news_urgency = market_condition.get('news_urgency', 5.0)
        volatility = market_condition.get('volatility', 0)
        emergency = market_condition.get('emergency', False)
        
        # 긴급: 3분
        if emergency or news_urgency >= 9.0:
            return 180
        
        # 매우 중요: 5분
        elif news_urgency >= 7.0 or volatility >= 5:
            return 300
        
        # 중요: 7분
        elif news_urgency >= 6.0 or volatility >= 3:
            return 420
        
        # 평상시: 15분
        else:
            return 900
    
    def analyze(self, market_data, include_news=True):
        """
        AI 토론 기반 시장 분석
        
        Args:
            market_data: {
                'coin': 'BTC',
                'df': DataFrame,  # OHLCV 데이터
                'price': 95000000,
                'technical': {...}  # 기술적 분석 결과
            }
            include_news: 뉴스 포함 여부
        
        Returns:
            dict: {
                'regime': 'STRONG_UPTREND',
                'confidence': 0.85,
                'news_sentiment': 'BULLISH',
                'news_urgency': 7.5,
                'decision_guide': 'BALANCED',
                'reasoning': '...',
                'debate_summary': [...]
            }
        """
        if len(self.available_ais) < 2:
            error("❌ 최소 2개 AI 필요 (토론 불가)")
            return None
        
        info(f"\n{'='*60}")
        info(f"🎭 AI 토론 분석 시작 (Round {self.debate_count + 1})")
        info(f"{'='*60}")
        
        # 1. 뉴스 수집
        news_list = []
        if include_news and NEWS_AVAILABLE:
            try:
                info("📰 뉴스 수집 중...")
                news_list = news_collector.fetch_crypto_news(hours=24, max_results=10)
                if news_list:
                    info(f"  ✅ {len(news_list)}개 수집")
            except Exception as e:
                warning(f"  ⚠️ 뉴스 수집 실패: {e}")
        
        # 2. 차트 텍스트화
        chart_description = ""
        if CHART_FORMATTER_AVAILABLE and 'df' in market_data:
            try:
                chart_description = chart_formatter.describe_candle_pattern(
                    market_data['df'], 
                    count=20
                )
            except Exception as e:
                warning(f"  ⚠️ 차트 포맷 실패: {e}")
        
        # 3. 초기 프롬프트 생성
        initial_prompt = self._create_initial_prompt(
            market_data, 
            news_list, 
            chart_description
        )
        
        # 4. 토론 실행
        debate_result = self._run_debate(initial_prompt)
        
        if not debate_result:
            error("❌ 토론 실패")
            return None
        
        # 5. 결과 업데이트
        self.last_debate_time = datetime.now()
        self.debate_count += 1
        
        info(f"{'='*60}")
        info(f"✅ 토론 완료!")
        info(f"  최종 판단: {debate_result['regime']}")
        info(f"  신뢰도: {debate_result['confidence']*100:.0f}%")
        info(f"  뉴스 중요도: {debate_result['news_urgency']:.1f}/10")
        info(f"  의사결정: {debate_result['decision_guide']}")
        info(f"{'='*60}\n")
        
        return debate_result
    
    def _create_initial_prompt(self, market_data, news_list, chart_description):
        """초기 토론 프롬프트 생성"""
        coin = market_data.get('coin', 'BTC')
        price = market_data.get('price', 0)
        technical = market_data.get('technical', {})
        
        prompt = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 AI 토론: {coin} 시장 분석
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 기본 정보
코인: {coin}
현재가: {price:,.0f}원

"""
        
        # 차트 분석 추가
        if chart_description:
            prompt += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 차트 분석
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{chart_description}

"""
        
        # 기술적 지표 추가
        if technical:
            prompt += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 기술적 지표
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RSI: {technical.get('rsi', {}).get('value', 'N/A')}
MACD: {technical.get('macd', {}).get('signal', 'N/A')}
볼린저: {technical.get('bollinger', {}).get('position', 'N/A')}
이동평균: {technical.get('ma', {}).get('trend', 'N/A')}
거래량: {technical.get('volume', {}).get('status', 'N/A')}
종합 점수: {technical.get('score', 0):.1f}/5

"""
        
        # 뉴스 추가
        if news_list:
            news_text = news_collector.format_news_for_ai(news_list, max_count=10)
            prompt += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📰 최근 뉴스 ({len(news_list)}개)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{news_text}

"""
        
        # 토론 가이드
        prompt += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎭 토론 가이드
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
위 정보를 바탕으로 다음을 판단해주세요:

1️⃣ 시장 국면 (5개 중 선택):
  - STRONG_UPTREND (강한 상승장)
  - WEAK_UPTREND (약한 상승장)
  - SIDEWAYS (횡보장)
  - WEAK_DOWNTREND (약한 하락장)
  - STRONG_DOWNTREND (강한 하락장)

2️⃣ 뉴스 감성:
  - BULLISH (상승 재료)
  - BEARISH (하락 재료)
  - NEUTRAL (중립)
  - EMERGENCY (긴급 대응 필요)

3️⃣ 뉴스 중요도 (0~10점):
  - 0~3점: 영향 미미
  - 4~6점: 중간 영향
  - 7~10점: 결정적 영향

4️⃣ 판단 근거:
  - 차트가 말하는 것
  - 뉴스가 말하는 것
  - 최종 의견 및 추천 행동

응답 형식 (JSON):
{
  "regime": "STRONG_UPTREND",
  "confidence": 0.85,
  "news_sentiment": "BULLISH",
  "news_urgency": 7.5,
  "reasoning": "차트는 강한 상승 추세이며, 뉴스도 긍정적. 진입 추천."
}
"""
        return prompt
    
    def _run_debate(self, initial_prompt):
        """토론 실행"""
        rounds = self.debate_config['rounds']
        compression = self.debate_config['compression']
        
        # 초기 응답 수집
        responses = {}
        for ai_name in self.available_ais:
            response = self._ask_ai(ai_name, initial_prompt)
            if response:
                responses[ai_name] = response
                info(f"  {ai_name}: {response['regime']} ({response['confidence']*100:.0f}%)")
        
        if len(responses) < 2:
            error("  ❌ 응답 수집 실패")
            return None
        
        debate_history = [responses]
        
        # 2라운드 토론
        for round_num in range(2, rounds + 1):
            info(f"\n🔄 Round {round_num}")
            
            # 다른 AI 의견 요약
            others_opinions = self._summarize_opinions(responses, compression)
            
            # 재토론 프롬프트
            debate_prompt = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 Round {round_num} - 다른 AI의 의견
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{others_opinions}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 재검토 요청
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
다른 AI의 의견을 고려하여:
1. 당신의 의견을 유지하거나 수정하세요
2. 근거를 보강하거나 반박하세요
3. 최종 판단을 내려주세요

응답 형식 (JSON):
{{
  "regime": "...",
  "confidence": 0.0~1.0,
  "news_sentiment": "...",
  "news_urgency": 0~10,
  "reasoning": "...",
  "changed": true/false
}}
"""
            
            # 재응답 수집
            new_responses = {}
            for ai_name in responses.keys():
                response = self._ask_ai(ai_name, debate_prompt)
                if response:
                    new_responses[ai_name] = response
                    
                    # 의견 변경 확인
                    old_regime = responses[ai_name]['regime']
                    new_regime = response['regime']
                    if old_regime != new_regime:
                        info(f"  💡 {ai_name}: {old_regime} → {new_regime}")
                    else:
                        info(f"  {ai_name}: {new_regime} (유지)")
            
            responses = new_responses
            debate_history.append(responses)
            
            # 합의 체크
            agreement = self._check_agreement(responses)
            if agreement >= self.debate_config['min_agreement']:
                info(f"  ✅ 합의 도달! (동의율: {agreement*100:.0f}%)")
                break
        
        # 최종 결과 도출
        final_result = self._aggregate_results(responses, debate_history)
        return final_result
    
    def _ask_ai(self, ai_name, prompt):
        """개별 AI에게 질문"""
        try:
            if ai_name == 'claude' and CLAUDE_AVAILABLE:
                response = claude_client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.content[0].text
            
            elif ai_name == 'openai' and OPENAI_AVAILABLE:
                response = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000
                )
                text = response.choices[0].message.content
            
            elif ai_name == 'gemini' and GEMINI_AVAILABLE:
                response = gemini_model.generate_content(prompt)
                text = response.text
            
            else:
                return None
            
            # JSON 파싱
            import json
            import re
            
            # JSON 블록 추출
            json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    'regime': data.get('regime', 'SIDEWAYS'),
                    'confidence': float(data.get('confidence', 0.5)),
                    'news_sentiment': data.get('news_sentiment', 'NEUTRAL'),
                    'news_urgency': float(data.get('news_urgency', 5.0)),
                    'reasoning': data.get('reasoning', ''),
                    'changed': data.get('changed', False)
                }
            
            return None
        
        except Exception as e:
            warning(f"  ⚠️ {ai_name} 오류: {e}")
            return None
    
    def _summarize_opinions(self, responses, use_compression=True):
        """다른 AI 의견 요약"""
        if use_compression:
            # 압축 프로토콜 사용
            protocol = protocol_pruner.get_current_protocol()
            
            summary = []
            for ai_name, response in responses.items():
                abbr_regime = protocol.get('abbreviations', {}).get(
                    response['regime'], 
                    response['regime'][:4]
                )
                abbr_news = protocol.get('abbreviations', {}).get(
                    response['news_sentiment'],
                    response['news_sentiment'][:4]
                )
                
                summary.append(
                    f"{ai_name}: {abbr_regime} ({response['confidence']:.0%}), "
                    f"뉴스 {abbr_news} ({response['news_urgency']:.1f}점)"
                )
            
            return "\n".join(summary)
        
        else:
            # 일반 요약
            summary = []
            for ai_name, response in responses.items():
                summary.append(
                    f"{ai_name}:\n"
                    f"  시장: {response['regime']} (신뢰도: {response['confidence']*100:.0f}%)\n"
                    f"  뉴스: {response['news_sentiment']} (중요도: {response['news_urgency']:.1f}/10)\n"
                    f"  근거: {response['reasoning'][:100]}..."
                )
            
            return "\n\n".join(summary)
    
    def _check_agreement(self, responses):
        """합의 수준 체크"""
        if len(responses) < 2:
            return 0.0
        
        # 가장 많이 선택된 국면
        regime_votes = {}
        for response in responses.values():
            regime = response['regime']
            regime_votes[regime] = regime_votes.get(regime, 0) + 1
        
        max_votes = max(regime_votes.values())
        agreement = max_votes / len(responses)
        
        return agreement
    
    def _aggregate_results(self, final_responses, debate_history):
        """최종 결과 집계"""
        # 다수결 + 신뢰도 가중평균
        regime_scores = {}
        news_sentiment_votes = {}
        urgency_sum = 0
        confidence_sum = 0
        
        for ai_name, response in final_responses.items():
            regime = response['regime']
            confidence = response['confidence']
            
            # 시장 국면 (신뢰도 가중)
            regime_scores[regime] = regime_scores.get(regime, 0) + confidence
            
            # 뉴스 감성
            news = response['news_sentiment']
            news_sentiment_votes[news] = news_sentiment_votes.get(news, 0) + 1
            
            # 평균 계산용
            urgency_sum += response['news_urgency']
            confidence_sum += confidence
        
        # 최다 득표 국면
        winner_regime = max(regime_scores.items(), key=lambda x: x[1])
        avg_confidence = confidence_sum / len(final_responses)
        
        # 최다 득표 뉴스 감성
        winner_news = max(news_sentiment_votes.items(), key=lambda x: x[1])
        
        # 평균 뉴스 중요도
        avg_urgency = urgency_sum / len(final_responses)
        
        # 의사결정 가이드
        if avg_urgency >= 7.0:
            decision_guide = 'NEWS_PRIORITY'
        elif avg_urgency <= 3.0:
            decision_guide = 'CHART_PRIORITY'
        else:
            decision_guide = 'BALANCED'
        
        # 토론 요약
        debate_summary = []
        for round_num, round_responses in enumerate(debate_history, 1):
            round_summary = f"Round {round_num}: "
            regimes = [r['regime'] for r in round_responses.values()]
            round_summary += ", ".join(regimes)
            debate_summary.append(round_summary)
        
        return {
            'regime': winner_regime[0],
            'confidence': avg_confidence,
            'news_sentiment': winner_news[0],
            'news_urgency': avg_urgency,
            'decision_guide': decision_guide,
            'reasoning': self._compile_reasoning(final_responses),
            'debate_summary': debate_summary,
            'rounds_count': len(debate_history),
            'final_agreement': self._check_agreement(final_responses)
        }
    
    def _compile_reasoning(self, responses):
        """판단 근거 종합"""
        reasonings = []
        for ai_name, response in responses.items():
            if response.get('reasoning'):
                reasonings.append(f"[{ai_name}] {response['reasoning']}")
        
        return " | ".join(reasonings)


# 전역 인스턴스
debate_system = AIDebateSystem()


# 테스트 코드
if __name__ == "__main__":
    print("🧪 AI 토론 시스템 v2.0 테스트\n")
    
    # 테스트 데이터
    import pandas as pd
    
    test_data = {
        'coin': 'BTC',
        'price': 95000000,
        'df': pd.DataFrame({
            'open': [94000000] * 20,
            'high': [95000000] * 20,
            'low': [93000000] * 20,
            'close': [94500000] * 20,
            'volume': [1000] * 20
        }),
        'technical': {
            'rsi': {'value': 68, 'signal': 'NEUTRAL'},
            'macd': {'signal': 'BULLISH'},
            'bollinger': {'position': 0.6},
            'ma': {'trend': 'UPTREND'},
            'volume': {'status': 'NORMAL'},
            'score': 2.5
        }
    }
    
    # 토론 분석 실행
    result = debate_system.analyze(test_data, include_news=True)
    
    if result:
        print("\n" + "="*60)
        print("✅ AI 토론 완료!")
        print("="*60)
        print(f"📊 시장 국면: {result['regime']}")
        print(f"💪 신뢰도: {result['confidence']*100:.0f}%")
        print(f"📰 뉴스 감성: {result['news_sentiment']}")
        print(f"📈 뉴스 중요도: {result['news_urgency']:.1f}/10")
        print(f"🎯 의사결정: {result['decision_guide']}")
        print(f"🔄 토론 라운드: {result['rounds_count']}")
        print(f"🤝 최종 합의도: {result['final_agreement']*100:.0f}%")
        print(f"\n💭 판단 근거:\n{result['reasoning']}")
        print(f"\n📜 토론 과정:")
        for summary in result['debate_summary']:
            print(f"  {summary}")
    else:
        print("\n❌ 토론 실패")