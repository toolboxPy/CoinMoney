"""
Multi-AI 분석 시스템
Claude + ChatGPT + Gemini 동시 호출 + 뉴스 감성 분석 + 중요도 판단
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
import re
from config.master_config import (
    AI_CONFIG, CLAUDE_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY
)
from utils.logger import info, warning, error, ai_log

# 뉴스 수집기
try:
    from utils.news_analyzer import news_collector
    NEWS_AVAILABLE = True
except ImportError:
    NEWS_AVAILABLE = False
    warning("⚠️ news_analyzer 없음 - 뉴스 분석 비활성화")

# AI 클라이언트 초기화
try:
    import anthropic

    if CLAUDE_API_KEY:
        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        CLAUDE_AVAILABLE = True
    else:
        CLAUDE_AVAILABLE = False
except ImportError:
    CLAUDE_AVAILABLE = False
    warning("⚠️ anthropic 패키지 없음")

try:
    import openai

    if OPENAI_API_KEY:
        openai.api_key = OPENAI_API_KEY
        OPENAI_AVAILABLE = True
    else:
        OPENAI_AVAILABLE = False
except ImportError:
    OPENAI_AVAILABLE = False
    warning("⚠️ openai 패키지 없음")

try:
    import google.generativeai as genai

    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-pro')
        GEMINI_AVAILABLE = True
    else:
        GEMINI_AVAILABLE = False
except ImportError:
    GEMINI_AVAILABLE = False
    warning("⚠️ google-generativeai 패키지 없음")


class MultiAIAnalyzer:
    """3개 AI 동시 분석 + 뉴스 감성 + 중요도 판단"""

    def __init__(self):
        self.claude_available = CLAUDE_AVAILABLE
        self.openai_available = OPENAI_AVAILABLE
        self.gemini_available = GEMINI_AVAILABLE
        self.news_available = NEWS_AVAILABLE

        available = []
        if self.claude_available:
            available.append("Claude")
        if self.openai_available:
            available.append("ChatGPT")
        if self.gemini_available:
            available.append("Gemini")

        info(f"🤖 Multi-AI 초기화: {', '.join(available)}")

        if not available:
            warning("⚠️ 사용 가능한 AI가 없습니다!")

        if self.news_available:
            info("📰 뉴스 분석 활성화 (중요도 판단 포함)")
        else:
            warning("⚠️ 뉴스 분석 비활성화")

    def analyze_market_regime(self, market_data, include_news=True):
        """
        시장 국면 분석 (3개 AI 동시 + 뉴스 + 중요도)

        Args:
            market_data: {
                'coin': 'BTC',
                'price': 95000000,
                'price_change_24h': 0.05,
                'volume_change': 1.5,
                'rsi': 65,
                'recent_prices': [...]
            }
            include_news: 뉴스 포함 여부

        Returns:
            dict: {
                'regime': 'STRONG_UPTREND',
                'confidence': 0.85,
                'news_sentiment': 'BULLISH',
                'news_urgency': 8.5,
                'decision_guide': 'NEWS_PRIORITY',
                'emergency': False,
                'votes': {...}
            }
        """
        info("\n🤖 Multi-AI 시장 분석 시작...")

        # 뉴스 수집 (옵션)
        news_list = []
        if include_news and self.news_available:
            try:
                info("📰 뉴스 수집 중...")
                news_list = news_collector.fetch_crypto_news(hours=24, max_results=10)
                if news_list:
                    info(f"✅ 뉴스 {len(news_list)}개 수집")
                else:
                    warning("⚠️ 수집된 뉴스 없음")
            except Exception as e:
                warning(f"⚠️ 뉴스 수집 실패: {e}")

        # 시장 데이터 + 뉴스 프롬프트
        prompt = self._prepare_market_prompt(market_data, news_list)

        # 3개 AI에게 동시 질문
        results = []

        # Claude
        if self.claude_available:
            claude_result = self._ask_claude(prompt)
            if claude_result:
                results.append(('claude', claude_result))
                ai_log('claude', claude_result['regime'], claude_result['confidence'])

        # ChatGPT
        if self.openai_available:
            openai_result = self._ask_openai(prompt)
            if openai_result:
                results.append(('openai', openai_result))
                ai_log('openai', openai_result['regime'], openai_result['confidence'])

        # Gemini
        if self.gemini_available:
            gemini_result = self._ask_gemini(prompt)
            if gemini_result:
                results.append(('gemini', gemini_result))
                ai_log('gemini', gemini_result['regime'], gemini_result['confidence'])

        # 투표/평균
        if not results:
            error("❌ 모든 AI 실패 - Fallback 필요")
            return None

        final_decision = self._combine_results(results)

        info(f"\n📊 최종 판단: {final_decision['regime']} (신뢰도: {final_decision['confidence']*100:.0f}%)")
        if final_decision.get('news_sentiment'):
            info(f"📰 뉴스 감성: {final_decision['news_sentiment']}")
        if final_decision.get('news_urgency'):
            info(f"📊 뉴스 중요도: {final_decision['news_urgency']:.1f}/10")
            info(f"🎯 의사결정 가이드: {final_decision['decision_guide']}")
        if final_decision.get('emergency'):
            error(f"🚨 긴급 상황 감지!")

        return final_decision

    # 🔥 동기 호출 별칭 (컨트롤러 호환성)
    def analyze_sync(self, coin=None, ticker=None, df=None, news_list=None, **kwargs):
        """
        동기 분석 (컨트롤러 호환 - 모든 파라미터 받음)

        Args:
            coin: 코인 티커 (예: "KRW-BTC")
            ticker: 코인 티커 (예: "KRW-BTC")
            df: OHLCV DataFrame
            news_list: 뉴스 리스트
            **kwargs: 기타 파라미터 (무시)

        Returns:
            dict: 분석 결과
        """
        try:
            # 🔥 coin과 ticker 둘 다 받기 (호환성)
            symbol = coin or ticker

            if not symbol:
                error("❌ coin 또는 ticker 파라미터 필요")
                return None

            # DataFrame에서 시장 데이터 추출
            if df is None or len(df) == 0:
                warning("⚠️ DataFrame 없음")
                return None

            # 최근 데이터
            recent = df.tail(5)
            current_price = float(df['close'].iloc[-1])
            prev_price = float(df['close'].iloc[-2]) if len(df) >= 2 else current_price

            # 가격 변화
            price_change_24h = (current_price - prev_price) / prev_price if prev_price > 0 else 0

            # 거래량 변화
            current_volume = float(df['volume'].iloc[-1])
            prev_volume = float(df['volume'].iloc[-2]) if len(df) >= 2 else current_volume
            volume_change = current_volume / prev_volume if prev_volume > 0 else 1.0

            # RSI (있으면)
            rsi = 50  # 기본값
            if 'rsi' in df.columns:
                rsi = float(df['rsi'].iloc[-1])

            # 시장 데이터 구성
            market_data = {
                'coin': symbol.replace('KRW-', ''),
                'price': current_price,
                'price_change_24h': price_change_24h,
                'volume_change': volume_change,
                'rsi': rsi,
                'recent_prices': df['close'].tail(5).tolist()
            }

            # 뉴스 포함 여부
            include_news = news_list is not None and len(news_list) > 0

            # 기존 analyze_market_regime 호출
            return self.analyze_market_regime(market_data, include_news=include_news)

        except Exception as e:
            error(f"❌ AI 동기 분석 오류: {e}")
            import traceback
            error(traceback.format_exc())
            return None

    def _prepare_market_prompt(self, data, news_list=None):
        """시장 데이터 + 뉴스를 프롬프트로 변환"""

        # 기본 시장 데이터
        prompt = f"""
현재 암호화폐 시장 분석을 요청합니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 시장 데이터
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
코인: {data.get('coin', 'BTC')}
현재가: {data.get('price', 0):,.0f}원
24시간 변화: {data.get('price_change_24h', 0)*100:+.2f}%
거래량 변화: {data.get('volume_change', 1)*100:+.0f}%
RSI: {data.get('rsi', 50):.1f}

최근 가격 추세:
{data.get('recent_prices', [])}
"""

        # 뉴스 추가
        if news_list and self.news_available:
            try:
                news_text = news_collector.format_news_for_ai(news_list, max_count=10)
                prompt += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📰 최근 뉴스 (24시간)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{news_text}
"""
            except Exception as e:
                warning(f"⚠️ 뉴스 포맷 오류: {e}")

        prompt += """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 분석 요청
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
시장 데이터와 뉴스를 종합하여 다음을 판단해주세요:

1. 시장 국면 (다음 중 하나):
   - STRONG_UPTREND: 강한 상승장 (공격적 매수)
   - WEAK_UPTREND: 약한 상승장 (보수적 매수)
   - SIDEWAYS: 횡보장 (관망 또는 그리드)
   - WEAK_DOWNTREND: 약한 하락장 (DCA 또는 관망)
   - STRONG_DOWNTREND: 강한 하락장 (모든 거래 중단)

2. 뉴스 감성:
   - BULLISH: 긍정적 (상승 재료)
   - BEARISH: 부정적 (하락 재료)
   - NEUTRAL: 중립
   - EMERGENCY: 긴급 (해킹, 붕괴, 규제 등 즉시 대응 필요)

3. 뉴스 중요도 (0~10 점수):
   - 0-3점: 낮음 → 차트 기술적 분석 우선 판단
   - 4-6점: 중간 → 차트와 뉴스 균형 판단
   - 7-10점: 높음 → 뉴스 우선 판단
   
   중요도 산정 기준:
   * 시장 충격도 (해킹, 규제, 대규모 투자 등)
   * 신뢰도 (공식 발표, 주요 언론 등)
   * 시급성 (즉시 대응 필요 여부)

반드시 JSON 형식으로만 답변하세요:
{
    "regime": "STRONG_UPTREND",
    "confidence": 0.85,
    "news_sentiment": "BULLISH",
    "news_urgency": 8.5,
    "emergency": false,
    "reason": "시장과 뉴스 종합 판단 이유를 한 문장으로"
}
"""

        return prompt

    def _ask_claude(self, prompt):
        """Claude에게 질문"""
        try:
            response = claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                timeout=AI_CONFIG['timeout'],
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            content = response.content[0].text
            return self._parse_ai_response(content)

        except Exception as e:
            warning(f"❌ Claude 오류: {e}")
            return None

    def _ask_openai(self, prompt):
        """ChatGPT에게 질문"""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional crypto market analyst."},
                    {"role": "user", "content": prompt}
                ],
                timeout=AI_CONFIG['timeout']
            )

            content = response.choices[0].message.content
            return self._parse_ai_response(content)

        except Exception as e:
            warning(f"❌ OpenAI 오류: {e}")
            return None

    def _ask_gemini(self, prompt):
        """Gemini에게 질문"""
        try:
            response = gemini_model.generate_content(prompt)
            content = response.text
            return self._parse_ai_response(content)

        except Exception as e:
            warning(f"❌ Gemini 오류: {e}")
            return None

    def _parse_ai_response(self, text):
        """AI 응답 파싱 (뉴스 중요도 포함)"""
        try:
            # JSON 추출 - 더 강력한 파싱
            content = text.strip()

            # 마크다운 코드 블록 제거
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()

            # { } 사이만 추출
            if '{' in content and '}' in content:
                start = content.find('{')
                end = content.rfind('}') + 1
                content = content[start:end]

            data = json.loads(content)

            return {
                'regime': data.get('regime', 'UNKNOWN'),
                'confidence': float(data.get('confidence', 0.5)),
                'news_sentiment': data.get('news_sentiment', 'NEUTRAL'),
                'news_urgency': float(data.get('news_urgency', 5.0)),  # 추가!
                'emergency': bool(data.get('emergency', False)),
                'reason': data.get('reason', '')
            }

        except Exception as e:
            warning(f"⚠️ 파싱 오류: {e}")
            return None

    def _combine_results(self, results):
        """
        결과 통합 (투표 또는 평균) + 뉴스 감성 + 중요도

        Args:
            results: [(ai_name, result), ...]
        """
        method = AI_CONFIG['voting_method']

        if method == 'majority':
            # 다수결
            votes = {}
            confidence_sum = {}
            news_votes = {}
            urgency_sum = 0
            emergency_count = 0

            for ai_name, result in results:
                # 시장 국면
                regime = result['regime']
                votes[regime] = votes.get(regime, 0) + 1
                confidence_sum[regime] = confidence_sum.get(regime, 0) + result['confidence']

                # 뉴스 감성
                news_sentiment = result.get('news_sentiment', 'NEUTRAL')
                news_votes[news_sentiment] = news_votes.get(news_sentiment, 0) + 1

                # 뉴스 중요도
                urgency_sum += result.get('news_urgency', 5.0)

                # 긴급 상황
                if result.get('emergency', False):
                    emergency_count += 1

            # 최다 득표 - 시장 국면
            winner = max(votes.items(), key=lambda x: x[1])
            regime = winner[0]
            avg_confidence = confidence_sum[regime] / votes[regime]

            # 최다 득표 - 뉴스 감성
            news_winner = max(news_votes.items(), key=lambda x: x[1]) if news_votes else ('NEUTRAL', 0)

            # 평균 뉴스 중요도
            avg_urgency = urgency_sum / len(results)

            # 의사결정 가이드
            if avg_urgency >= 7.0:
                decision_guide = 'NEWS_PRIORITY'
            elif avg_urgency <= 3.0:
                decision_guide = 'CHART_PRIORITY'
            else:
                decision_guide = 'BALANCED'

            # 긴급 (2개 이상 AI가 동의하면 긴급)
            is_emergency = emergency_count >= 2

            return {
                'regime': regime,
                'confidence': avg_confidence,
                'news_sentiment': news_winner[0],
                'news_urgency': avg_urgency,  # 추가!
                'decision_guide': decision_guide,  # 추가!
                'emergency': is_emergency,
                'votes': votes,
                'news_votes': news_votes,
                'method': 'majority',
                'ai_count': len(results)
            }

        elif method == 'weighted':
            # 가중 평균
            weights = AI_CONFIG['weights']

            regime_scores = {}
            news_scores = {}
            urgency_sum = 0
            emergency_score = 0

            for ai_name, result in results:
                weight = weights.get(ai_name, 0.33)

                # 시장 국면
                regime = result['regime']
                confidence = result['confidence']
                score = weight * confidence
                regime_scores[regime] = regime_scores.get(regime, 0) + score

                # 뉴스 감성
                news_sentiment = result.get('news_sentiment', 'NEUTRAL')
                news_scores[news_sentiment] = news_scores.get(news_sentiment, 0) + weight

                # 뉴스 중요도
                urgency_sum += result.get('news_urgency', 5.0) * weight

                # 긴급
                if result.get('emergency', False):
                    emergency_score += weight

            # 최고 점수
            regime_winner = max(regime_scores.items(), key=lambda x: x[1])
            news_winner = max(news_scores.items(), key=lambda x: x[1]) if news_scores else ('NEUTRAL', 0)

            # 가중 평균 중요도
            avg_urgency = urgency_sum

            # 의사결정 가이드
            if avg_urgency >= 7.0:
                decision_guide = 'NEWS_PRIORITY'
            elif avg_urgency <= 3.0:
                decision_guide = 'CHART_PRIORITY'
            else:
                decision_guide = 'BALANCED'

            return {
                'regime': regime_winner[0],
                'confidence': regime_winner[1],
                'news_sentiment': news_winner[0],
                'news_urgency': avg_urgency,  # 추가!
                'decision_guide': decision_guide,  # 추가!
                'emergency': emergency_score > 0.5,
                'scores': regime_scores,
                'news_scores': news_scores,
                'method': 'weighted',
                'ai_count': len(results)
            }

        else:  # average
            # 첫 번째 결과 반환 (임시)
            return results[0][1] if results else None


# 전역 인스턴스
multi_ai = MultiAIAnalyzer()


# 사용 예시
if __name__ == "__main__":
    print("🧪 Multi-AI Analyzer 테스트 (뉴스 중요도 판단)\n")

    # 테스트 데이터
    test_data = {
        'coin': 'BTC',
        'price': 95000000,
        'price_change_24h': 0.05,
        'volume_change': 1.8,
        'rsi': 68,
        'recent_prices': [
            94000000, 94200000, 94500000, 94800000, 95000000
        ]
    }

    print("📊 테스트 시장 데이터:")
    print(f"  코인: {test_data['coin']}")
    print(f"  가격: {test_data['price']:,}원")
    print(f"  24시간: {test_data['price_change_24h']*100:+.2f}%")
    print(f"  거래량: {test_data['volume_change']*100:+.0f}%")
    print(f"  RSI: {test_data['rsi']}")

    # AI 분석 실행 (뉴스 포함)
    result = multi_ai.analyze_market_regime(test_data, include_news=True)

    if result:
        print("\n✅ AI 분석 완료!")
        print(f"  시장 국면: {result['regime']}")
        print(f"  신뢰도: {result['confidence']*100:.0f}%")
        print(f"  뉴스 감성: {result.get('news_sentiment', 'N/A')}")
        print(f"  뉴스 중요도: {result.get('news_urgency', 0):.1f}/10")
        print(f"  의사결정: {result.get('decision_guide', 'N/A')}")
        print(f"  긴급 상황: {'🚨 YES' if result.get('emergency') else '✅ NO'}")
        print(f"  투표 방식: {result.get('method', 'N/A')}")
        print(f"  참여 AI: {result.get('ai_count', 0)}개")

        if 'votes' in result:
            print(f"  시장 투표: {result['votes']}")
        if 'news_votes' in result:
            print(f"  뉴스 투표: {result['news_votes']}")
    else:
        print("\n❌ AI 분석 실패")

    print("\n" + "="*60)
    print("💡 참고:")
    print("  - API 키가 없으면 해당 AI는 작동하지 않습니다")
    print("  - .env 파일에 API 키를 입력하세요")
    print("  - NEWS_API_KEY가 있으면 실시간 뉴스 분석이 추가됩니다")
    print("  - 뉴스 중요도에 따라 차트/뉴스 우선 판단이 자동 결정됩니다")