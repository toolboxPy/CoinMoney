#!/usr/bin/env python3
"""
GPT-4.1 API 테스트 스크립트
"""
import os
import sys
import requests
from dotenv import load_dotenv

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env 로드
load_dotenv()


def test_gpt41():
    """GPT-4.1 테스트"""

    # API 키 확인
    api_key = os.getenv('OPENAI_API_KEY')

    if not api_key:
        print("❌ .env 파일에 OPENAI_API_KEY가 없습니다!")
        return False

    print("🧪 GPT-4.1 테스트 시작...")
    print(f"🔑 API 키: {api_key[:10]}...{api_key[-4:]}")

    # API 호출
    url = "https://api.openai.com/v1/responses"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": "gpt-4.1",
        "input": "Tell me a three sentence bedtime story about a unicorn."
    }

    try:
        print("\n📤 요청 전송 중...")

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        print(f"📊 상태 코드: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            print("\n✅ 성공!")
            print(f"   Response ID: {data.get('id')}")
            print(f"   상태: {data.get('status')}")

            # 출력 추출
            output = data.get('output', [])
            if output:
                content = output[0].get('content', [])
                if content:
                    text = content[0].get('text', '')
                    print(f"\n📥 응답:\n{text}")

            # 사용량
            usage = data.get('usage', {})
            print(f"\n📊 사용량:")
            print(f"   입력 토큰: {usage.get('input_tokens', 0)}")
            print(f"   출력 토큰: {usage.get('output_tokens', 0)}")
            print(f"   총 토큰: {usage.get('total_tokens', 0)}")

            return True

        else:
            print(f"\n❌ 실패!")
            print(f"   에러: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_gpt41()
    sys.exit(0 if success else 1)