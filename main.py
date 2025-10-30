"""
CoinMoney 자동매매 봇 (v3.1 - 비동기 + 선물 + Registry)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[주요 개선사항]
1. asyncio 비동기 처리 → 코인별 독립 워커
2. 선물 거래 워커 추가
3. Strategy Registry 패턴 → 유연한 전략 관리
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import pyupbit
import asyncio
import pandas as pd
from datetime import datetime
from config.master_config import *

# 유틸리티
from utils.logger import info, warning, error, trade_log
from utils.state_manager import state_manager
from utils.performance_tracker import performance_tracker

# 핵심 시스템
from master.global_risk import global_risk
from analysis.technical import technical_analyzer

# 🔥 v3.0: 스마트 마스터 컨트롤러
try:
    from master.controller_v3 import smart_controller as master_controller
    CONTROLLER_VERSION = "v3.1"
    info("✅ 스마트 컨트롤러 v3.1 로드")
except ImportError:
    from master.controller import master_controller
    CONTROLLER_VERSION = "v1.0"
    warning("⚠️ v1.0 컨트롤러 사용 (Fallback)")

# 거래 모듈
from traders.spot_trader import spot_trader
from traders.futures_trader import futures_trader

# 🔥 Strategy Registry (전략 등록부)
from strategies import strategy_registry, futures_strategy_registry

# 뉴스 수집기 (선택)
try:
    from utils.news_analyzer import NewsCollector
    news_collector = NewsCollector()
    NEWS_AVAILABLE = True
except:
    NEWS_AVAILABLE = False
    warning("⚠️ 뉴스 수집기 없음 (선택 기능)")

# 선물 거래용 ccxt (바이낸스)
try:
    import ccxt
    CCXT_AVAILABLE = True
except:
    CCXT_AVAILABLE = False
    warning("⚠️ ccxt 없음 (선물 거래 비활성)")


class CoinMoneyBot:
    """CoinMoney 자동매매 봇 v3.1 (비동기)"""

    def __init__(self):
        info("🚀 CoinMoney Bot v3.1 시작!")
        info("=" * 60)
        info(f"📊 컨트롤러: {CONTROLLER_VERSION}")
        info(f"🤖 비동기 처리: ✅")
        info(f"⚡ 독립 워커: ✅")

        # Upbit 인증
        try:
            self.upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
            info("✅ Upbit API 인증 성공")
        except Exception as e:
            error(f"❌ Upbit API 인증 실패: {e}")
            self.upbit = None

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

        # 상태 복구
        try:
            state_manager.load_state()
            info("✅ 이전 상태 복구 완료")
        except:
            info("💾 새로운 상태 시작")

        # 통계
        self.spot_loop_counts = {}
        self.futures_loop_counts = {}
        self.last_news_check = None

        # 🔥 시장 감정 상태 (전체 시장 흐름)
        self.market_sentiment = {
            'status': 'UNKNOWN',        # BULL_RUN, BULLISH, NEUTRAL, BEARISH, CRASH
            'score': 0.0,               # -100 ~ +100
            'btc_trend': 'NEUTRAL',     # BTC 추세
            'total_market_cap': 0,      # 전체 시가총액
            'fear_greed_index': 50,     # 공포/탐욕 지수
            'major_coins_avg': 0.0,     # 주요 코인 평균 변화율
            'trading_allowed': True,    # 거래 허용 여부
            'last_update': None
        }

        # 🔥 동적 워커 관리
        self.active_workers = {}  # {coin: task}
        self.worker_lock = asyncio.Lock()

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
                    warning("⚠️ 선물 연결 실패 (현물만 운영)")

            return True
        except Exception as e:
            error(f"❌ 연결 실패: {e}")
            return False

    # ========================================
    # 🔥 시장 감정 워커 (Market Sentiment)
    # ========================================

    async def analyze_market_sentiment(self):
        """
        전체 시장 감정 분석

        Returns:
            dict: 시장 상태
        """
        try:
            # 주요 코인들 데이터 수집
            major_coins = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-BNB']
            changes = []

            for coin in major_coins:
                try:
                    # 1시간 전 대비 변화율
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

            # 평균 변화율
            avg_change = sum(changes) / len(changes)

            # 시장 상태 판단
            if avg_change > 5:
                status = 'BULL_RUN'      # 강한 상승장
                trading_allowed = True
            elif avg_change > 2:
                status = 'BULLISH'       # 상승장
                trading_allowed = True
            elif avg_change > -2:
                status = 'NEUTRAL'       # 중립
                trading_allowed = True
            elif avg_change > -5:
                status = 'BEARISH'       # 하락장
                trading_allowed = False  # 거래 중단!
            else:
                status = 'CRASH'         # 폭락
                trading_allowed = False  # 거래 중단!

            # BTC 트렌드 (가장 중요)
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
                'major_coins_avg': avg_change,
                'trading_allowed': trading_allowed,
                'last_update': datetime.now()
            }

        except Exception as e:
            error(f"❌ 시장 감정 분석 오류: {e}")
            return None

    async def market_sentiment_worker(self):
        """
        시장 감정 감시 워커 (5분마다)

        전체 시장의 흐름을 파악하여 개별 코인 워커들에게 신호 제공
        """
        info("🌍 시장 감정 워커 시작")

        while True:
            try:
                info("\n" + "="*60)
                info("🌍 전체 시장 분석 중...")
                info("="*60)

                # 시장 분석
                sentiment = await self.analyze_market_sentiment()

                if sentiment:
                    # 상태 업데이트
                    self.market_sentiment.update(sentiment)

                    # 로그
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

                    # 🔥 긴급 상황 처리
                    if sentiment['status'] in ['CRASH', 'BEARISH']:
                        warning(f"⚠️ 시장 {sentiment['status']}! 모든 거래 중단!")

                        # 포지션 있으면 청산 신호
                        state = state_manager.state['spot']
                        if state['in_position']:
                            warning("🚨 긴급 청산 필요!")

                    # 🔥 동적 코인 추가/제거 판단
                    await self._adjust_coin_workers(sentiment)

                info("="*60)

                # 5분 대기
                await asyncio.sleep(300)

            except asyncio.CancelledError:
                info("🛑 시장 감정 워커 종료")
                break

            except Exception as e:
                error(f"⚠️ 시장 감정 워커 오류: {e}")
                await asyncio.sleep(60)

    async def _adjust_coin_workers(self, sentiment):
        """
        시장 상황에 따라 코인 워커 동적 조정

        Args:
            sentiment: 시장 감정
        """
        async with self.worker_lock:
            current_coins = set(TRADING_COINS['spot'])

            # BULL_RUN: 알트코인 추가
            if sentiment['status'] == 'BULL_RUN':
                potential_coins = ['KRW-SOL', 'KRW-AVAX', 'KRW-DOT']
                for coin in potential_coins:
                    if coin not in self.active_workers and coin not in current_coins:
                        info(f"🚀 [{coin}] 상승장 → 워커 추가!")
                        # TODO: 동적 워커 추가 구현

            # CRASH/BEARISH: 위험 코인 제거
            elif sentiment['status'] in ['CRASH', 'BEARISH']:
                # 알트코인 워커 중단
                risky_coins = ['KRW-XRP', 'KRW-ADA', 'KRW-DOGE']
                for coin in risky_coins:
                    if coin in self.active_workers:
                        warning(f"📉 [{coin}] 하락장 → 워커 중단!")
                        # TODO: 워커 중단 구현

    # ========================================
    # 현물 거래 관련 메서드
    # ========================================

    async def get_market_data(self, coin):
        """
        시장 데이터 수집 (비동기)

        Returns:
            dict or None
        """
        try:
            # 현재가 (동기 → 비동기 래핑)
            price = await asyncio.to_thread(pyupbit.get_current_price, coin)
            if price is None:
                warning(f"⚠️ {coin} 가격 조회 실패")
                return None

            # OHLCV 데이터 (비동기 래핑)
            df = await asyncio.to_thread(
                pyupbit.get_ohlcv,
                coin,
                interval="minute60",
                count=200
            )

            if df is None or len(df) < 20:
                warning(f"⚠️ {coin} 차트 데이터 부족")
                return None

            # 기술적 분석 (로컬, 무료!)
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
        """뉴스 데이터 수집 (비동기)"""
        if not NEWS_AVAILABLE:
            return None

        from datetime import timedelta
        now = datetime.now()

        # 10분마다만 체크
        if self.last_news_check and (now - self.last_news_check) < timedelta(minutes=10):
            return None

        try:
            # 비동기 래핑
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
        """포지션 데이터 수집 (비동기)"""
        try:
            # 비동기 래핑
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

    async def execute_spot_strategies(self, coin, analysis_result):
        """
        현물 전략 실행 (비동기 + Registry 패턴)

        Args:
            coin: 거래 코인
            analysis_result: 마스터 분석 결과
        """
        if not analysis_result.get('trading_allowed', False):
            return

        spot_strategies = analysis_result['strategies'].get('spot', [])

        if not spot_strategies:
            # 전략 없음 → 포지션 청산
            state = state_manager.state['spot']
            if state['in_position']:
                info(f"📤 [{coin}] 모든 전략 비활성 → 포지션 청산")
                await asyncio.to_thread(
                    spot_trader.sell_all,
                    coin,
                    reason="전략 비활성화"
                )
            return

        # 🔥 Registry 패턴으로 전략 실행
        for strategy_name in spot_strategies:
            strategy_module = strategy_registry.get(strategy_name)

            if strategy_module:
                try:
                    # 전략 실행 (비동기 래핑)
                    action = await asyncio.to_thread(
                        strategy_module.run,
                        coin,
                        analysis_result['analysis']
                    )

                    # 액션 실행
                    if action == 'BUY':
                        info(f"💰 [{coin}] {strategy_name} 매수 신호")
                        await asyncio.to_thread(
                            spot_trader.buy,
                            coin,
                            SPOT_BUDGET * 0.3,
                            reason=f"{strategy_name} 매수"
                        )

                    elif action == 'SELL':
                        info(f"📤 [{coin}] {strategy_name} 매도 신호")
                        await asyncio.to_thread(
                            spot_trader.sell_all,
                            coin,
                            reason=f"{strategy_name} 매도"
                        )

                except Exception as e:
                    error(f"❌ [{coin}] {strategy_name} 실행 오류: {e}")
            else:
                warning(f"⚠️ 알 수 없는 전략: {strategy_name}")

    async def spot_worker(self, coin):
        """
        현물 코인 전용 워커 (독립 실행)

        Args:
            coin: 거래 코인 (예: 'KRW-BTC')
        """
        loop_count = 0

        info(f"🟢 [{coin}] 현물 워커 시작")

        while True:
            try:
                loop_count += 1
                self.spot_loop_counts[coin] = loop_count

                # 🔥 시장 감정 체크 (최우선!)
                if not self.market_sentiment['trading_allowed']:
                    warning(f"⚠️ [{coin}] 시장 {self.market_sentiment['status']} → 거래 중단!")

                    # 포지션 있으면 청산
                    state = state_manager.state['spot']
                    if state['in_position'] and state['positions'].get(coin):
                        warning(f"🚨 [{coin}] 긴급 청산 실행!")
                        await asyncio.to_thread(
                            spot_trader.sell_all,
                            coin,
                            reason=f"시장 {self.market_sentiment['status']}"
                        )

                    # 30초 대기 후 재확인
                    await asyncio.sleep(CHECK_INTERVALS['main_loop'])
                    continue

                info(f"\n{'='*60}")
                info(f"🔍 [{coin}] 분석 시작 (#{loop_count})")
                info(f"🌍 시장: {self.market_sentiment['status']} ({self.market_sentiment['score']:+.1f}%)")
                info(f"{'='*60}")

                # 1. 시장 데이터
                market_data = await self.get_market_data(coin)
                if not market_data:
                    await asyncio.sleep(CHECK_INTERVALS['main_loop'])
                    continue

                info(f"💰 현재가: {market_data['price']:,.0f}원")
                info(f"📊 기술 점수: {market_data['technical'].get('score', 0):.1f}/5")

                # 2. 뉴스 (공유)
                news_data = await self.get_news_data()
                if news_data:
                    info(f"📰 뉴스: {news_data['count_1h']}개 (중요도: {news_data['urgency']:.1f}/10)")

                # 3. 포지션
                position_data = await self.get_position_data(coin)
                if position_data and position_data.get('in_position'):
                    pnl = position_data['pnl_ratio'] * 100
                    info(f"📈 포지션: {pnl:+.2f}%")

                # 4. 🧠 마스터 분석 (+ 시장 감정 전달)
                info("\n🧠 마스터 분석 중...")

                # 시장 감정을 market_data에 추가
                market_data['market_sentiment'] = self.market_sentiment

                analysis_result = await asyncio.to_thread(
                    master_controller.analyze_and_adjust,
                    market_data,
                    news_data=news_data,
                    position_data=position_data
                )

                if not analysis_result:
                    warning("⚠️ 분석 실패")
                    await asyncio.sleep(CHECK_INTERVALS['main_loop'])
                    continue

                # 5. 전략 실행
                info("\n🎯 전략 실행 중...")
                await self.execute_spot_strategies(coin, analysis_result)

                info(f"{'='*60}\n")

                # 6. 대기 (진짜 30초!)
                await asyncio.sleep(CHECK_INTERVALS['main_loop'])

            except asyncio.CancelledError:
                info(f"🛑 [{coin}] 워커 종료")
                break

            except Exception as e:
                error(f"⚠️ [{coin}] 워커 오류: {e}")
                await asyncio.sleep(10)

    # ========================================
    # 선물 거래 관련 메서드
    # ========================================

    async def get_futures_market_data(self, symbol):
        """
        선물 시장 데이터 수집 (ccxt)

        Args:
            symbol: 선물 심볼 (예: 'BTC/USDT')

        Returns:
            dict or None
        """
        if not self.binance:
            return None

        try:
            # 현재가 (비동기)
            ticker = await asyncio.to_thread(self.binance.fetch_ticker, symbol)
            price = ticker['last']

            # OHLCV (1시간봉 200개)
            ohlcv = await asyncio.to_thread(
                self.binance.fetch_ohlcv,
                symbol,
                timeframe='1h',
                limit=200
            )

            # DataFrame 변환
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # 기술적 분석
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

    async def get_futures_position_data(self, symbol):
        """선물 포지션 데이터 수집"""
        if not self.binance:
            return None

        try:
            positions = await asyncio.to_thread(self.binance.fetch_positions, [symbol])

            for pos in positions:
                if pos['symbol'] == symbol and float(pos['contracts']) > 0:
                    pnl_ratio = float(pos['percentage']) / 100

                    return {
                        'in_position': True,
                        'side': pos['side'],
                        'contracts': float(pos['contracts']),
                        'entry_price': float(pos['entryPrice']),
                        'current_price': float(pos['markPrice']),
                        'pnl_ratio': pnl_ratio,
                        'leverage': float(pos['leverage'])
                    }

            return {'in_position': False}

        except Exception as e:
            warning(f"⚠️ {symbol} 선물 포지션 오류: {e}")
            return None

    async def execute_futures_strategies(self, symbol, analysis_result):
        """
        선물 전략 실행 (비동기 + Registry)

        Args:
            symbol: 선물 심볼
            analysis_result: 분석 결과
        """
        if not analysis_result.get('trading_allowed', False):
            return

        futures_strategies = analysis_result['strategies'].get('futures', [])

        if not futures_strategies:
            return

        # 🔥 Registry 패턴
        for strategy_name in futures_strategies:
            strategy_module = futures_strategy_registry.get(strategy_name)

            if strategy_module:
                try:
                    action = await asyncio.to_thread(
                        strategy_module.run,
                        symbol,
                        analysis_result['analysis']
                    )

                    if action == 'LONG':
                        info(f"📈 [{symbol}] {strategy_name} 롱 진입")
                        await asyncio.to_thread(
                            futures_trader.open_long,
                            symbol,
                            FUTURES_BUDGET * 0.5,
                            reason=f"{strategy_name} 롱"
                        )

                    elif action == 'SHORT':
                        info(f"📉 [{symbol}] {strategy_name} 숏 진입")
                        await asyncio.to_thread(
                            futures_trader.open_short,
                            symbol,
                            FUTURES_BUDGET * 0.5,
                            reason=f"{strategy_name} 숏"
                        )

                    elif action == 'CLOSE':
                        info(f"🔒 [{symbol}] {strategy_name} 포지션 청산")
                        await asyncio.to_thread(
                            futures_trader.close_position,
                            symbol,
                            reason=f"{strategy_name} 청산"
                        )

                except Exception as e:
                    error(f"❌ [{symbol}] {strategy_name} 실행 오류: {e}")
            else:
                warning(f"⚠️ 알 수 없는 선물 전략: {strategy_name}")

    async def futures_worker(self, symbol):
        """
        선물 심볼 전용 워커 (독립 실행)

        Args:
            symbol: 선물 심볼 (예: 'BTC/USDT')
        """
        if not self.binance:
            info(f"⚠️ [{symbol}] 선물 API 없음, 워커 미실행")
            return

        loop_count = 0

        info(f"🔵 [{symbol}] 선물 워커 시작")

        while True:
            try:
                loop_count += 1
                self.futures_loop_counts[symbol] = loop_count

                info(f"\n{'='*60}")
                info(f"🔍 [{symbol}] 선물 분석 시작 (#{loop_count})")
                info(f"{'='*60}")

                # 1. 선물 시장 데이터
                market_data = await self.get_futures_market_data(symbol)
                if not market_data:
                    await asyncio.sleep(CHECK_INTERVALS['futures'])
                    continue

                info(f"💰 현재가: ${market_data['price']:,.2f}")
                info(f"📊 기술 점수: {market_data['technical'].get('score', 0):.1f}/5")

                # 2. 뉴스 (공유)
                news_data = await self.get_news_data()

                # 3. 선물 포지션
                position_data = await self.get_futures_position_data(symbol)
                if position_data and position_data.get('in_position'):
                    pnl = position_data['pnl_ratio'] * 100
                    side = position_data['side']
                    info(f"📊 포지션: {side} {pnl:+.2f}%")

                # 4. 🧠 마스터 분석
                info("\n🧠 마스터 분석 중...")
                analysis_result = await asyncio.to_thread(
                    master_controller.analyze_and_adjust,
                    market_data,
                    news_data=news_data,
                    position_data=position_data
                )

                if not analysis_result:
                    await asyncio.sleep(CHECK_INTERVALS['futures'])
                    continue

                # 5. 선물 전략 실행
                info("\n🎯 선물 전략 실행 중...")
                await self.execute_futures_strategies(symbol, analysis_result)

                info(f"{'='*60}\n")

                # 6. 대기 (선물 주기)
                await asyncio.sleep(CHECK_INTERVALS['futures'])

            except asyncio.CancelledError:
                info(f"🛑 [{symbol}] 선물 워커 종료")
                break

            except Exception as e:
                error(f"⚠️ [{symbol}] 선물 워커 오류: {e}")
                await asyncio.sleep(10)

    # ========================================
    # 유지보수 태스크
    # ========================================

    async def maintenance_task(self):
        """주기적 유지보수 태스크"""
        info("🛠️ 유지보수 태스크 시작")

        while True:
            try:
                # 10분마다 실행
                await asyncio.sleep(600)

                # 상태 저장
                try:
                    state_manager.save_state()
                    info("💾 상태 저장 완료")
                except:
                    warning("⚠️ 상태 저장 실패")

                # 통계 출력 (30분마다)
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
        info(f"📊 시장 점수: {self.market_sentiment['score']:+.2f}%")
        info(f"₿ BTC 추세: {self.market_sentiment['btc_trend']}")

        # 워커 상태
        for coin, count in self.spot_loop_counts.items():
            info(f"🟢 [{coin}] 현물 루프: {count}회")

        for symbol, count in self.futures_loop_counts.items():
            info(f"🔵 [{symbol}] 선물 루프: {count}회")

        # 컨트롤러 통계
        if CONTROLLER_VERSION == "v3.1":
            stats = master_controller.get_statistics()
            info(f"🧠 AI 호출률: {stats.get('ai_call_rate', 0):.1f}%")
            info(f"💰 비용 절감률: {stats.get('savings_rate', 0):.1f}%")

        # 리스크 통계
        risk_stats = global_risk.get_statistics()
        info(f"⚠️ 일일 손익: {risk_stats.get('daily_pnl', 0):+,.0f}원")

        # 성과 통계
        perf_report = performance_tracker.get_performance_report(days=1)
        info(f"📈 승률: {perf_report['actual_trades'].get('win_rate', 0):.1f}%")

        info("=" * 60 + "\n")

    # ========================================
    # 메인 실행
    # ========================================

    async def run(self):
        """메인 실행 (비동기)"""
        info("=" * 60)
        info("🎯 자동매매 시작! (비동기 모드)")
        info(f"📊 현물 체크 주기: {CHECK_INTERVALS['main_loop']}초")
        info(f"📊 선물 체크 주기: {CHECK_INTERVALS['futures']}초")
        info(f"🌍 시장 감정 체크 주기: 300초 (5분)")
        info(f"🪙 현물 코인: {', '.join(TRADING_COINS['spot'])}")
        info(f"🪙 선물 심볼: {', '.join(TRADING_COINS['futures'])}")
        info("=" * 60)

        tasks = []

        # 🌍 시장 감정 워커 (최우선!)
        market_task = asyncio.create_task(self.market_sentiment_worker())
        tasks.append(market_task)
        info("🌍 시장 감정 워커 등록 완료")

        # 🟢 현물 워커들 (각 코인마다 독립 실행!)
        for coin in TRADING_COINS['spot']:
            task = asyncio.create_task(self.spot_worker(coin))
            tasks.append(task)

        # 🔵 선물 워커들 (각 심볼마다 독립 실행!)
        if self.binance and TRADING_COINS.get('futures'):
            for symbol in TRADING_COINS['futures']:
                # BTCUSDT → BTC/USDT 변환
                ccxt_symbol = symbol.replace('USDT', '/USDT')
                task = asyncio.create_task(self.futures_worker(ccxt_symbol))
                tasks.append(task)

        # 🛠️ 유지보수 태스크
        maintenance = asyncio.create_task(self.maintenance_task())
        tasks.append(maintenance)

        # 모든 태스크 실행
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            info("\n⏹️  사용자 요청으로 봇을 종료합니다.")

            # 모든 태스크 취소
            for task in tasks:
                task.cancel()

            # 종료 대기
            await asyncio.gather(*tasks, return_exceptions=True)

            # 최종 저장
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
    # 설정 검증
    from config.master_config import validate_config

    is_valid, errors = validate_config()
    if not is_valid:
        print("\n❌ 설정 오류:")
        for err in errors:
            print(f"  - {err}")
        print("\n.env 파일과 config/master_config.py를 확인하세요!")
        return

    # 봇 생성
    bot = CoinMoneyBot()

    if bot.check_connection():
        # 🔥 비동기 실행!
        asyncio.run(bot.run())
    else:
        error("❌ 봇 연결 실패. API 키를 확인하세요.")


if __name__ == "__main__":
    main()