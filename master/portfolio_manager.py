"""
포트폴리오 매니저 (Portfolio Manager)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[핵심 기능]
1. 전체 시장 스캔 (모든 KRW 코인)
2. 거래량 급증 코인 발굴
3. 코인별 점수 계산 (기술적 + 거래량)
4. 동적 자금 배분 (좋은 코인에 더 많이)
5. 포트폴리오 리밸런싱
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import pyupbit
import asyncio
from datetime import datetime, timedelta
from config.master_config import SPOT_BUDGET
from utils.logger import info, warning, error
from analysis.technical import technical_analyzer


class PortfolioManager:
    """
    포트폴리오 매니저

    - 전체 시장 분석
    - 거래량 기반 코인 발굴
    - 동적 자금 배분
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

        info("💼 포트폴리오 매니저 초기화 완료")
        info(f"   총 예산: {self.total_budget:,}원")
        info(f"   최대 코인 수: {self.max_coins}개")
        info(f"   최소 점수 기준: {self.min_score}점")

    async def scan_all_coins(self):
        """
        전체 KRW 시장 스캔

        Returns:
            list: 분석된 코인 리스트
        """
        try:
            info("\n🔍 전체 시장 스캔 시작...")

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

            for ticker in valid_tickers[:50]:  # 상위 50개만 (시간 절약)
                try:
                    coin_data = await self._analyze_coin(ticker)

                    if coin_data:
                        analyzed_coins.append(coin_data)

                except Exception as e:
                    # 개별 코인 오류는 무시
                    continue

            info(f"✅ 분석 완료: {len(analyzed_coins)}개 코인")

            return analyzed_coins

        except Exception as e:
            error(f"❌ 전체 스캔 오류: {e}")
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

            if df is None or len(df) < 10:
                return None

            # 거래량 분석
            recent_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].iloc[-24:-1].mean()
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0

            # 가격 변화율
            price_change_1h = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]
            price_change_24h = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]

            # 기술적 분석
            technical = technical_analyzer.analyze(df)

            return {
                'ticker': ticker,
                'price': current_price,
                'volume_ratio': volume_ratio,
                'price_change_1h': price_change_1h,
                'price_change_24h': price_change_24h,
                'technical_score': technical.get('score', 0),
                'df': df
            }

        except Exception as e:
            return None

    def calculate_coin_scores(self, analyzed_coins):
        """
        코인별 점수 계산

        Args:
            analyzed_coins: 분석된 코인 리스트

        Returns:
            dict: {ticker: score}
        """
        scores = {}

        for coin in analyzed_coins:
            ticker = coin['ticker']

            # 점수 계산 (0~100)
            score = 0.0

            # 1. 거래량 (40점)
            volume_score = min(coin['volume_ratio'] * 10, 40)
            score += volume_score

            # 2. 기술적 분석 (30점)
            tech_score = coin['technical_score'] * 6  # 5점 만점 → 30점
            score += tech_score

            # 3. 가격 모멘텀 (20점)
            momentum_score = 0
            if coin['price_change_1h'] > 0.02:  # 1시간 +2%
                momentum_score += 10
            if coin['price_change_24h'] > 0.05:  # 24시간 +5%
                momentum_score += 10
            score += momentum_score

            # 4. 코어 코인 보너스 (10점)
            if ticker in self.core_coins:
                score += 10

            scores[ticker] = score

        return scores

    def detect_volume_surge_coins(self, analyzed_coins):
        """
        거래량 급증 코인 감지

        Args:
            analyzed_coins: 분석된 코인 리스트

        Returns:
            list: 거래량 급증 코인
        """
        surge_coins = []

        for coin in analyzed_coins:
            ticker = coin['ticker']
            volume_ratio = coin['volume_ratio']

            # 거래량 급증 (3배 이상)
            if volume_ratio >= self.volume_surge_threshold:
                surge_coins.append({
                    'ticker': ticker,
                    'volume_ratio': volume_ratio,
                    'price_change_1h': coin['price_change_1h']
                })

                info(f"🔥 [{ticker}] 거래량 급증! {volume_ratio:.1f}배")

        return surge_coins

    def calculate_allocation(self, coin_scores, market_sentiment):
        """
        동적 자금 배분 계산

        Args:
            coin_scores: 코인별 점수
            market_sentiment: 시장 상태

        Returns:
            dict: {ticker: amount}
        """
        # 점수 정렬 (높은 순)
        sorted_coins = sorted(
            coin_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # 상위 N개 선택
        top_coins = sorted_coins[:self.max_coins]

        # 총 점수 계산
        total_score = sum(score for _, score in top_coins)

        if total_score == 0:
            warning("⚠️ 총 점수가 0 - 기본 배분 사용")
            return self._default_allocation()

        # 점수 비율로 자금 배분
        allocations = {}

        for ticker, score in top_coins:
            # 기본 비율
            ratio = score / total_score

            # 최소/최대 제한
            ratio = max(ratio, self.min_allocation)
            ratio = min(ratio, self.max_allocation)

            # 코어 코인 보정
            if ticker in self.core_coins:
                ratio = max(ratio, 0.20)  # 최소 20%

            # 금액 계산
            amount = int(self.total_budget * ratio)
            allocations[ticker] = amount

        # 합계 조정 (정확히 total_budget)
        total_allocated = sum(allocations.values())
        if total_allocated != self.total_budget:
            # 가장 큰 코인에서 차액 조정
            largest_coin = max(allocations, key=allocations.get)
            diff = self.total_budget - total_allocated
            allocations[largest_coin] += diff

        return allocations

    def _default_allocation(self):
        """기본 배분 (코어 코인만)"""
        return {
            'KRW-BTC': int(self.total_budget * 0.6),  # 60%
            'KRW-ETH': int(self.total_budget * 0.4)   # 40%
        }

    def analyze_and_allocate(self, market_sentiment):
        """전체 시장 분석 + 자금 배분"""
        try:
            info("\n" + "=" * 60)
            info("💼 포트폴리오 분석 시작")
            info("=" * 60)

            # 1. 전체 코인 목록
            all_coins = pyupbit.get_tickers(fiat="KRW")
            info(f"\n🔍 전체 시장 스캔 시작...")
            info(f"📊 스캔 대상: {len(all_coins)}개 코인")

            valid_coins = []
            debug_count = 0
            max_debug = 10  # 상위 10개만 상세 로그

            failed_reasons = {
                'data_load_failed': 0,
                'insufficient_data': 0,
                'score_too_low': 0,
                'exception': 0
            }

            # 2. 각 코인 분석
            for i, coin in enumerate(all_coins):
                try:
                    # 데이터 로드
                    df = pyupbit.get_ohlcv(coin, interval="day", count=30)

                    if df is None or len(df) == 0:
                        failed_reasons['data_load_failed'] += 1
                        if debug_count < max_debug:
                            warning(f"❌ [{coin}] 데이터 로드 실패 (None)")
                            debug_count += 1
                        continue

                    if len(df) < 30:
                        failed_reasons['insufficient_data'] += 1
                        if debug_count < max_debug:
                            warning(f"❌ [{coin}] 데이터 부족 ({len(df)}일)")
                            debug_count += 1
                        continue

                    # 점수 계산
                    score_result = self._calculate_coin_score(coin, df, market_sentiment)

                    if score_result is None:
                        failed_reasons['exception'] += 1
                        continue

                    score = score_result['total_score']

                    # 상세 로그 (처음 10개만)
                    if debug_count < max_debug:
                        info(f"\n📊 [{coin}] 분석 결과:")
                        info(f"   거래량: {score_result['volume']:,.0f}원 → {score_result['volume_score']}점")
                        info(f"   변동성: {score_result['volatility'] * 100:.2f}% → {score_result['volatility_score']}점")
                        info(f"   추세: {score_result['trend_score']}점")
                        info(f"   총점: {score:.2f}점 (기준: {self.min_score})")
                        debug_count += 1

                    # 최소 점수 체크
                    if score < self.min_score:
                        failed_reasons['score_too_low'] += 1
                        if debug_count < max_debug:
                            warning(f"❌ [{coin}] 점수 미달 ({score:.2f} < {self.min_score})")
                            debug_count += 1
                        continue

                    valid_coins.append({
                        'symbol': coin,
                        'score': score,
                        'volume_24h': score_result['volume'],
                        'volatility': score_result['volatility']
                    })

                except Exception as e:
                    failed_reasons['exception'] += 1
                    if debug_count < max_debug:
                        error(f"❌ [{coin}] 예외 발생: {type(e).__name__}: {str(e)}")
                        debug_count += 1
                    continue

            # 3. 스캔 결과 통계
            info("\n" + "=" * 60)
            info("📊 스캔 결과 통계")
            info("=" * 60)
            info(f"✅ 유효 코인: {len(valid_coins)}개")
            info(f"❌ 실패 내역:")
            info(f"   - 데이터 로드 실패: {failed_reasons['data_load_failed']}개")
            info(f"   - 데이터 부족 (<30일): {failed_reasons['insufficient_data']}개")
            info(f"   - 점수 미달 (<{self.min_score}): {failed_reasons['score_too_low']}개")
            info(f"   - 예외 발생: {failed_reasons['exception']}개")
            info(f"📊 총 분석: {len(all_coins)}개")
            info("=" * 60)

            # 유효 코인 없음
            if not valid_coins:
                error("\n❌ 치명적 오류: 유효한 코인 0개")
                error(f"   시장 감정: {market_sentiment}")
                error(f"   최소 점수 기준: {self.min_score}")
                error("\n💡 점검 사항:")
                error("   1. Upbit API 정상 작동 확인")
                error("   2. 최소 점수 기준 ({self.min_score}) 적절성")
                error("   3. 점수 계산 로직 검토")
                return None

            # 4. 점수 순 정렬
            valid_coins.sort(key=lambda x: x['score'], reverse=True)

            # 5. 상위 코인 출력
            top_n = min(15, len(valid_coins))
            info(f"\n📈 상위 {top_n}개 코인:")
            for i, coin_info in enumerate(valid_coins[:top_n]):
                info(f"  {i + 1}. {coin_info['symbol']}: {coin_info['score']:.2f}점 "
                     f"(거래량: {coin_info['volume_24h'] / 1e9:.1f}억, "
                     f"변동성: {coin_info['volatility'] * 100:.1f}%)")

            # ... 이후 자금 배분 로직은 기존 코드 유지 ...

        except Exception as e:
            error(f"\n❌ 포트폴리오 분석 치명적 오류: {str(e)}")
            import traceback
            error("\n스택 트레이스:")
            error(traceback.format_exc())
            return None

    def should_rebalance(self):
        """
        리밸런싱 필요 여부 판단

        Returns:
            bool: 리밸런싱 필요 여부
        """
        # TODO: 실제 포지션과 목표 배분 비교
        # 지금은 간단히 True
        return True

    def get_allocation(self, ticker):
        """
        특정 코인의 배분 금액

        Args:
            ticker: 코인 티커

        Returns:
            int: 배분 금액
        """
        return self.allocations.get(ticker, 0)

    def get_top_coins(self, n=5):
        """
        상위 N개 코인

        Args:
            n: 개수

        Returns:
            list: 티커 리스트
        """
        return list(self.allocations.keys())[:n]


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

    def _calculate_coin_score(self, coin, df, market_sentiment):
        """코인 점수 계산 (상세 로그 포함)"""
        try:
            score = 0
            result = {
                'volume': 0,
                'volume_score': 0,
                'volatility': 0,
                'volatility_score': 0,
                'trend_score': 0,
                'total_score': 0
            }

            # 1. 거래량 점수 (0-30점)
            if 'value' in df.columns:
                volume_24h = df['value'].iloc[-1]
                result['volume'] = volume_24h

                if volume_24h > 100_000_000_000:  # 1000억+
                    result['volume_score'] = 30
                elif volume_24h > 50_000_000_000:  # 500억+
                    result['volume_score'] = 25
                elif volume_24h > 10_000_000_000:  # 100억+
                    result['volume_score'] = 20
                elif volume_24h > 5_000_000_000:  # 50억+
                    result['volume_score'] = 15
                elif volume_24h > 1_000_000_000:  # 10억+
                    result['volume_score'] = 10
                else:
                    result['volume_score'] = 5

            score += result['volume_score']

            # 2. 변동성 점수 (0-30점)
            if 'high' in df.columns and 'low' in df.columns:
                volatility = (df['high'] / df['low'] - 1).mean()
                result['volatility'] = volatility

                if 0.02 < volatility < 0.10:  # 2-10% (이상적)
                    result['volatility_score'] = 30
                elif 0.01 < volatility < 0.15:  # 1-15%
                    result['volatility_score'] = 20
                elif 0.005 < volatility < 0.20:  # 0.5-20%
                    result['volatility_score'] = 10
                else:
                    result['volatility_score'] = 5

            score += result['volatility_score']

            # 3. 추세 점수 (0-40점)
            if 'close' in df.columns:
                close = df['close']

                # 이동평균
                if len(close) >= 20:
                    ma_20 = close.rolling(20).mean()

                    if close.iloc[-1] > ma_20.iloc[-1]:
                        result['trend_score'] += 20

                    # 상승 추세
                    if close.iloc[-1] > close.iloc[-5]:
                        result['trend_score'] += 10

                    # 강한 상승
                    if close.iloc[-1] > close.iloc[-10]:
                        result['trend_score'] += 10

            score += result['trend_score']

            result['total_score'] = score
            return result

        except Exception as e:
            error(f"❌ [{coin}] 점수 계산 오류: {type(e).__name__}: {str(e)}")
            return None



# ============================================================
# 테스트
# ============================================================

async def test_portfolio_manager():
    """포트폴리오 매니저 테스트"""
    print("🧪 포트폴리오 매니저 테스트\n")

    pm = PortfolioManager(total_budget=600000)

    # 가짜 시장 상태
    market_sentiment = {
        'status': 'BULLISH',
        'score': 3.5
    }

    # 분석 및 배분
    result = await pm.analyze_and_allocate(market_sentiment)

    if result:
        print("\n✅ 테스트 성공!")
        print(f"   분석 코인: {result['analyzed_count']}개")
        print(f"   배분 코인: {len(result['allocations'])}개")
        print(f"   거래량 급증: {len(result['surge_coins'])}개")
    else:
        print("\n❌ 테스트 실패")


if __name__ == "__main__":
    asyncio.run(test_portfolio_manager())