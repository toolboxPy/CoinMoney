"""
CoinMoney 자동매매 봇 (v3.3 - 동적 포트폴리오)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[v3.3 핵심 기능]
1. 📊 동적 포트폴리오 관리 (실시간 잔고 기반)
2. 🔥 거래량 기반 코인 발굴
3. ⚙️ 워커 동적 생성/제거
4. 💰 개별 워커별 독립 예산
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import pyupbit
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from config.master_config import *

# 유틸리티
from utils.logger import info, warning, error, trade_log
from utils.state_manager import state_manager
from utils.performance_tracker import performance_tracker

# 핵심 시스템
from master.global_risk import global_risk
from master.portfolio_manager import PortfolioManager, DynamicWorkerManager
from analysis.technical import technical_analyzer

# 컨트롤러
try:
    from master.controller_v3 import smart_controller as master_controller
    CONTROLLER_VERSION = "v3.3"
    info("✅ 스마트 컨트롤러 v3.3 로드")
except ImportError:
    from master.controller import master_controller
    CONTROLLER_VERSION = "v1.0"
    warning("⚠️ v1.0 컨트롤러 사용 (Fallback)")

# 거래 모듈
from traders.spot_trader import spot_trader
from traders.futures_trader import futures_trader

# 🔥 Strategy Registry + get_strategy
from strategies import (
    strategy_registry,
    futures_strategy_registry,
    get_strategy
)

# 뉴스 수집기
try:
    from utils.news_analyzer import NewsCollector
    news_collector = NewsCollector()
    NEWS_AVAILABLE = True
except:
    NEWS_AVAILABLE = False
    warning("⚠️ 뉴스 수집기 없음")

# ccxt
try:
    import ccxt
    CCXT_AVAILABLE = True
except:
    CCXT_AVAILABLE = False
    warning("⚠️ ccxt 없음 (선물 거래 비활성)")


class CoinMoneyBot:
    """CoinMoney 자동매매 봇 v3.3 (동적 포트폴리오)"""

    def __init__(self):
        """봇 초기화"""
        info("🚀 CoinMoney Bot v3.3 시작!")
        info("=" * 60)
        info(f"📊 컨트롤러: {CONTROLLER_VERSION}")
        info(f"💼 포트폴리오 관리: ✅")
        info(f"🔥 거래량 기반 발굴: ✅")
        info(f"⚙️ 동적 워커: ✅")
        info("=" * 60)

        # ============================================================
        # 1. API 인증
        # ============================================================

        # Upbit 인증
        try:
            self.upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
            info("✅ Upbit API 인증 성공")

            # 🔥 실시간 KRW 잔고 조회
            try:
                krw_balance = self.upbit.get_balance("KRW")
                if krw_balance is not None:
                    info(f"💰 현재 KRW 잔고: {krw_balance:,.0f}원")
                    self.initial_krw_balance = krw_balance
                else:
                    warning("⚠️ KRW 잔고 조회 실패 (None)")
                    self.initial_krw_balance = 0
            except Exception as e:
                error(f"❌ KRW 잔고 조회 오류: {e}")
                self.initial_krw_balance = 0

        except Exception as e:
            error(f"❌ Upbit API 인증 실패: {e}")
            self.upbit = None
            self.initial_krw_balance = 0

        # 바이낸스 선물 인증
        self.binance = None
        if CCXT_AVAILABLE and BINANCE_API_KEY and BINANCE_API_SECRET:
            try:
                self.binance = ccxt.binance({
                    'apiKey': BINANCE_API_KEY,
                    'secret': BINANCE_API_SECRET,
                    'enableRateLimit': True,
                    'options': {'defaultType': 'future'}
                })
                info("✅ 바이낸스 선물 API 인증 성공")
            except Exception as e:
                error(f"❌ 바이낸스 인증 실패: {e}")

        # ============================================================
        # 2. 상태 관리
        # ============================================================

        try:
            state_manager.load_state()
            info("✅ 이전 상태 복구 완료")
        except:
            info("💾 새로운 상태 시작")

        # ============================================================
        # 3. 포트폴리오 & 워커 시스템
        # ============================================================

        # 🔥 포트폴리오 매니저 (동적 예산 - upbit_instance 전달)
        self.portfolio_manager = PortfolioManager(
            upbit_instance=self.upbit,  # ✅ 인스턴스 전달!
            max_coins=5,
            min_score=20.0
        )

        # 동적 워커 매니저
        self.dynamic_workers = DynamicWorkerManager(self)

        info("✅ 포트폴리오 시스템 초기화 완료")

        # ============================================================
        # 4. 시장 감정 상태
        # ============================================================

        self.market_sentiment = {
            'status': 'UNKNOWN',
            'score': 0.0,
            'btc_trend': 'NEUTRAL',
            'trading_allowed': True,
            'last_update': None
        }

        # ============================================================
        # 5. 주기 설정 (초 단위)
        # ============================================================

        # CHECK_INTERVALS에서 가져오기
        try:
            self.spot_check_interval = CHECK_INTERVALS.get('spot', 30)
        except:
            self.spot_check_interval = 30  # 기본값 30초

        self.portfolio_interval = 1800      # 포트폴리오 재분석 (30분)
        self.market_sentiment_interval = 300  # 시장 감정 업데이트 (5분)

        # ============================================================
        # 6. 통계 & 추적
        # ============================================================

        self.spot_loop_counts = {}          # 코인별 분석 횟수
        self.futures_loop_counts = {}       # 선물 분석 횟수
        self.last_news_check = None         # 마지막 뉴스 체크 시간
        self.last_portfolio_update = None   # 마지막 포트폴리오 업데이트

        # ============================================================
        # 완료
        # ============================================================

        info("=" * 60)
        info("✅ CoinMoney Bot 초기화 완료!")
        info(f"   💰 초기 KRW 잔고: {self.initial_krw_balance:,.0f}원")  # 🔥 수정!
        info(f"   ⏰ 포트폴리오 주기: {self.portfolio_interval // 60}분")
        info(f"   📊 워커 체크 주기: {self.spot_check_interval}초")
        info(f"   🌍 시장 감정 주기: {self.market_sentiment_interval // 60}분")
        info("=" * 60)

    def check_connection(self):
        """연결 확인"""
        if self.upbit is None:
            return False

        try:
            balance = self.upbit.get_balance("KRW")
            info(f"✅ 현물 연결 성공! KRW 잔고: {balance:,}원")

            if self.binance:
                try:
                    self.binance.fetch_balance()
                    info(f"✅ 선물 연결 성공!")
                except:
                    warning("⚠️ 선물 연결 실패")

            return True
        except Exception as e:
            error(f"❌ 연결 실패: {e}")
            return False

    # ========================================
    # 🔥 포트폴리오 관리 워커
    # ========================================

    async def portfolio_worker(self):
        """포트폴리오 관리 워커 (30분 주기)"""

        info("💼 포트폴리오 워커 시작")

        while True:
            try:
                info("\n" + "=" * 60)
                info("💼 포트폴리오 분석 시작")
                info("=" * 60)

                # 1. 시장 감정
                market_sentiment = self.market_sentiment

                # 2. 전체 시장 분석 + 자금 배분
                result = await self.portfolio_manager.analyze_and_allocate(
                    market_sentiment
                )

                if not result:
                    warning("⚠️ 포트폴리오 분석 실패")
                    await asyncio.sleep(300)
                    continue

                # 3. Budget 추출
                allocations = result['allocations']

                # dict에서 숫자만 추출
                budget_only = {
                    ticker: alloc['budget']
                    for ticker, alloc in allocations.items()
                }

                # 4. 워커 업데이트 (추가/제거/변경)
                await self.dynamic_workers.update_workers(budget_only)

                # 5. 완료
                info(f"\n✅ 포트폴리오 업데이트 완료")
                info(f"   활성 워커: {len(budget_only)}개")
                info(f"   다음 분석: {self.portfolio_interval // 60}분 후")
                info("=" * 60 + "\n")

                # 6. 대기 (30분)
                await asyncio.sleep(self.portfolio_interval)

            except asyncio.CancelledError:
                info("🛑 포트폴리오 워커 종료")
                break

            except Exception as e:
                error(f"\n❌ 포트폴리오 워커 오류: {e}")
                import traceback
                error(traceback.format_exc())

                # 5분 후 재시도
                await asyncio.sleep(300)

    # ========================================
    # 시장 감정 워커
    # ========================================

    async def analyze_market_sentiment(self):
        """전체 시장 감정 분석"""
        try:
            major_coins = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-BNB']
            changes = []

            for coin in major_coins:
                try:
                    df = await asyncio.to_thread(
                        pyupbit.get_ohlcv,
                        coin,
                        interval='minute60',
                        count=2
                    )

                    if df is not None and len(df) >= 2:
                        change = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]
                        changes.append(change * 100)
                except:
                    continue

            if not changes:
                return None

            avg_change = sum(changes) / len(changes)

            # 시장 상태 판단
            if avg_change > 5:
                status = 'BULL_RUN'
                trading_allowed = True
            elif avg_change > 2:
                status = 'BULLISH'
                trading_allowed = True
            elif avg_change > -2:
                status = 'NEUTRAL'
                trading_allowed = True
            elif avg_change > -5:
                status = 'BEARISH'
                trading_allowed = False
            else:
                status = 'CRASH'
                trading_allowed = False

            btc_change = changes[0] if len(changes) > 0 else 0
            if btc_change > 3:
                btc_trend = 'STRONG_UP'
            elif btc_change > 1:
                btc_trend = 'UP'
            elif btc_change > -1:
                btc_trend = 'NEUTRAL'
            elif btc_change > -3:
                btc_trend = 'DOWN'
            else:
                btc_trend = 'STRONG_DOWN'

            return {
                'status': status,
                'score': avg_change,
                'btc_trend': btc_trend,
                'trading_allowed': trading_allowed,
                'last_update': datetime.now()
            }

        except Exception as e:
            error(f"❌ 시장 감정 분석 오류: {e}")
            return None

    async def market_sentiment_worker(self):
        """시장 감정 감시 워커 (5분마다)"""
        info("🌍 시장 감정 워커 시작")

        while True:
            try:
                info("\n" + "="*60)
                info("🌍 전체 시장 분석 중...")
                info("="*60)

                sentiment = await self.analyze_market_sentiment()

                if sentiment:
                    self.market_sentiment.update(sentiment)

                    status_emoji = {
                        'BULL_RUN': '🚀',
                        'BULLISH': '📈',
                        'NEUTRAL': '➡️',
                        'BEARISH': '📉',
                        'CRASH': '💥'
                    }

                    emoji = status_emoji.get(sentiment['status'], '❓')
                    info(f"{emoji} 시장 상태: {sentiment['status']}")
                    info(f"📊 평균 변화: {sentiment['score']:+.2f}%")
                    info(f"₿ BTC 추세: {sentiment['btc_trend']}")
                    info(f"🎯 거래 허용: {'✅' if sentiment['trading_allowed'] else '❌'}")

                    if sentiment['status'] in ['CRASH', 'BEARISH']:
                        warning(f"⚠️ 시장 {sentiment['status']}! 모든 거래 중단!")

                info("="*60)

                await asyncio.sleep(self.market_sentiment_interval)

            except asyncio.CancelledError:
                info("🛑 시장 감정 워커 종료")
                break

            except Exception as e:
                error(f"⚠️ 시장 감정 워커 오류: {e}")
                await asyncio.sleep(60)

    # ========================================
    # 현물 거래
    # ========================================

    async def get_market_data(self, coin):
        """시장 데이터 수집 (비동기)"""
        try:
            price = await asyncio.to_thread(pyupbit.get_current_price, coin)
            if price is None:
                warning(f"⚠️ {coin} 가격 조회 실패")
                return None

            df = await asyncio.to_thread(
                pyupbit.get_ohlcv,
                coin,
                interval="minute60",
                count=200
            )

            if df is None or len(df) < 20:
                warning(f"⚠️ {coin} 차트 데이터 부족")
                return None

            technical = technical_analyzer.analyze(df)

            return {
                'coin': coin,
                'price': price,
                'df': df,
                'technical': technical
            }

        except Exception as e:
            error(f"❌ {coin} 시장 데이터 수집 오류: {e}")
            return None

    async def get_news_data(self):
        """뉴스 데이터 수집"""
        if not NEWS_AVAILABLE:
            return None

        now = datetime.now()

        if self.last_news_check and (now - self.last_news_check) < timedelta(minutes=10):
            return None

        try:
            news_list = await asyncio.to_thread(
                news_collector.fetch_crypto_news,
                hours=1,
                max_results=10
            )

            if news_list:
                self.last_news_check = now
                urgency = sum(n.get('impact', 5) for n in news_list) / len(news_list)

                return {
                    'urgency': urgency,
                    'count_1h': len(news_list),
                    'emergency': any(n.get('impact', 0) >= 9 for n in news_list),
                    'list': news_list
                }
        except Exception as e:
            warning(f"⚠️ 뉴스 수집 오류: {e}")

        return None

    async def get_position_data(self, coin):
        """포지션 데이터 수집"""
        try:
            ticker = coin.split('-')[1]
            balance = await asyncio.to_thread(self.upbit.get_balance, ticker)
            avg_price = await asyncio.to_thread(self.upbit.get_avg_buy_price, ticker)
            current_price = await asyncio.to_thread(pyupbit.get_current_price, coin)

            if balance > 0 and avg_price > 0:
                pnl_ratio = (current_price - avg_price) / avg_price

                return {
                    'in_position': True,
                    'balance': balance,
                    'avg_price': avg_price,
                    'current_price': current_price,
                    'pnl_ratio': pnl_ratio,
                    'stop_loss': PROFIT_TARGETS['spot_minute30']['stop_loss'],
                    'take_profit': PROFIT_TARGETS['spot_minute30']['take_profit_2']
                }

            return {'in_position': False}

        except Exception as e:
            warning(f"⚠️ {coin} 포지션 데이터 오류: {e}")
            return None

    async def execute_spot_strategies(self, coin, analysis_result, budget):
        """
        현물 전략 실행

        Args:
            coin: 거래 코인
            analysis_result: 마스터 분석 결과
            budget: 이 코인에 배분된 예산
        """
        if not analysis_result.get('trading_allowed', False):
            return

        spot_strategies = analysis_result['strategies'].get('spot', [])

        if not spot_strategies:
            # 전략 없으면 포지션 청산
            state = state_manager.state['spot']
            if state['in_position']:
                info(f"📤 [{coin}] 모든 전략 비활성 → 포지션 청산")
                await asyncio.to_thread(
                    spot_trader.sell_all,
                    coin,
                    reason="전략 비활성화"
                )
            return

        # 전략 실행
        for strategy_name in spot_strategies:
            try:
                # 전략 가져오기
                strategy = get_strategy(strategy_name)

                if not strategy:
                    warning(f"⚠️ 알 수 없는 전략: {strategy_name}")
                    continue

                # execute() 메서드 호출
                result = await asyncio.to_thread(strategy.execute, coin)

                if not result:
                    continue

                action = result.get('action')

                # 매수
                if action == 'BUY':
                    trade_amount = budget * 0.3  # 예산의 30%

                    info(f"💰 [{coin}] {strategy_name} 매수 신호 (예산: {budget:,}원)")
                    await asyncio.to_thread(
                        spot_trader.buy,
                        coin,
                        trade_amount,
                        reason=f"{strategy_name} 매수"
                    )

                # 매도
                elif action == 'SELL':
                    info(f"📤 [{coin}] {strategy_name} 매도 신호")
                    await asyncio.to_thread(
                        spot_trader.sell_all,
                        coin,
                        reason=f"{strategy_name} 매도"
                    )

            except Exception as e:
                error(f"❌ [{coin}] {strategy_name} 실행 오류: {e}")
                import traceback
                error(traceback.format_exc())

    async def spot_worker(self, coin, budget=None):
        """
        현물 코인 전용 워커 (독립 실행 + 개별 예산)

        Args:
            coin: 거래 코인
            budget: 배분된 예산
        """
        loop_count = 0

        info(f"🟢 [{coin}] 현물 워커 시작 (예산: {budget:,}원)" if budget else f"🟢 [{coin}] 현물 워커 시작")

        while True:
            try:
                loop_count += 1
                self.spot_loop_counts[coin] = loop_count

                # 예산 조회 (동적 업데이트)
                if budget is None:
                    budget = self.dynamic_workers.get_worker_budget(coin)

                # 시장 감정 체크
                if not self.market_sentiment['trading_allowed']:
                    warning(f"⚠️ [{coin}] 시장 {self.market_sentiment['status']} → 거래 중단!")

                    state = state_manager.state['spot']
                    if state['in_position'] and state['positions'].get(coin):
                        warning(f"🚨 [{coin}] 긴급 청산 실행!")
                        await asyncio.to_thread(
                            spot_trader.sell_all,
                            coin,
                            reason=f"시장 {self.market_sentiment['status']}"
                        )

                    await asyncio.sleep(self.spot_check_interval)
                    continue

                info(f"\n{'='*60}")
                info(f"🔍 [{coin}] 분석 시작 (#{loop_count})")
                info(f"🌍 시장: {self.market_sentiment['status']} ({self.market_sentiment['score']:+.1f}%)")
                info(f"💰 배분 예산: {budget:,}원")
                info(f"{'='*60}")

                # 시장 데이터
                market_data = await self.get_market_data(coin)
                if not market_data:
                    await asyncio.sleep(self.spot_check_interval)
                    continue

                info(f"💰 현재가: {market_data['price']:,.0f}원")
                info(f"📊 기술 점수: {market_data['technical'].get('score', 0):.1f}/5")

                # 뉴스
                news_data = await self.get_news_data()
                if news_data:
                    info(f"📰 뉴스: {news_data['count_1h']}개 (중요도: {news_data['urgency']:.1f}/10)")

                # 포지션
                position_data = await self.get_position_data(coin)
                if position_data and position_data.get('in_position'):
                    pnl = position_data['pnl_ratio'] * 100
                    info(f"📈 포지션: {pnl:+.2f}%")

                # 마스터 분석
                info("\n🧠 마스터 분석 중...")
                market_data['market_sentiment'] = self.market_sentiment

                analysis_result = await asyncio.to_thread(
                    master_controller.analyze_and_adjust,
                    market_data,
                    news_data=news_data,
                    position_data=position_data
                )

                if not analysis_result:
                    warning("⚠️ 분석 실패")
                    await asyncio.sleep(self.spot_check_interval)
                    continue

                # 전략 실행 (예산 전달)
                info("\n🎯 전략 실행 중...")
                await self.execute_spot_strategies(coin, analysis_result, budget)

                info(f"{'='*60}\n")

                await asyncio.sleep(self.spot_check_interval)

            except asyncio.CancelledError:
                info(f"🛑 [{coin}] 워커 종료")
                break

            except Exception as e:
                error(f"⚠️ [{coin}] 워커 오류: {e}")
                import traceback
                error(traceback.format_exc())
                await asyncio.sleep(10)

    # ========================================
    # 선물 거래 (기존과 동일)
    # ========================================

    async def get_futures_market_data(self, symbol):
        """선물 시장 데이터 수집"""
        if not self.binance:
            return None

        try:
            ticker = await asyncio.to_thread(self.binance.fetch_ticker, symbol)
            price = ticker['last']

            ohlcv = await asyncio.to_thread(
                self.binance.fetch_ohlcv,
                symbol,
                timeframe='1h',
                limit=200
            )

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            technical = technical_analyzer.analyze(df)

            return {
                'symbol': symbol,
                'price': price,
                'df': df,
                'technical': technical
            }

        except Exception as e:
            error(f"❌ {symbol} 선물 데이터 수집 오류: {e}")
            return None

    async def futures_worker(self, symbol):
        """선물 워커 (기존과 동일)"""
        if not self.binance:
            return

        info(f"🔵 [{symbol}] 선물 워커 시작")

        # TODO: 선물 로직 (기존 코드 유지)
        while True:
            await asyncio.sleep(CHECK_INTERVALS.get('futures', 300))

    # ========================================
    # 유지보수
    # ========================================

    async def maintenance_task(self):
        """주기적 유지보수"""
        info("🛠️ 유지보수 태스크 시작")

        while True:
            try:
                await asyncio.sleep(600)

                try:
                    state_manager.save_state()
                    info("💾 상태 저장 완료")
                except:
                    warning("⚠️ 상태 저장 실패")

                if sum(self.spot_loop_counts.values()) % 60 == 0:
                    self._print_statistics()

            except asyncio.CancelledError:
                info("🛑 유지보수 태스크 종료")
                break

            except Exception as e:
                error(f"⚠️ 유지보수 오류: {e}")

    def _print_statistics(self):
        """통계 출력"""
        info("\n" + "=" * 60)
        info("📊 봇 통계")
        info("=" * 60)

        # 시장 감정
        status_emoji = {
            'BULL_RUN': '🚀',
            'BULLISH': '📈',
            'NEUTRAL': '➡️',
            'BEARISH': '📉',
            'CRASH': '💥',
            'UNKNOWN': '❓'
        }
        emoji = status_emoji.get(self.market_sentiment['status'], '❓')
        info(f"🌍 시장 상태: {emoji} {self.market_sentiment['status']}")

        # 포트폴리오
        active_coins = list(self.dynamic_workers.active_workers.keys())
        info(f"💼 활성 코인: {len(active_coins)}개")
        for coin in active_coins:
            budget = self.dynamic_workers.active_workers[coin].get('budget', 0)
            count = self.spot_loop_counts.get(coin, 0)
            info(f"   🟢 {coin}: {budget:,}원 (루프: {count}회)")

        # 리스크
        risk_stats = global_risk.get_statistics()
        info(f"⚠️ 일일 손익: {risk_stats.get('daily_pnl', 0):+,.0f}원")

        info("=" * 60 + "\n")

    # ========================================
    # 메인 실행
    # ========================================

    async def run(self):
        """메인 실행 (비동기)"""
        info("=" * 60)
        info("🎯 자동매매 시작! (동적 포트폴리오)")
        info(f"📊 현물 체크 주기: {self.spot_check_interval}초")
        info(f"💼 포트폴리오 체크 주기: {self.portfolio_interval}초 ({self.portfolio_interval // 60}분)")
        info(f"🌍 시장 감정 체크 주기: {self.market_sentiment_interval}초 ({self.market_sentiment_interval // 60}분)")
        info("=" * 60)

        tasks = []

        # 1. 🌍 시장 감정 워커
        market_task = asyncio.create_task(self.market_sentiment_worker())
        tasks.append(market_task)

        # 2. 💼 포트폴리오 워커
        portfolio_task = asyncio.create_task(self.portfolio_worker())
        tasks.append(portfolio_task)

        # 3. 🛠️ 유지보수 태스크
        maintenance = asyncio.create_task(self.maintenance_task())
        tasks.append(maintenance)

        # 모든 태스크 실행
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            info("\n⏹️  사용자 요청으로 봇을 종료합니다.")

            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)

            self._shutdown()

    def _shutdown(self):
        """종료 처리"""
        info("\n🛑 봇 종료 중...")

        try:
            state_manager.save_state()
            info("✅ 상태 저장 완료")
        except:
            warning("⚠️ 상태 저장 실패")

        self._print_statistics()
        info("👋 안녕히 가세요!")


def main():
    """메인 함수"""
    from config.master_config import validate_config

    is_valid, errors = validate_config()
    if not is_valid:
        print("\n❌ 설정 오류:")
        for err in errors:
            print(f"  - {err}")
        print("\n.env 파일과 config/master_config.py를 확인하세요!")
        return

    bot = CoinMoneyBot()

    if bot.check_connection():
        asyncio.run(bot.run())
    else:
        error("❌ 봇 연결 실패. API 키를 확인하세요.")


if __name__ == "__main__":
    main()