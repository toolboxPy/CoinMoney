"""
AI 클라이언트 베이스 클래스
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
모든 AI 클라이언트의 공통 인터페이스
"""
from abc import ABC, abstractmethod
from utils.logger import info, warning, error


class BaseAIClient(ABC):
    """AI 클라이언트 베이스 클래스"""

    def __init__(self, api_key, model_name):
        """
        초기화

        Args:
            api_key: API 키
            model_name: 모델 이름
        """
        self.api_key = api_key
        self.model_name = model_name
        self.available = bool(api_key)

        # 토큰 추적
        self.input_tokens_used = 0
        self.output_tokens_used = 0
        self.total_tokens_used = 0
        self.total_cost = 0.0

        # 토큰 가격 (100만 토큰 기준, USD)
        self.input_price_per_mtok = 0.0
        self.output_price_per_mtok = 0.0

    @abstractmethod
    def send_message(self, messages, system_prompt=None, **kwargs):
        """
        메시지 전송 (추상 메서드)

        Args:
            messages: 메시지 리스트
            system_prompt: 시스템 프롬프트
            **kwargs: 추가 옵션

        Returns:
            dict: 응답 결과
        """
        pass

    @abstractmethod
    def get_remaining_tokens(self):
        """
        남은 토큰 수 (추상 메서드)

        Returns:
            dict: {
                'daily_limit': int,
                'used': int,
                'remaining': int
            }
        """
        pass

    def calculate_cost(self, input_tokens, output_tokens):
        """
        비용 계산

        Args:
            input_tokens: 입력 토큰
            output_tokens: 출력 토큰

        Returns:
            float: 비용 (USD)
        """
        input_cost = (input_tokens / 1_000_000) * self.input_price_per_mtok
        output_cost = (output_tokens / 1_000_000) * self.output_price_per_mtok
        return input_cost + output_cost

    def update_usage(self, input_tokens, output_tokens):
        """
        사용량 업데이트

        Args:
            input_tokens: 입력 토큰
            output_tokens: 출력 토큰
        """
        self.input_tokens_used += input_tokens
        self.output_tokens_used += output_tokens
        self.total_tokens_used += (input_tokens + output_tokens)

        cost = self.calculate_cost(input_tokens, output_tokens)
        self.total_cost += cost

    def get_usage_stats(self):
        """
        사용 통계

        Returns:
            dict: 통계 정보
        """
        return {
            'model': self.model_name,
            'input_tokens': self.input_tokens_used,
            'output_tokens': self.output_tokens_used,
            'total_tokens': self.total_tokens_used,
            'total_cost_usd': round(self.total_cost, 4),
            'total_cost_krw': int(self.total_cost * 1400)  # 환율 1400원
        }

    def reset_usage(self):
        """사용량 초기화"""
        self.input_tokens_used = 0
        self.output_tokens_used = 0
        self.total_tokens_used = 0
        self.total_cost = 0.0