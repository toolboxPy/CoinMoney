"""
AI 전략 생성기
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI가 시장 상황을 분석하고 최적의 전략을 동적으로 생성
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ai.multi_ai_analyzer import multi_ai_analyzer
from utils.logger import info, warning, error
import json


class AIStrategyGenerator:
    """AI 커스텀 전략 생성기"""

    def __init__(self):
        self.name = "AI-Strategy-Generator"
        info(f"🤖 {self.name} 초기화 완료")

    async def generate_strategy(self, ticker, market_data, news=None):
        """
        AI가 시장 분석 후 최적 전략 생성

        Args:
            ticker: 코인 티커
            market_data: 시장 데이터 (df, technical, current_price)
            news: 뉴스 데이터 (선택)

        Returns:
            dict: {
                'strategy_name': str,
                'entry_condition': dict,
                'exit_condition': dict,
                'params': dict,
                'confidence': float,
                'reasoning': str
            }
        """
        try:
            info(f"\n{'=' * 60}")
            info(f"🤖 AI 전략 생성: {ticker}")
            info(f"{'=' * 60}")

            # AI에게 물어볼 프롬프트
            prompt = self._build_strategy_prompt(ticker, market_data, news)

            # AI 분석 (Claude, GPT, Gemini 토론)
            ai_result = await multi_ai_analyzer.analyze_with_debate(
                ticker=ticker,
                question=prompt,
                market_data=market_data,
                news=news,
                rounds=3  # 3라운드 토론
            )

            if not ai_result or not ai_result.get('consensus'):
                warning(f"⚠️ AI 전략 생성 실패")
                return None

            # AI 응답 파싱
            strategy = self._parse_ai_strategy(ai_result['consensus'])

            info(f"✅ AI 전략 생성 완료:")
            info(f"   전략: {strategy['strategy_name']}")
            info(f"   신뢰도: {strategy['confidence'] * 100:.0f}%")
            info(f"   근거: {strategy['reasoning'][:100]}...")

            return strategy

        except Exception as e:
            error(f"❌ AI 전략 생성 오류: {e}")
            return None

    def _build_strategy_prompt(self, ticker, market_data, news):
        """AI에게 물어볼 프롬프트 작성"""

        # 시장 요약
        technical = market_data.get('technical', {})
        current_price = market_data.get('current_price', 0)

        prompt = f"""
당신은 전문 퀀트 트레이더입니다. {ticker}에 대한 최적의 거래 전략을 설계해주세요.

# 현재 시장 상황

## 기술적 분석
- 가격: {current_price:,.0f}원
- 점수: {technical.get('score', 0)}/5
- RSI: {technical.get('rsi', {}).get('value', 50):.1f}
- MACD: {'골든크로스' if technical.get('macd', {}).get('bullish_cross') else '데드크로스' if technical.get('macd', {}).get('bearish_cross') else '중립'}
- 추천: {technical.get('recommendation', 'HOLD')}

## 뉴스
{'긍정적 뉴스 다수' if news and len(news.get('articles', [])) > 5 else '뉴스 부족'}

# 요청사항

다음 형식으로 전략을 설계해주세요:

{{
  "strategy_name": "전략 이름 (예: Aggressive Breakout, Conservative DCA)",
  "strategy_type": "기본 전략 타입 (dca, grid, breakout, scalping, trailing 중 선택)",
  "entry_condition": {{
    "trigger": "진입 조건 (예: RSI < 30 and Volume > 2x)",
    "position_size": "투자 비율 (0.0 ~ 1.0)"
  }},
  "exit_condition": {{
    "take_profit": "익절 조건 (예: +5%)",
    "stop_loss": "손절 조건 (예: -3%)",
    "trailing": "추적매도 사용 여부 (true/false)"
  }},
  "params": {{
    "timeframe": "시간프레임 (5m, 30m, 1h, 4h)",
    "aggressiveness": "공격성 (low, medium, high)"
  }},
  "confidence": 0.85,
  "reasoning": "이 전략을 선택한 상세한 이유"
}}

JSON 형식으로만 응답해주세요.
"""

        return prompt

    def _parse_ai_strategy(self, consensus_text):
        """AI 응답 파싱"""
        try:
            # JSON 추출
            start = consensus_text.find('{')
            end = consensus_text.rfind('}') + 1

            if start == -1 or end == 0:
                warning("⚠️ JSON 형식 찾기 실패, 기본 전략 반환")
                return self._get_default_strategy()

            json_str = consensus_text[start:end]
            strategy = json.loads(json_str)

            # 필수 필드 체크
            required = ['strategy_name', 'strategy_type', 'entry_condition', 'exit_condition']

            for field in required:
                if field not in strategy:
                    warning(f"⚠️ 필수 필드 누락: {field}")
                    return self._get_default_strategy()

            return strategy

        except Exception as e:
            warning(f"⚠️ AI 응답 파싱 실패: {e}")
            return self._get_default_strategy()

    def _get_default_strategy(self):
        """기본 전략 (파싱 실패 시)"""
        return {
            'strategy_name': 'Conservative DCA',
            'strategy_type': 'dca',
            'entry_condition': {
                'trigger': 'Always',
                'position_size': 0.25
            },
            'exit_condition': {
                'take_profit': '+5%',
                'stop_loss': '-3%',
                'trailing': False
            },
            'params': {
                'timeframe': '1h',
                'aggressiveness': 'low'
            },
            'confidence': 0.5,
            'reasoning': 'AI 분석 실패로 기본 DCA 전략 사용'
        }


# 전역 인스턴스
ai_strategy_generator = AIStrategyGenerator()

if __name__ == "__main__":
    print("🧪 AI 전략 생성기 테스트\n")

    import asyncio


    async def test():
        # 테스트 데이터
        market_data = {
            'ticker': 'KRW-BTC',
            'current_price': 50000000,
            'technical': {
                'score': 3.5,
                'rsi': {'value': 45},
                'macd': {'bullish_cross': True},
                'recommendation': 'BUY'
            }
        }

        strategy = await ai_strategy_generator.generate_strategy(
            'KRW-BTC',
            market_data
        )

        if strategy:
            print("=" * 60)
            print("🤖 AI 생성 전략")
            print("=" * 60)
            print(json.dumps(strategy, indent=2, ensure_ascii=False))
            print("=" * 60)


    asyncio.run(test())