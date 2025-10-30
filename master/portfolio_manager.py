"""
포트폴리오 매니저 (Portfolio Manager)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[핵심 기능]
1. 전체 시장 스캔 (모든 KRW 코인)
2. 거래량 급증 코인 발굴
3. 🤖 AI 토론: 코인 선택 + 배분 비율 결정
4. 🧬 압축 언어 (동적 진화): 토큰 절약
5. 💳 크레딧 시스템: 무분별한 AI 호출 방지
6. 동적 자금 배분 (좋은 코인에 더 많이)
7. 포트폴리오 리밸런싱
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import pyupbit
import asyncio
import json
from datetime import datetime, timedelta
from config.master_config import SPOT_BUDGET
from utils.logger import info, warning, error
from analysis.technical import technical_analyzer

# 🔥 AI 시스템 임포트
try:
    from ai.credit_system import credit_system
    from ai.multi_ai_debate_dynamic import DynamicAIDebate
    AI_AVAILABLE = True
    info("✅ AI 포트폴리오 시스템 활성화")
except ImportError as e:
    AI_AVAILABLE = False
    credit_system = None
    warning(f"⚠️ AI 시스템 비활성: {e}")


class PortfolioManager:
    """
    AI 통합 포트폴리오 매니저

    - 전체 시장 분석
    - AI 토론: 코인 선택 + 배분
    - 압축 언어 (동적 진화)
    - 크레딧 관리
    """

    def __init__(self, total_budget=SPOT_BUDGET, max_coins=5, min_score=50.0):
        """
        포트폴리오 매니저 초기화

        Args:
            total_budget: 총 투자 예산
            max_coins: 최대 코인 수
            min_score: 최소 점수 기준
        """
        # 기본 설정
        self.total_budget = total_budget
        self.max_coins = max_coins
        self.min_score = min_score

        # 포트폴리오 상태
        self.allocations = {}  # {coin: allocated_amount}
        self.coin_scores = {}  # {coin: score}
        self.coin_data = {}  # {coin: market_data}
        self.current_allocation = {}

        # 배분 설정
        self.min_allocation = 0.05  # 최소 5%
        self.max_allocation = 0.40  # 최대 40%

        # 거래량 급증 감지
        self.volume_surge_threshold = 3.0  # 평균 대비 3배
        self.volume_history = {}  # {coin: [volumes]}

        # 메인 코인 (항상 포함 고려)
        self.core_coins = ['KRW-BTC', 'KRW-ETH']

        # 제외 코인 (스테이블코인, 레버리지 등)
        self.excluded_coins = [
            'KRW-USDT', 'KRW-USDC', 'KRW-DAI',  # 스테이블
            'KRW-WBTC', 'KRW-WEMIX',  # 래핑
        ]

        # 🤖 AI 시스템
        if AI_AVAILABLE:
            self.ai_debate = DynamicAIDebate(
                interval=timedelta(minutes=30),
                rounds=3  # 포트폴리오 선택: 3라운드 토론
            )
            info("🤖 AI 토론 시스템 연결 완료 (압축 언어 활성화)")
        else:
            self.ai_debate = None

        info("💼 포트폴리오 매니저 초기화 완료")
        info(f"   총 예산: {self.total_budget:,}원")
        info(f"   최대 코인 수: {self.max_coins}개")
        info(f"   최소 점수 기준: {self.min_score}점")
        if AI_AVAILABLE:
            info(f"   💳 AI 크레딧: {credit_system.get_remaining()}/{credit_system.daily_limit}")

    async def scan_all_coins(self):
        """
        전체 KRW 시장 스캔 → 상위 10개 후보 선정

        Returns:
            list: [
                {
                    'ticker': 'KRW-BTC',
                    'score': 85.5,
                    'volume_24h': 1000000000,
                    'change_24h': 3.2,
                    'technical_score': 3.5,
                    'momentum': 'STRONG_UP',
                    'volatility': 0.05
                },
                ...
            ]
        """
        try:
            info("\n" + "=" * 60)
            info("🔍 전체 시장 스캔 시작")
            info("=" * 60)

            # 모든 KRW 코인 가져오기
            all_tickers = await asyncio.to_thread(pyupbit.get_tickers, fiat="KRW")

            if not all_tickers:
                warning("⚠️ 코인 목록 조회 실패")
                return []

            # 제외 코인 필터링
            valid_tickers = [
                t for t in all_tickers
                if t not in self.excluded_coins
            ]

            info(f"📊 스캔 대상: {len(valid_tickers)}개 코인")

            # 각 코인 분석
            analyzed_coins = []
            failed_count = 0

            for ticker in valid_tickers:
                try:
                    coin_data = await self._analyze_coin(ticker)

                    if coin_data and coin_data['score'] >= self.min_score:
                        analyzed_coins.append(coin_data)
                    else:
                        failed_count += 1

                except Exception as e:
                    failed_count += 1
                    continue

            info(f"✅ 분석 완료: {len(analyzed_coins)}개 유효 (실패: {failed_count}개)")

            if len(analyzed_coins) == 0:
                error("❌ 유효한 코인 0개!")
                return []

            # 점수순 정렬
            analyzed_coins.sort(key=lambda x: x['score'], reverse=True)

            # 상위 10개 선정
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
        """
        개별 코인 분석

        Args:
            ticker: 코인 티커 (예: 'KRW-BTC')

        Returns:
            dict or None: 코인 데이터
        """
        try:
            # 현재가
            current_price = await asyncio.to_thread(
                pyupbit.get_current_price,
                ticker
            )

            if not current_price or current_price < 100:
                return None

            # OHLCV 데이터 (1시간봉 24개)
            df = await asyncio.to_thread(
                pyupbit.get_ohlcv,
                ticker,
                interval='minute60',
                count=24
            )

            if df is None or len(df) < 20:
                return None

            # 거래량 (24시간)
            volume_24h = df['value'].sum()

            if volume_24h < 10_000_000:  # 1000만원 미만 제외
                return None

            # 거래량 비율
            recent_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].iloc[-24:-1].mean()
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0

            # 가격 변화율
            price_change_1h = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]
            price_change_24h = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]

            # 변동성
            volatility = (df['high'] / df['low'] - 1).mean()

            # 기술적 분석
            technical = technical_analyzer.analyze(df)
            technical_score = technical.get('score', 0)

            # 모멘텀 판단
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

            # 종합 점수 (0~100)
            score = 0.0

            # 1. 기술 점수 (40점)
            score += technical_score * 8  # 5점 만점 → 40점

            # 2. 거래량 (30점)
            if volume_24h > 100_000_000_000:  # 1000억+
                score += 30
            elif volume_24h > 50_000_000_000:  # 500억+
                score += 25
            elif volume_24h > 10_000_000_000:  # 100억+
                score += 20
            elif volume_24h > 1_000_000_000:  # 10억+
                score += 15
            else:
                score += 10

            # 3. 모멘텀 (20점)
            if momentum == 'STRONG_UP':
                score += 20
            elif momentum == 'UP':
                score += 15
            elif momentum == 'NEUTRAL':
                score += 10
            else:
                score += 5

            # 4. 변동성 (10점)
            if 0.02 < volatility < 0.10:  # 2~10% 이상적
                score += 10
            elif 0.01 < volatility < 0.15:
                score += 7
            else:
                score += 5

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
        """
        🤖 AI가 포트폴리오 선택 (압축 언어 + 토론)

        Args:
            top_10_candidates: 상위 10개 후보

        Returns:
            {
                'selected': [
                    {
                        'ticker': 'KRW-BTC',
                        'allocation': 0.4,
                        'reasoning': '...'
                    },
                    ...
                ],
                'ai_confidence': 0.85,
                'reasoning': '전체 전략...',
                'protocol_version': 'v1.2'
            }
        """
        try:
            info("\n" + "=" * 60)
            info("🤖 AI 포트폴리오 자문 시작")
            info("=" * 60)

            # 1. 크레딧 체크
            if not credit_system.can_use('debate'):
                warning("⚠️ AI 크레딧 부족! 기본 알고리즘 사용")
                return self._default_ai_selection(top_10_candidates)

            # 2. 프롬프트 작성 (압축 언어 사용)
            prompt = self._build_ai_prompt(top_10_candidates)

            # 3. AI 토론 실행 (압축 언어 + 진화)
            info(f"💬 AI 토론 시작 (3 라운드, 압축 언어 활성화)")
            info(f"💳 크레딧 소비: 3 (토론 2 + 진화 체크 1)")

            credit_system.use_credit('debate', '포트폴리오 선택 토론')

            debate_result = await self.ai_debate.start_debate(
                topic=f"포트폴리오 선택 (예산: {self.total_budget:,}원)",
                context=prompt,
                num_rounds=3
            )

            if not debate_result or not debate_result.get('consensus'):
                warning("⚠️ AI 토론 실패")
                return self._default_ai_selection(top_10_candidates)

            # 4. 결과 파싱
            ai_response = self._parse_ai_response(
                debate_result['consensus'],
                top_10_candidates
            )

            # 5. 출력
            info(f"\n✅ AI 선택 완료!")
            info(f"   선택: {len(ai_response['selected'])}개 코인")
            info(f"   신뢰도: {ai_response['ai_confidence'] * 100:.0f}%")
            info(f"   프로토콜: {ai_response.get('protocol_version', 'v1.0')}")
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

    def _build_ai_prompt(self, candidates):
        """AI 프롬프트 작성 (압축 언어 버전)"""

        # 후보 요약 (압축)
        candidates_text = "\n".join([
            f"{i+1}. {c['ticker']}: S={c['score']:.1f} "
            f"V24={c['volume_24h']/1e9:.1f}B Δ24={c['change_24h']:+.1f}% "
            f"T={c['technical_score']:.1f} M={c['momentum']}"
            for i, c in enumerate(candidates)
        ])

        prompt = f"""
TASK: Select 3-5 coins from top 10 for portfolio (Budget: {self.total_budget:,} KRW)

CANDIDATES:
{candidates_text}

REQUIREMENTS:
1. Choose 3-5 coins
2. Allocate % (total=100%)
3. Risk diversification
4. Max profit potential

OUTPUT (JSON only):
{{
  "sel": [
    {{"tkr": "KRW-BTC", "pct": 0.4, "why": "reason"}},
    ...
  ],
  "strat": "overall strategy",
  "conf": 0.85
}}

Use compressed language. Think step-by-step.
"""
        return prompt

    def _parse_ai_response(self, consensus_text, candidates):
        """AI 응답 파싱"""
        try:
            # JSON 추출
            start = consensus_text.find('{')
            end = consensus_text.rfind('}') + 1

            if start == -1 or end == 0:
                warning("⚠️ JSON 형식 없음")
                return self._default_ai_selection(candidates)

            json_str = consensus_text[start:end]
            data = json.loads(json_str)

            # 압축 형식 지원
            selected_key = 'sel' if 'sel' in data else 'selected'
            strategy_key = 'strat' if 'strat' in data else 'strategy'
            conf_key = 'conf' if 'conf' in data else 'confidence'

            selected = data.get(selected_key, [])

            if not selected:
                warning("⚠️ 선택 코인 없음")
                return self._default_ai_selection(candidates)

            # 변환
            result = {
                'selected': [],
                'ai_confidence': data.get(conf_key, 0.7),
                'reasoning': data.get(strategy_key, 'AI 포트폴리오 전략'),
                'protocol_version': self.ai_debate.protocol.version
            }

            total_allocation = 0.0

            for item in selected:
                ticker = item.get('tkr') or item.get('ticker')
                allocation = item.get('pct') or item.get('allocation', 0)
                reasoning = item.get('why') or item.get('reasoning', '')

                if ticker and allocation > 0:
                    result['selected'].append({
                        'ticker': ticker,
                        'allocation': allocation,
                        'reasoning': reasoning
                    })
                    total_allocation += allocation

            # 비율 정규화
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

        # 상위 3개 선택
        top_3 = candidates[:3]

        # 점수 비례 배분
        total_score = sum(c['score'] for c in top_3)

        result = {
            'selected': [],
            'ai_confidence': 0.6,
            'reasoning': '기본 알고리즘: 점수 기반 상위 3개',
            'protocol_version': 'v0.0 (No AI)'
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
        전체 시장 분석 + AI 자문 + 자금 배분

        Returns:
            {
                'allocations': {
                    'KRW-BTC': {
                        'budget': 20000,
                        'allocation': 0.4,
                        'score': 85.5,
                        'reasoning': '...'
                    },
                    ...
                },
                'total_analyzed': 200,
                'ai_used': True,
                'protocol_version': 'v1.2'
            }
        """
        try:
            info("\n" + "=" * 60)
            info("💼 포트폴리오 분석 + AI 자문")
            info("=" * 60)

            # 1. 전체 시장 스캔 → 상위 10개
            top_10 = await self.scan_all_coins()

            if not top_10 or len(top_10) == 0:
                error("❌ 유효한 후보 없음")
                return None

            # 2. AI 선택 (압축 언어 + 토론)
            if AI_AVAILABLE and credit_system.get_remaining() >= 3:
                ai_result = await self.ai_select_portfolio(top_10)
            else:
                warning("⚠️ AI 미사용 (크레딧 부족 또는 비활성)")
                ai_result = self._default_ai_selection(top_10)

            if not ai_result or not ai_result.get('selected'):
                error("❌ AI 선택 실패")
                return None

            # 3. 예산 배분
            allocations = {}

            info(f"\n💰 자금 배분:")

            for coin_info in ai_result['selected']:
                ticker = coin_info['ticker']
                allocation_pct = coin_info['allocation']
                budget = int(self.total_budget * allocation_pct)

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
                'ai_used': AI_AVAILABLE,
                'ai_confidence': ai_result.get('ai_confidence', 0),
                'protocol_version': ai_result.get('protocol_version', 'v0.0'),
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
    """
    동적 워커 관리자

    - 워커 동적 생성/제거
    - 자금 배분 관리
    """

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.active_workers = {}  # {ticker: task}
        self.worker_budgets = {}  # {ticker: budget}

        info("⚙️ 동적 워커 매니저 초기화")

    async def update_workers(self, allocations):
        """
        워커 업데이트 (추가/제거/예산변경)

        Args:
            allocations: 새로운 배분 {ticker: amount}
        """
        try:
            current_coins = set(self.active_workers.keys())
            target_coins = set(allocations.keys())

            # 추가할 코인
            coins_to_add = target_coins - current_coins

            # 제거할 코인
            coins_to_remove = current_coins - target_coins

            # 유지할 코인 (예산 변경)
            coins_to_update = current_coins & target_coins

            info(f"\n⚙️ 워커 업데이트:")
            info(f"   추가: {len(coins_to_add)}개")
            info(f"   제거: {len(coins_to_remove)}개")
            info(f"   유지: {len(coins_to_update)}개")

            # 1. 워커 추가
            for ticker in coins_to_add:
                budget = allocations[ticker]
                await self.add_worker(ticker, budget)

            # 2. 워커 제거
            for ticker in coins_to_remove:
                await self.remove_worker(ticker)

            # 3. 예산 업데이트
            for ticker in coins_to_update:
                new_budget = allocations[ticker]
                old_budget = self.worker_budgets.get(ticker, 0)

                if new_budget != old_budget:
                    self.worker_budgets[ticker] = new_budget
                    info(f"💰 [{ticker}] 예산 변경: {old_budget:,} → {new_budget:,}원")

        except Exception as e:
            error(f"❌ 워커 업데이트 오류: {e}")

    async def add_worker(self, ticker, budget):
        """
        워커 추가

        Args:
            ticker: 코인 티커
            budget: 배분 예산
        """
        if ticker in self.active_workers:
            warning(f"⚠️ [{ticker}] 이미 워커 존재")
            return

        try:
            info(f"🆕 [{ticker}] 워커 생성 (예산: {budget:,}원)")

            # 워커 태스크 생성
            task = asyncio.create_task(
                self.bot.spot_worker(ticker, budget)
            )

            self.active_workers[ticker] = task
            self.worker_budgets[ticker] = budget

            info(f"✅ [{ticker}] 워커 시작 완료")

        except Exception as e:
            error(f"❌ [{ticker}] 워커 생성 오류: {e}")

    async def remove_worker(self, ticker):
        """
        워커 제거

        Args:
            ticker: 코인 티커
        """
        if ticker not in self.active_workers:
            return

        try:
            info(f"🗑️ [{ticker}] 워커 제거 중...")

            # 워커 중단
            task = self.active_workers[ticker]
            task.cancel()

            # 제거
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

    pm = PortfolioManager(total_budget=50000)

    # 가짜 시장 상태
    market_sentiment = {
        'status': 'BULLISH',
        'score': 3.5
    }

    # 분석 및 배분
    result = await pm.analyze_and_allocate(market_sentiment)

    if result:
        print("\n✅ 테스트 성공!")
        print(f"   분석 코인: {result['total_analyzed']}개")
        print(f"   배분 코인: {len(result['allocations'])}개")
        print(f"   AI 사용: {'✅' if result['ai_used'] else '❌'}")
        if result['ai_used']:
            print(f"   신뢰도: {result['ai_confidence'] * 100:.0f}%")
            print(f"   프로토콜: {result['protocol_version']}")
    else:
        print("\n❌ 테스트 실패")


if __name__ == "__main__":
    asyncio.run(test_portfolio_manager())