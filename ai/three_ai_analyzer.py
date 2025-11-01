"""
3 AI 순차 분석 시스템
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Claude + OpenAI 의견 → Gemini 최종 판단
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from ai.claude_client import init_claude_client
from ai.openai_client import init_openai_client
from ai.gemini_client import init_gemini_client
from utils.logger import info, warning, error
import json


class ThreeAIAnalyzer:
    """3 AI 순차 분석"""

    def __init__(self, claude_key, openai_key, gemini_key):
        """초기화"""
        info("🤖 3 AI 분석 시스템 초기화")

        # 클라이언트 초기화
        self.claude = init_claude_client(claude_key)
        self.openai = init_openai_client(openai_key)
        self.gemini = init_gemini_client(gemini_key)

        # 사용 가능 확인
        self.available = (
                self.claude.available and
                self.openai.available and
                self.gemini.available
        )

        if self.available:
            info("✅ 3 AI 모두 준비 완료!")
        else:
            warning("⚠️ 일부 AI 사용 불가")

    def analyze_market(self, market_data, temperature=0.7):
        """
        시장 분석 (3단계)

        Args:
            market_data: 시장 데이터 (텍스트)
            temperature: 온도 설정

        Returns:
            dict: 최종 분석 결과
        """
        if not self.available:
            return {'success': False, 'error': 'AI not available'}

        info("\n" + "=" * 60)
        info("🔍 3 AI 순차 분석 시작")
        info("=" * 60)

        # Step 1: Claude 의견
        info("\n1️⃣ Claude 의견 수집 중...")
        claude_opinion = self._get_opinion(
            self.claude,
            market_data,
            "Claude",
            temperature
        )

        if not claude_opinion['success']:
            error("❌ Claude 실패")
            return claude_opinion

        # Step 2: OpenAI 의견
        info("\n2️⃣ OpenAI 의견 수집 중...")
        openai_opinion = self._get_opinion(
            self.openai,
            market_data,
            "OpenAI",
            temperature
        )

        if not openai_opinion['success']:
            error("❌ OpenAI 실패")
            return openai_opinion

        # Step 3: Gemini 최종 판단
        info("\n3️⃣ Gemini 최종 판단 중...")
        final_decision = self._get_final_decision(
            market_data,
            claude_opinion['analysis'],
            openai_opinion['analysis'],
            temperature
        )

        if not final_decision['success']:
            error("❌ Gemini 실패")
            return final_decision

        # 결과 통합
        result = {
            'success': True,
            'claude_opinion': claude_opinion['analysis'],
            'openai_opinion': openai_opinion['analysis'],
            'final_decision': final_decision['decision'],
            'total_cost_usd': (
                    claude_opinion.get('cost_usd', 0) +
                    openai_opinion.get('cost_usd', 0) +
                    final_decision.get('cost_usd', 0)
            ),
            'total_cost_krw': (
                    claude_opinion.get('cost_krw', 0) +
                    openai_opinion.get('cost_krw', 0) +
                    final_decision.get('cost_krw', 0)
            )
        }

        info("\n" + "=" * 60)
        info("✅ 3 AI 분석 완료!")
        info(f"💰 총 비용: ${result['total_cost_usd']:.4f} ({result['total_cost_krw']:,}원)")
        info("=" * 60 + "\n")

        return result

    def _get_opinion(self, client, market_data, ai_name, temperature):
        """개별 AI 의견 수집"""
        try:
            result = client.send_message(
                market_data,
                temperature=temperature
            )

            if not result['success']:
                return result

            # JSON 파싱
            analysis = self._parse_json(result['response'])

            if not analysis:
                warning(f"⚠️ {ai_name} JSON 파싱 실패")
                return {'success': False, 'error': 'JSON parse failed'}

            info(f"✅ {ai_name}: {analysis.get('regime', 'N/A')} (신뢰도: {analysis.get('confidence', 0):.2f})")

            return {
                'success': True,
                'analysis': analysis,
                'cost_usd': result.get('cost_usd', 0),
                'cost_krw': result.get('cost_krw', 0)
            }

        except Exception as e:
            error(f"❌ {ai_name} 오류: {e}")
            return {'success': False, 'error': str(e)}

    def _get_final_decision(self, market_data, claude_opinion, openai_opinion, temperature):
        """Gemini 최종 판단"""
        try:
            # 최종 판단용 프롬프트
            prompt = f"""다른 2개 AI의 의견을 참고하여 최종 판단하세요.

[시장 데이터]
{market_data}

[Claude 의견]
{json.dumps(claude_opinion, ensure_ascii=False)}

[OpenAI 의견]
{json.dumps(openai_opinion, ensure_ascii=False)}

위 2개 의견을 종합하여 최종 판단하세요.
- 의견이 일치하면 신뢰도 높게
- 의견이 다르면 근거 강한 쪽 선택
- 필요시 중립적 판단"""

            result = self.gemini.send_message(
                prompt,
                temperature=temperature
            )

            if not result['success']:
                return result

            # JSON 파싱
            decision = self._parse_json(result['response'])

            if not decision:
                warning("⚠️ Gemini JSON 파싱 실패")
                return {'success': False, 'error': 'JSON parse failed'}

            info(f"✅ Gemini 최종: {decision.get('regime', 'N/A')} (신뢰도: {decision.get('confidence', 0):.2f})")

            return {
                'success': True,
                'decision': decision,
                'cost_usd': result.get('cost_usd', 0),
                'cost_krw': result.get('cost_krw', 0)
            }

        except Exception as e:
            error(f"❌ Gemini 오류: {e}")
            return {'success': False, 'error': str(e)}

    def _parse_json(self, text):
        """JSON 파싱"""
        try:
            # 코드 블록 제거
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0]
            elif '```' in text:
                text = text.split('```')[1].split('```')[0]

            # JSON 추출
            if '{' in text:
                start = text.find('{')
                end = text.rfind('}') + 1
                text = text[start:end]

            return json.loads(text)

        except json.JSONDecodeError:
            return None
        except Exception:
            return None


# 전역 인스턴스
three_ai_analyzer = None


def init_three_ai_analyzer(claude_key, openai_key, gemini_key):
    """3 AI 분석기 초기화"""
    global three_ai_analyzer
    three_ai_analyzer = ThreeAIAnalyzer(claude_key, openai_key, gemini_key)
    return three_ai_analyzer


# 테스트
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    claude_key = os.getenv('CLAUDE_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    gemini_key = os.getenv('GEMINI_API_KEY')

    if not all([claude_key, openai_key, gemini_key]):
        print("❌ API 키 없음")
        exit(1)

    print("🧪 3 AI 분석 테스트\n")

    # 초기화
    analyzer = ThreeAIAnalyzer(claude_key, openai_key, gemini_key)

    # 테스트 데이터
    market_data = """
코인: BTC
현재가: 95,000,000원
24시간: +5.2%
RSI: 68
MACD: 골든크로스
거래량: +80%

분석하세요.
"""

    # 분석 실행
    result = analyzer.analyze_market(market_data)

    if result['success']:
        print("\n📊 분석 결과:")
        print("=" * 60)

        print("\n1️⃣ Claude 의견:")
        print(json.dumps(result['claude_opinion'], indent=2, ensure_ascii=False))

        print("\n2️⃣ OpenAI 의견:")
        print(json.dumps(result['openai_opinion'], indent=2, ensure_ascii=False))

        print("\n3️⃣ Gemini 최종 판단:")
        print(json.dumps(result['final_decision'], indent=2, ensure_ascii=False))

        print(f"\n💰 총 비용: ${result['total_cost_usd']:.4f} ({result['total_cost_krw']:,}원)")
    else:
        print(f"\n❌ 실패: {result.get('error')}")