"""
OpenAI GPT-4.1 클라이언트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OpenAI Prompt(정적) + Python(동적 약어)
"""
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from openai import OpenAI
import json
from ai.base_client import BaseAIClient
from ai.protocols.trading_protocol import trading_protocol
from utils.logger import info, warning, error


class OpenAIClient(BaseAIClient):
    """OpenAI GPT-4.1 클라이언트"""

    def __init__(self, api_key, prompt_id, prompt_version="2"):
        super().__init__(api_key, "gpt-4.1")

        # OpenAI 클라이언트
        self.client = OpenAI(api_key=api_key)

        # Prompt ID (OpenAI에 저장된 정적 프롬프트)
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version

        # 가격 (100만 토큰당 USD)
        self.input_price_per_mtok = 1.25
        self.output_price_per_mtok = 10.0

        if self.available:
            info(f"✅ GPT-4.1 초기화 (Prompt: ...{prompt_id[-8:]})")

    def send_message(self, user_message, system_prompt=None, **kwargs):
        """
        메시지 전송

        Args:
            user_message: 사용자 메시지
            system_prompt: 무시됨 (Prompt ID 사용)
            **kwargs: 추가 옵션
        """
        if not self.available:
            return {'success': False, 'error': 'No API key'}

        try:
            # 🔥 약어 목록만 추가
            abbreviations = trading_protocol.get_ultra_compact_prompt()

            # 약어 + 사용자 메시지
            full_message = f"{abbreviations}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n{user_message}"

            info(f"📤 GPT-4.1 호출 (~{len(user_message)} chars, {len(trading_protocol.DYNAMIC_ABBREVIATIONS)} 동적약어)")

            # API 호출 (Prompt ID 사용!)
            response = self.client.responses.create(
                prompt={
                    "id": self.prompt_id,
                    "version": self.prompt_version
                },
                input=full_message,
                temperature=kwargs.get('temperature', 1.0),
                max_output_tokens=kwargs.get('max_tokens', 500)
            )

            # 상태 확인
            if response.status != 'completed':
                error(f"❌ 상태: {response.status}")
                return {'success': False, 'error': f'Status: {response.status}'}

            # 응답 추출
            text = response.output[0].content[0].text

            # 🔥 동적 약어 자동 처리
            self._process_suggested_abbreviations(text)

            # 사용량
            usage = response.usage
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens

            self.update_usage(input_tokens, output_tokens)
            cost = self.calculate_cost(input_tokens, output_tokens)

            info(f"✅ GPT-4.1 완료 | {input_tokens}→{output_tokens} tokens | ${cost:.4f}")

            return {
                'success': True,
                'response': text,
                'usage': {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens
                },
                'model': self.model_name,
                'response_id': response.id,
                'cost_usd': cost,
                'cost_krw': int(cost * 1400)
            }

        except Exception as e:
            error(f"❌ GPT-4.1 오류: {e}")
            import traceback
            error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    def _process_suggested_abbreviations(self, response_text):
        """약어 제안 자동 처리"""
        try:
            # JSON 추출
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

            # 약어 제안 확인
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
openai_client = None

def init_openai_client(api_key, prompt_id, prompt_version="2"):
    """
    OpenAI 클라이언트 초기화

    Args:
        api_key: API 키
        prompt_id: Prompt ID (필수!)
        prompt_version: Prompt 버전 (기본: "1")
    """
    global openai_client
    openai_client = OpenAIClient(api_key, prompt_id, prompt_version)
    return openai_client


# 테스트
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.getenv('OPENAI_API_KEY')
    prompt_id = os.getenv('OPENAI_PROMPT_ID')

    if not api_key:
        print("❌ OPENAI_API_KEY 없음")
        exit(1)

    if not prompt_id:
        print("❌ OPENAI_PROMPT_ID 없음")
        exit(1)

    print("🧪 OpenAI Client 테스트\n")

    # 초기화
    client = OpenAIClient(api_key, prompt_id)

    # 약어 확인
    print("=" * 60)
    print("📋 전송할 약어:")
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

        # 통계
        stats = client.get_usage_stats()
        print(f"\n📈 누적:")
        print(f"   총 토큰: {stats['total_tokens']}")
        print(f"   총 비용: ${stats['total_cost_usd']:.4f} ({stats['total_cost_krw']:,}원)")
    else:
        print(f"\n❌ 실패: {result.get('error')}")