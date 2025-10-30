"""
포트폴리오 매니저 (Portfolio Manager)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[핵심 기능]
1. 전체 시장 스캔 (모든 KRW 코인)
2. 거래량 급증 코인 발굴
3. 🤖 AI 자문: 코인 선택 + 배분 비율 결정
4. 💳 크레딧 시스템: 무분별한 AI 호출 방지
5. 동적 자금 배분 (실시간 KRW 잔고 기반)
6. 포트폴리오 리밸런싱
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import pyupbit
import asyncio
import json
import random
from datetime import datetime, timedelta
from utils.logger import info, warning, error
from analysis.technical import technical_analyzer

# 🔥 AI 시스템 임포트
try:
    from ai.credit_system import credit_system
    AI_AVAILABLE = True
    info("✅ AI 포트폴리오 시스템 활성화")
except ImportError as e:
    AI_AVAILABLE = False
    credit_system = None
    warning(f"⚠️ AI 시스템 비활성: {e}")


class PortfolioManager:
    """
    AI 통합 포트폴리오 매니저 (동적 예산)

    - 전체 시장 분석
    - AI 자문: 코인 선택 + 배분
    - 크레딧 관리
    - 실시간 KRW 잔고 기반
    """

    def __init__(self, upbit_instance, max_coins=5, min_score=20.0):
        """
        포트폴리오 매니저 초기화

        Args:
            upbit_instance: Upbit API 인스턴스 (실시간 잔고 조회용)
            max_coins: 최대 코인 수
            min_score: 최소 점수 기준
        """
        # 🔥 Upbit 인스턴스 저장 (잔고 조회용)
        self.upbit = upbit_instance

        # 기본 설정
        self.max_coins = max_coins
        self.min_score = min_score

        # 포트폴리오 상태
        self.allocations = {}
        self.coin_scores = {}
        self.coin_data = {}
        self.current_allocation = {}

        # 배분 설정
        self.min_allocation = 0.05
        self.max_allocation = 0.40

        # 거래량 급증 감지
        self.volume_surge_threshold = 3.0
        self.volume_history = {}

        # 메인 코인
        self.core_coins = ['KRW-BTC', 'KRW-ETH']

        # 제외 코인
        self.excluded_coins = [
            'KRW-USDT', 'KRW-USDC', 'KRW-DAI',
            'KRW-WBTC', 'KRW-WEMIX',
        ]

        info("💼 포트폴리오 매니저 초기화 완료")
        info(f"   최대 코인 수: {self.max_coins}개")
        info(f"   최소 점수 기준: {self.min_score}점")
        if AI_AVAILABLE:
            info(f"   💳 AI 크레딧: {credit_system.get_remaining()}/{credit_system.daily_limit}")

    def get_current_budget(self):
        """
        실시간 KRW 잔고 조회

        Returns:
            float: 현재 KRW 잔고
        """
        try:
            krw_balance = self.upbit.get_balance("KRW")
            return krw_balance if krw_balance else 0
        except Exception as e:
            error(f"❌ 잔고 조회 오류: {e}")
            return 0

    async def scan_all_coins(self):
        """
        전체 KRW 시장 스캔 → 상위 10개 후보 선정
        """
        try:
            info("\n" + "=" * 60)
            info("🔍 전체 시장 스캔 시작")
            info("=" * 60)

            all_tickers = await asyncio.to_thread(pyupbit.get_tickers, fiat="KRW")

            if not all_tickers:
                warning("⚠️ 코인 목록 조회 실패")
                return []

            valid_tickers = [
                t for t in all_tickers
                if t not in self.excluded_coins
            ]

            info(f"📊 스캔 대상: {len(valid_tickers)}개 코인")

            analyzed_coins = []
            failed_count = 0
            debug_count = 0

            fail_reasons = {
                'no_data': 0,
                'below_threshold': 0,
                'exception': 0
            }

            for ticker in valid_tickers:
                try:
                    coin_data = await self._analyze_coin(ticker)

                    if coin_data:
                        if coin_data['score'] >= self.min_score:
                            analyzed_coins.append(coin_data)

                            if debug_count < 10:
                                info(f"✅ [{ticker}] 통과! 점수: {coin_data['score']:.1f}")
                                debug_count += 1
                        else:
                            failed_count += 1
                            fail_reasons['below_threshold'] += 1
                    else:
                        failed_count += 1
                        fail_reasons['no_data'] += 1

                except Exception as e:
                    failed_count += 1
                    fail_reasons['exception'] += 1
                    continue

            info(f"\n✅ 분석 완료:")
            info(f"   유효: {len(analyzed_coins)}개")
            info(f"   실패: {failed_count}개")
            info(f"      - 데이터 없음: {fail_reasons['no_data']}개")
            info(f"      - 점수 미달: {fail_reasons['below_threshold']}개")
            info(f"      - 예외 발생: {fail_reasons['exception']}개")

            if len(analyzed_coins) == 0:
                error("\n❌ 유효한 코인 0개!")
                error(f"   최소 점수 기준: {self.min_score}점")
                error(f"   → 모든 코인이 데이터 없음 또는 조건 미달")
                return []

            analyzed_coins.sort(key=lambda x: x['score'], reverse=True)
            top_10 = analyzed_coins[:10]

            info(f"\n📋 상위 10개 후보:")
            for i, coin in enumerate(top_10, 1):
                info(f"   {i}. {coin['ticker']}: {coin['score']:.1f}점 "
                     f"(24h {coin['change_24h']:+.1f}%, {coin['momentum']})")

            info("=" * 60 + "\n")

            return top_10

        except Exception as e:
            error(f"❌ 전체 스캔 오류: {e}")
            import traceback
            error(traceback.format_exc())
            return []

    async def _analyze_coin(self, ticker):
        """개별 코인 분석 (안전 버전)"""
        try:
            current_price = await asyncio.to_thread(
                pyupbit.get_current_price,
                ticker
            )

            if not current_price or current_price < 100:
                return None

            df = await asyncio.to_thread(
                pyupbit.get_ohlcv,
                ticker,
                interval='minute60',
                count=24
            )

            if df is None or len(df) < 20:
                return None

            volume_24h = df['value'].sum()

            if volume_24h < 1_000_000:
                return None

            recent_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].iloc[-24:-1].mean()
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0

            price_change_1h = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]
            price_change_24h = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]

            volatility = (df['high'] / df['low'] - 1).mean()

            # 🔥 기술 분석 (안전하게)
            technical_score = 0
            try:
                technical = technical_analyzer.analyze(df)
                if technical is None or not isinstance(technical, dict):
                    technical_score = 0
                else:
                    technical_score = technical.get('score', 0)
            except Exception as e:
                technical_score = 0

            # 모멘텀
            if price_change_24h > 0.05:
                momentum = 'STRONG_UP'
            elif price_change_24h > 0.02:
                momentum = 'UP'
            elif price_change_24h > -0.02:
                momentum = 'NEUTRAL'
            elif price_change_24h > -0.05:
                momentum = 'DOWN'
            else:
                momentum = 'STRONG_DOWN'

            # 점수 계산
            score = 0.0

            # 1. 기술 (30점)
            tech_points = technical_score * 6
            score += tech_points

            # 2. 거래량 (40점)
            if volume_24h > 100_000_000_000:
                vol_points = 40
            elif volume_24h > 50_000_000_000:
                vol_points = 35
            elif volume_24h > 10_000_000_000:
                vol_points = 30
            elif volume_24h > 1_000_000_000:
                vol_points = 25
            elif volume_24h > 100_000_000:
                vol_points = 20
            else:
                vol_points = 15

            score += vol_points

            # 3. 모멘텀 (20점)
            if momentum == 'STRONG_UP':
                mom_points = 20
            elif momentum == 'UP':
                mom_points = 15
            elif momentum == 'NEUTRAL':
                mom_points = 10
            else:
                mom_points = 5

            score += mom_points

            # 4. 변동성 (10점)
            if 0.02 < volatility < 0.10:
                vol_points_2 = 10
            elif 0.01 < volatility < 0.15:
                vol_points_2 = 7
            else:
                vol_points_2 = 5

            score += vol_points_2

            return {
                'ticker': ticker,
                'score': score,
                'price': current_price,
                'volume_24h': volume_24h,
                'volume_ratio': volume_ratio,
                'change_1h': price_change_1h * 100,
                'change_24h': price_change_24h * 100,
                'technical_score': technical_score,
                'momentum': momentum,
                'volatility': volatility
            }

        except Exception as e:
            return None

    async def ai_select_portfolio(self, top_10_candidates):
        """🤖 AI가 포트폴리오 선택"""
        try:
            info("\n" + "=" * 60)
            info("🤖 AI 포트폴리오 자문 시작")
            info("=" * 60)

            if not credit_system.can_use('single_ai'):
                warning("⚠️ AI 크레딧 부족! 기본 알고리즘 사용")
                return self._default_ai_selection(top_10_candidates)

            prompt = self._build_ai_prompt(top_10_candidates)

            info(f"🤖 AI 자문 중...")
            info(f"💳 크레딧 소비: 1")

            credit_system.use_credit('single_ai', '포트폴리오 선택')

            ai_response_text = await self._call_ai(prompt)

            if not ai_response_text:
                warning("⚠️ AI 응답 없음")
                return self._default_ai_selection(top_10_candidates)

            ai_response = self._parse_ai_response(
                ai_response_text,
                top_10_candidates
            )

            info(f"\n✅ AI 선택 완료!")
            info(f"   선택: {len(ai_response['selected'])}개 코인")
            info(f"   신뢰도: {ai_response['ai_confidence'] * 100:.0f}%")
            info(f"   남은 크레딧: {credit_system.get_remaining()}/{credit_system.daily_limit}")

            for coin in ai_response['selected']:
                info(f"      🎯 {coin['ticker']}: {coin['allocation'] * 100:.0f}%")

            info("=" * 60 + "\n")

            return ai_response

        except Exception as e:
            error(f"❌ AI 선택 오류: {e}")
            import traceback
            error(traceback.format_exc())
            return self._default_ai_selection(top_10_candidates)

    async def _call_ai(self, prompt):
        """AI 호출"""
        try:
            from ai.multi_ai_analyzer import multi_ai

            result = await asyncio.to_thread(
                multi_ai.analyze_sync,
                ticker="PORTFOLIO",
                question=prompt
            )

            if result and result.get('analysis'):
                return result['analysis']

            return None

        except Exception as e:
            error(f"❌ AI 호출 오류: {e}")
            return None

    def _build_ai_prompt(self, candidates):
        """AI 프롬프트 작성"""
        candidates_text = "\n".join([
            f"{i+1}. {c['ticker']}: Score={c['score']:.1f} "
            f"Vol24h={c['volume_24h']/1e9:.1f}B Change24h={c['change_24h']:+.1f}% "
            f"Tech={c['technical_score']:.1f} Momentum={c['momentum']}"
            for i, c in enumerate(candidates)
        ])

        # 🔥 실시간 예산 조회
        current_budget = self.get_current_budget()

        prompt = f"""
You are a crypto portfolio manager. Select 3-5 coins from these top 10 candidates.

Budget: {current_budget:,} KRW (real-time balance)
Goal: Maximize profit with risk diversification

CANDIDATES:
{candidates_text}

REQUIREMENTS:
1. Choose 3-5 coins
2. Allocate percentage (total must be 100%)
3. Provide brief reasoning for each

OUTPUT FORMAT (JSON only):
{{
  "selected": [
    {{"ticker": "KRW-BTC", "allocation": 0.4, "reasoning": "Market leader, stable"}},
    {{"ticker": "KRW-ETH", "allocation": 0.3, "reasoning": "Strong fundamentals"}},
    ...
  ],
  "overall_strategy": "Brief strategy description",
  "confidence": 0.85
}}

Return ONLY the JSON. No explanation before or after.
"""
        return prompt

    def _parse_ai_response(self, response_text, candidates):
        """AI 응답 파싱"""
        try:
            start = response_text.find('{')
            end = response_text.rfind('}') + 1

            if start == -1 or end == 0:
                warning("⚠️ JSON 형식 없음")
                return self._default_ai_selection(candidates)

            json_str = response_text[start:end]
            data = json.loads(json_str)

            selected = data.get('selected', [])

            if not selected:
                warning("⚠️ 선택 코인 없음")
                return self._default_ai_selection(candidates)

            result = {
                'selected': [],
                'ai_confidence': data.get('confidence', 0.7),
                'reasoning': data.get('overall_strategy', 'AI 포트폴리오 전략')
            }

            total_allocation = 0.0

            for item in selected:
                ticker = item.get('ticker')
                allocation = item.get('allocation', 0)
                reasoning = item.get('reasoning', '')

                if ticker and allocation > 0:
                    result['selected'].append({
                        'ticker': ticker,
                        'allocation': allocation,
                        'reasoning': reasoning
                    })
                    total_allocation += allocation

            if total_allocation > 0 and abs(total_allocation - 1.0) > 0.01:
                for coin in result['selected']:
                    coin['allocation'] /= total_allocation

            return result

        except Exception as e:
            warning(f"⚠️ AI 응답 파싱 실패: {e}")
            return self._default_ai_selection(candidates)

    def _default_ai_selection(self, candidates):
        """기본 선택 (AI 없이)"""
        info("⚙️ 기본 알고리즘 사용")

        top_3 = candidates[:3]
        total_score = sum(c['score'] for c in top_3)

        result = {
            'selected': [],
            'ai_confidence': 0.6,
            'reasoning': '기본 알고리즘: 점수 기반 상위 3개'
        }

        for coin in top_3:
            allocation = coin['score'] / total_score
            result['selected'].append({
                'ticker': coin['ticker'],
                'allocation': allocation,
                'reasoning': f"점수 {coin['score']:.1f}점"
            })

        return result

    async def analyze_and_allocate(self, market_sentiment):
        """
        전체 시장 분석 + AI 자문 + 자금 배분 (🔥 실시간 예산)
        """
        try:
            info("\n" + "=" * 60)
            info("💼 포트폴리오 분석 + AI 자문")
            info("=" * 60)

            # 🔥 실시간 예산 조회
            current_budget = self.get_current_budget()
            info(f"💰 현재 사용 가능 예산: {current_budget:,.0f}원")

            if current_budget < 10000:
                error("❌ 예산 부족 (10,000원 미만)")
                return None

            # 1. 전체 시장 스캔
            top_10 = await self.scan_all_coins()

            if not top_10 or len(top_10) == 0:
                error("❌ 유효한 후보 없음")
                return None

            # 2. AI 선택
            if AI_AVAILABLE and credit_system.get_remaining() >= 1:
                ai_result = await self.ai_select_portfolio(top_10)
            else:
                warning("⚠️ AI 미사용")
                ai_result = self._default_ai_selection(top_10)

            if not ai_result or not ai_result.get('selected'):
                error("❌ AI 선택 실패")
                return None

            # 3. 예산 배분 (🔥 실시간 예산 사용)
            allocations = {}

            info(f"\n💰 자금 배분 (총 예산: {current_budget:,.0f}원):")

            for coin_info in ai_result['selected']:
                ticker = coin_info['ticker']
                allocation_pct = coin_info['allocation']
                budget = int(current_budget * allocation_pct)  # 🔥 동적!

                allocations[ticker] = {
                    'budget': budget,
                    'allocation': allocation_pct,
                    'score': next((c['score'] for c in top_10 if c['ticker'] == ticker), 0),
                    'reasoning': coin_info.get('reasoning', '')
                }

                info(f"   {ticker}: {budget:,}원 ({allocation_pct * 100:.0f}%)")
                info(f"      → {coin_info.get('reasoning', 'N/A')}")

            info("=" * 60 + "\n")

            # 4. 반환
            return {
                'allocations': allocations,
                'total_analyzed': len(top_10),
                'current_budget': current_budget,  # 🔥 실제 예산 포함
                'ai_used': AI_AVAILABLE,
                'ai_confidence': ai_result.get('ai_confidence', 0),
                'reasoning': ai_result.get('reasoning', '')
            }

        except Exception as e:
            error(f"❌ 포트폴리오 분석 오류: {e}")
            import traceback
            error(traceback.format_exc())
            return None


# ============================================================
# 동적 워커 매니저
# ============================================================

class DynamicWorkerManager:
    """동적 워커 관리자"""

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.active_workers = {}
        self.worker_budgets = {}

        info("⚙️ 동적 워커 매니저 초기화")

    async def update_workers(self, allocations):
        """워커 업데이트 (추가/제거/예산변경)"""
        try:
            current_coins = set(self.active_workers.keys())
            target_coins = set(allocations.keys())

            coins_to_add = target_coins - current_coins
            coins_to_remove = current_coins - target_coins
            coins_to_update = current_coins & target_coins

            info(f"\n⚙️ 워커 업데이트:")
            info(f"   추가: {len(coins_to_add)}개")
            info(f"   제거: {len(coins_to_remove)}개")
            info(f"   유지: {len(coins_to_update)}개")

            for ticker in coins_to_add:
                budget = allocations[ticker]
                await self.add_worker(ticker, budget)

            for ticker in coins_to_remove:
                await self.remove_worker(ticker)

            for ticker in coins_to_update:
                new_budget = allocations[ticker]
                old_budget = self.worker_budgets.get(ticker, 0)

                if new_budget != old_budget:
                    self.worker_budgets[ticker] = new_budget
                    info(f"💰 [{ticker}] 예산 변경: {old_budget:,} → {new_budget:,}원")

        except Exception as e:
            error(f"❌ 워커 업데이트 오류: {e}")

    async def add_worker(self, ticker, budget):
        """워커 추가"""
        if ticker in self.active_workers:
            warning(f"⚠️ [{ticker}] 이미 워커 존재")
            return

        try:
            info(f"🆕 [{ticker}] 워커 생성 (예산: {budget:,}원)")

            task = asyncio.create_task(
                self.bot.spot_worker(ticker, budget)
            )

            self.active_workers[ticker] = task
            self.worker_budgets[ticker] = budget

            info(f"✅ [{ticker}] 워커 시작 완료")

        except Exception as e:
            error(f"❌ [{ticker}] 워커 생성 오류: {e}")

    async def remove_worker(self, ticker):
        """워커 제거"""
        if ticker not in self.active_workers:
            return

        try:
            info(f"🗑️ [{ticker}] 워커 제거 중...")

            task = self.active_workers[ticker]
            task.cancel()

            del self.active_workers[ticker]
            del self.worker_budgets[ticker]

            info(f"✅ [{ticker}] 워커 제거 완료")

        except Exception as e:
            error(f"❌ [{ticker}] 워커 제거 오류: {e}")

    def get_worker_budget(self, ticker):
        """워커 예산 조회"""
        return self.worker_budgets.get(ticker, 0)

    def get_active_coins(self):
        """활성 코인 목록"""
        return list(self.active_workers.keys())


# ============================================================
# 테스트
# ============================================================

async def test_portfolio_manager():
    """포트폴리오 매니저 테스트"""
    print("🧪 AI 포트폴리오 매니저 테스트\n")

    import pyupbit
    upbit = pyupbit.Upbit("test", "test")

    pm = PortfolioManager(
        upbit_instance=upbit,
        max_coins=5,
        min_score=20.0
    )

    market_sentiment = {
        'status': 'BULLISH',
        'score': 3.5
    }

    result = await pm.analyze_and_allocate(market_sentiment)

    if result:
        print("\n✅ 테스트 성공!")
        print(f"   분석 코인: {result['total_analyzed']}개")
        print(f"   배분 코인: {len(result['allocations'])}개")
        print(f"   실시간 예산: {result['current_budget']:,}원")
        print(f"   AI 사용: {'✅' if result['ai_used'] else '❌'}")
    else:
        print("\n❌ 테스트 실패")


if __name__ == "__main__":
    asyncio.run(test_portfolio_manager())