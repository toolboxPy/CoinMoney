"""
연결 관리자
API 실패 시 자동 재시도
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import time
from functools import wraps
from config.master_config import CONNECTION_RETRY
from utils.logger import warning, error, info


class ConnectionManager:
    """API 연결 관리자"""

    def __init__(self):
        self.max_retries = CONNECTION_RETRY['max_retries']
        self.retry_delays = CONNECTION_RETRY['delays']

    def with_retry(self, func):
        """
        재시도 데코레이터

        사용법:
        @connection_manager.with_retry
        def get_balance():
            return upbit.get_balance()
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(self.max_retries + 1):
                try:
                    result = func(*args, **kwargs)

                    if attempt > 0:
                        info(f"✅ 재시도 성공 ({attempt}회 시도) - {func.__name__}")

                    return result

                except Exception as e:
                    last_error = e

                    if attempt < self.max_retries:
                        delay = self.retry_delays[attempt]
                        warning(
                            f"⚠️ API 오류 ({attempt + 1}/{self.max_retries + 1}): {func.__name__} - {e}"
                        )
                        warning(f"   {delay}초 후 재시도...")
                        time.sleep(delay)
                    else:
                        error(f"❌ 최대 재시도 횟수 초과 - {func.__name__}")

            # 모든 재시도 실패
            raise last_error

        return wrapper

    def safe_api_call(self, func, *args, **kwargs):
        """
        안전한 API 호출

        Returns:
            tuple: (success: bool, result: any)
        """
        try:
            retry_func = self.with_retry(func)
            result = retry_func(*args, **kwargs)
            return True, result

        except Exception as e:
            error(f"💥 API 호출 최종 실패: {func.__name__} - {e}")
            return False, None

    def retry_on_failure(self, max_attempts=None, delay=None):
        """
        커스텀 재시도 데코레이터

        Args:
            max_attempts: 최대 시도 횟수
            delay: 재시도 간격 (초)
        """
        attempts = max_attempts or self.max_retries
        retry_delay = delay or 3

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                for attempt in range(attempts):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        if attempt < attempts - 1:
                            warning(f"⚠️ {func.__name__} 실패 ({attempt + 1}/{attempts}): {e}")
                            time.sleep(retry_delay)
                        else:
                            raise
                return None

            return wrapper

        return decorator


# 전역 인스턴스
connection_manager = ConnectionManager()


# 편의 함수
def with_retry(func):
    """재시도 데코레이터"""
    return connection_manager.with_retry(func)


def safe_call(func, *args, **kwargs):
    """안전한 호출"""
    return connection_manager.safe_api_call(func, *args, **kwargs)


# 사용 예시
if __name__ == "__main__":
    print("🧪 Connection Manager 테스트\n")


    # 테스트 1: 성공하는 함수
    @with_retry
    def test_success():
        print("  ✅ API 호출 성공!")
        return "데이터"


    print("테스트 1: 정상 작동")
    result = test_success()
    print(f"  결과: {result}\n")


    # 테스트 2: 2번 실패 후 성공
    class Counter:
        count = 0


    @with_retry
    def test_retry_success():
        Counter.count += 1
        if Counter.count < 3:
            raise Exception(f"API 에러 (시도 {Counter.count})")
        return "성공!"


    print("테스트 2: 재시도 후 성공")
    Counter.count = 0
    result = test_retry_success()
    print(f"  결과: {result}\n")


    # 테스트 3: 계속 실패
    @with_retry
    def test_always_fail():
        raise Exception("항상 실패하는 API")


    print("테스트 3: 모든 재시도 실패")
    try:
        test_always_fail()
    except Exception as e:
        print(f"  예상된 실패: {e}\n")


    # 테스트 4: safe_call 사용
    def risky_function():
        import random
        if random.random() < 0.7:
            raise Exception("랜덤 에러")
        return "성공"


    print("테스트 4: safe_call 사용")
    success, result = safe_call(risky_function)
    if success:
        print(f"  성공: {result}")
    else:
        print(f"  실패했지만 프로그램은 계속 실행됨")

    print("\n✅ 테스트 완료!")