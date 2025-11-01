"""
Google Gemini 2.5 Pro 클라이언트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Claude, OpenAI와 완전히 동일한 방식!
"""
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from google import genai
from google.genai import types
from google.genai import errors as genai_errors
import json
from ai.base_client import BaseAIClient
from ai.protocols.trading_protocol import trading_protocol
from utils.logger import info, warning, error


class GeminiClient(BaseAIClient):
    """Google Gemini 2.5 Pro 클라이언트"""

    def __init__(self, api_key):
        super().__init__(api_key, "gemini-2.5-pro")

        # Gemini 클라이언트
        self.client = genai.Client(api_key=api_key)

        # 가격 (100만 토큰당 USD)
        self.input_price_per_mtok = 1.25
        self.output_price_per_mtok = 10.0

        if self.available:
            info("✅ Gemini 2.5 Pro 초기화 완료")

    def send_message(self, user_message, system_prompt=None, **kwargs):
        """메시지 전송"""
        if not self.available:
            return {'success': False, 'error': 'No API key'}

        try:
            # 시스템 프롬프트 자동
            if system_prompt is None:
                system_prompt = trading_protocol.get_ultra_compact_prompt()

            info(f"📤 Gemini 호출 (~{len(user_message)} chars, {len(trading_protocol.DYNAMIC_ABBREVIATIONS)} 동적약어)")

            # API 호출
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=kwargs.get('temperature', 0.7),
                    max_output_tokens=kwargs.get('max_tokens', 2000)
                )
            )

            # 🔥 응답 체크
            if not response or not response.text:
                error("❌ Gemini 응답 없음")
                return {'success': False, 'error': 'No response'}

            # 응답 추출
            text = response.text

            # 🔥 동적 약어 자동 처리 (text가 있을 때만)
            if text:
                self._process_suggested_abbreviations(text)

            # 🔥 사용량 안전하게 추출
            try:
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0
            except AttributeError:
                # usage_metadata가 없으면 추정
                input_tokens = len(system_prompt.split()) + len(user_message.split())
                output_tokens = len(text.split())
                warning(f"⚠️ 토큰 사용량 추정: {input_tokens}→{output_tokens}")

            self.update_usage(input_tokens, output_tokens)
            cost = self.calculate_cost(input_tokens, output_tokens)

            info(f"✅ Gemini 완료 | {input_tokens}→{output_tokens} tokens | ${cost:.4f}")

            return {
                'success': True,
                'response': text,
                'usage': {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens
                },
                'model': self.model_name,
                'cost_usd': cost,
                'cost_krw': int(cost * 1400)
            }

        except Exception as e:
            error(f"❌ Gemini 오류: {e}")
            import traceback
            error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    def _process_suggested_abbreviations(self, response_text):
        """약어 제안 자동 처리"""
        try:
            # 🔥 None 체크
            if not response_text:
                return

            json_text = response_text.strip()

            if '```json' in json_text:
                json_text = json_text.split('```json')[1].split('```')[0]
            elif '```' in json_text:
                json_text = json_text.split('```')[1].split('```')[0]

            if '{' in json_text:
                start = json_text.find('{')
                end = json_text.rfind('}') + 1
                json_text = json_text[start:end]

            data = json.loads(json_text)

            suggestions = data.get('suggested_abbreviations', [])

            if not suggestions:
                return

            info(f"🧬 약어 제안 {len(suggestions)}개!")

            for suggestion in suggestions:
                abbr = suggestion.get('abbr')
                meaning = suggestion.get('meaning')
                reason = suggestion.get('reason', 'AI suggested')

                if abbr and meaning:
                    success = trading_protocol.add_abbreviation(
                        abbr=abbr,
                        meaning=meaning,
                        reason=reason,
                        ai_name=self.model_name
                    )

                    if success:
                        info(f"  ✅ {abbr} = {meaning}")

        except json.JSONDecodeError:
            pass
        except Exception as e:
            warning(f"⚠️ 약어 처리 오류: {e}")

    def _process_suggested_abbreviations(self, response_text):
        """약어 제안 자동 처리"""
        try:
            json_text = response_text.strip()

            if '```json' in json_text:
                json_text = json_text.split('```json')[1].split('```')[0]
            elif '```' in json_text:
                json_text = json_text.split('```')[1].split('```')[0]

            if '{' in json_text:
                start = json_text.find('{')
                end = json_text.rfind('}') + 1
                json_text = json_text[start:end]

            data = json.loads(json_text)

            suggestions = data.get('suggested_abbreviations', [])

            if not suggestions:
                return

            info(f"🧬 약어 제안 {len(suggestions)}개!")

            for suggestion in suggestions:
                abbr = suggestion.get('abbr')
                meaning = suggestion.get('meaning')
                reason = suggestion.get('reason', 'AI suggested')

                if abbr and meaning:
                    success = trading_protocol.add_abbreviation(
                        abbr=abbr,
                        meaning=meaning,
                        reason=reason,
                        ai_name=self.model_name
                    )

                    if success:
                        info(f"  ✅ {abbr} = {meaning}")

        except json.JSONDecodeError:
            pass
        except Exception as e:
            warning(f"⚠️ 약어 처리 오류: {e}")

    def get_remaining_tokens(self):
        """남은 토큰"""
        return {
            'daily_limit': float('inf'),
            'used': self.total_tokens_used,
            'remaining': float('inf')
        }


# 전역 인스턴스
gemini_client = None

def init_gemini_client(api_key):
    """
    Gemini 클라이언트 초기화

    Args:
        api_key: Gemini API 키
    """
    global gemini_client
    gemini_client = GeminiClient(api_key)
    return gemini_client


# 테스트
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.getenv('GEMINI_API_KEY')

    if not api_key:
        print("❌ GEMINI_API_KEY 없음")
        exit(1)

    print("🧪 Gemini Client 테스트\n")

    # 초기화
    client = GeminiClient(api_key)

    # 프롬프트 확인
    print("=" * 60)
    print("📋 시스템 프롬프트 (초압축):")
    print("=" * 60)
    print(trading_protocol.get_ultra_compact_prompt())
    print("\n" + "=" * 60)

    # 테스트 메시지
    result = client.send_message("""
코인: BTC
현재가: 95,000,000원
24시간: +5.2%
RSI: 68
거래량: +80%

분석하세요.
""")

    if result['success']:
        print(f"\n✅ 성공!")
        print(f"\n📥 응답:\n{result['response']}\n")
        print(f"📊 토큰: {result['usage']['input_tokens']}→{result['usage']['output_tokens']}")
        print(f"💰 비용: ${result['cost_usd']:.4f} ({result['cost_krw']:,}원)")

        stats = client.get_usage_stats()
        print(f"\n📈 누적:")
        print(f"   총 토큰: {stats['total_tokens']}")
        print(f"   총 비용: ${stats['total_cost_usd']:.4f} ({stats['total_cost_krw']:,}원)")
    else:
        print(f"\n❌ 실패: {result.get('error')}")