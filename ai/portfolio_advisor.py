"""
AI 포트폴리오 어드바이저
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
초기 포트폴리오 구성 시 AI에게 자문
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ai.credit_system import credit_system
from utils.logger import info, warning, error
import json


class PortfolioAdvisor:
    """AI 포트폴리오 자문"""

    def __init__(self):
        self.name = "Portfolio-Advisor"
        info(f"🎯 {self.name} 초기화")

    async def select_coins(self, candidates, total_budget):
        """
        AI에게 코인 선택 요청

        Args:
            candidates: [
                {
                    'ticker': 'KRW-BTC',
                    'score': 85.5,
                    'volume_24h': 1000000000,
                    'change_24h': 3.2,
                    'technical_score': 3.5,
                    'momentum': 'STRONG_UP'
                },
                ...
            ]
            total_budget: 총 예산 (원)

        Returns:
            {
                'selected': [
                    {
                        'ticker': 'KRW-BTC',
                        'allocation': 0.4,  # 40%
                        'budget': 20000,
                        'reasoning': 'BTC는 시장 주도...'
                    },
                    ...
                ],
                'total_allocation': 1.0,
                'ai_confidence': 0.85,
                'reasoning': '전체 포트폴리오 전략...'
            }
        """
        try:
            info(f"\n{'=' * 60}")
            info(f"🤖 AI 포트폴리오 자문 시작")
            info(f"{'=' * 60}")
            info(f"📊 후보: {len(candidates)}개")
            info(f"💰 예산: {total_budget:,}원")

            # 1. 크레딧 체크
            if not credit_system.can_use('single_ai'):
                warning("⚠️ 크레딧 부족! 기본 선택 사용")
                return self._default_selection(candidates, total_budget)

            # 2. 프롬프트 작성
            prompt = self._build_prompt(candidates, total_budget)

            # 3. 크레딧 사용
            credit_system.use_credit('single_ai', '초기 포트폴리오 선택')

            # 4. AI 호출
            info("🤖 AI에게 자문 중...")

            # TODO: 실제 AI 호출 (지금은 시뮬레이션)
            ai_response = await self._simulate_ai_response(candidates, total_budget)

            # 5. AI 토론 필요?
            if credit_system.can_use('debate'):
                info("💬 AI 토론 시작...")
                credit_system.use_credit('debate', '포트폴리오 토론')

                # TODO: 3 AI 토론
                ai_response = await self._simulate_debate(ai_response)

            info(f"✅ AI 선택 완료: {len(ai_response['selected'])}개 코인")
            for coin in ai_response['selected']:
                info(f"   🎯 {coin['ticker']}: {coin['allocation'] * 100:.0f}% ({coin['budget']:,}원)")

            info(f"{'=' * 60}\n")

            return ai_response

        except Exception as e:
            error(f"❌ AI 자문 오류: {e}")
            return self._default_selection(candidates, total_budget)

    def _build_prompt(self, candidates, total_budget):
        """AI 프롬프트 작성"""

        # 후보 요약
        candidates_text = "\n".join([
            f"{i + 1}. {c['ticker']}: 점수 {c['score']:.1f}, "
            f"24h {c['change_24h']:+.1f}%, "
            f"기술 {c['technical_score']:.1f}/5, "
            f"모멘텀 {c['momentum']}"
            for i, c in enumerate(candidates[:10])
        ])

        prompt = f"""
당신은 전문 암호화폐 포트폴리오 매니저입니다.

# 투자 조건
- 총 예산: {total_budget:,}원
- 선택 가능: 3~5개 코인
- 목표: 리스크 분산 + 수익 극대화

# 후보 코인 (상위 10개)
{candidates_text}

# 요청사항
1. 위 10개 중 3~5개 선택
2. 각 코인별 투자 비율 결정 (합 100%)
3. 선택 이유 설명

다음 JSON 형식으로 응답:

{{
  "selected": [
    {{
      "ticker": "KRW-BTC",
      "allocation": 0.4,
      "reasoning": "시장 주도 코인, 안정성..."
    }}
  ],
  "overall_strategy": "전체 전략 설명",
  "confidence": 0.85
}}

JSON만 출력하세요.
"""
        return prompt

    async def _simulate_ai_response(self, candidates, total_budget):
        """AI 응답 시뮬레이션 (실제로는 Claude/GPT 호출)"""

        # 상위 3~5개 선택 (점수 기준)
        sorted_candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)

        # 3~5개 선택
        import random
        num_select = random.choice([3, 4, 5])
        selected = sorted_candidates[:num_select]

        # 비율 배분 (점수 비례)
        total_score = sum(c['score'] for c in selected)

        result = {
            'selected': [],
            'total_allocation': 0.0,
            'ai_confidence': 0.8,
            'reasoning': f'{num_select}개 코인 분산 투자 전략'
        }

        for coin in selected:
            allocation = coin['score'] / total_score
            budget = total_budget * allocation

            result['selected'].append({
                'ticker': coin['ticker'],
                'allocation': allocation,
                'budget': budget,
                'reasoning': f"점수 {coin['score']:.1f}점, {coin['momentum']} 모멘텀"
            })

            result['total_allocation'] += allocation

        return result

    async def _simulate_debate(self, initial_response):
        """AI 토론 시뮬레이션"""
        # 실제로는 3 AI가 토론하지만, 지금은 약간 조정만
        info("   Claude: 동의합니다")
        info("   GPT: 좋은 선택입니다")
        info("   Gemini: 리스크 균형이 좋습니다")

        return initial_response

    def _default_selection(self, candidates, total_budget):
        """기본 선택 (AI 없이)"""
        warning("⚠️ AI 미사용 - 기본 알고리즘 사용")

        # 상위 3개 균등 배분
        sorted_candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)
        selected = sorted_candidates[:3]

        allocation = 1.0 / len(selected)

        result = {
            'selected': [],
            'total_allocation': 1.0,
            'ai_confidence': 0.6,
            'reasoning': '기본 알고리즘: 상위 3개 균등 배분'
        }

        for coin in selected:
            budget = total_budget * allocation
            result['selected'].append({
                'ticker': coin['ticker'],
                'allocation': allocation,
                'budget': budget,
                'reasoning': f"점수 기준 상위 선택"
            })

        return result


# 전역 인스턴스
portfolio_advisor = PortfolioAdvisor()

if __name__ == "__main__":
    import asyncio

    print("🧪 포트폴리오 어드바이저 테스트\n")


    async def test():
        # 테스트 후보
        candidates = [
            {
                'ticker': 'KRW-BTC',
                'score': 85.5,
                'volume_24h': 1000000000,
                'change_24h': 3.2,
                'technical_score': 4.0,
                'momentum': 'STRONG_UP'
            },
            {
                'ticker': 'KRW-ETH',
                'score': 78.3,
                'volume_24h': 500000000,
                'change_24h': 2.5,
                'technical_score': 3.5,
                'momentum': 'UP'
            },
            {
                'ticker': 'KRW-XRP',
                'score': 72.1,
                'volume_24h': 300000000,
                'change_24h': 1.8,
                'technical_score': 3.0,
                'momentum': 'UP'
            },
        ]

        result = await portfolio_advisor.select_coins(candidates, 50000)

        print("\n" + "=" * 60)
        print("🎯 AI 선택 결과")
        print("=" * 60)

        for coin in result['selected']:
            print(f"\n📊 {coin['ticker']}")
            print(f"   배분: {coin['allocation'] * 100:.1f}%")
            print(f"   예산: {coin['budget']:,.0f}원")
            print(f"   이유: {coin['reasoning']}")

        print("\n" + "=" * 60)


    asyncio.run(test())