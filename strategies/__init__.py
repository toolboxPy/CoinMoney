"""
전략 등록부 (Strategy Registry)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
새로운 전략을 추가할 때 main.py를 수정할 필요 없이,
여기에 한 줄만 추가하면 자동으로 등록됩니다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from utils.logger import info, warning

# ============================================================
# 현물 전략 임포트
# ============================================================

try:
    from strategies.multi_indicator import multi_indicator_30m as multi_indicator_strategy
    MULTI_INDICATOR_AVAILABLE = True
    info("✅ Multi-Indicator 전략 로드 완료")
except ImportError as e:
    MULTI_INDICATOR_AVAILABLE = False
    multi_indicator_strategy = None
    warning(f"⚠️ Multi-Indicator 전략 로드 실패: {e}")

try:
    from strategies.dca import dca_strategy
    DCA_AVAILABLE = True
    info("✅ DCA 전략 로드 완료")
except ImportError as e:
    DCA_AVAILABLE = False
    dca_strategy = None
    warning(f"⚠️ DCA 전략 로드 실패: {e}")

try:
    from strategies.grid import grid_strategy
    GRID_AVAILABLE = True
    info("✅ Grid 전략 로드 완료")
except ImportError as e:
    GRID_AVAILABLE = False
    grid_strategy = None
    warning(f"⚠️ Grid 전략 로드 실패: {e}")

try:
    from strategies.breakout import breakout_strategy
    BREAKOUT_AVAILABLE = True
    info("✅ Breakout 전략 로드 완료")
except ImportError as e:
    BREAKOUT_AVAILABLE = False
    breakout_strategy = None
    warning(f"⚠️ Breakout 전략 로드 실패: {e}")

try:
    from strategies.scalping import scalping_strategy
    SCALPING_AVAILABLE = True
    info("✅ Scalping 전략 로드 완료")
except ImportError as e:
    SCALPING_AVAILABLE = False
    scalping_strategy = None
    warning(f"⚠️ Scalping 전략 로드 실패: {e}")

try:
    from strategies.trailing import trailing_strategy
    TRAILING_AVAILABLE = True
    info("✅ Trailing 전략 로드 완료")
except ImportError as e:
    TRAILING_AVAILABLE = False
    trailing_strategy = None
    warning(f"⚠️ Trailing 전략 로드 실패: {e}")


# ============================================================
# 선물 전략 임포트
# ============================================================

try:
    from strategies.long_short import long_short_strategy
    LONG_SHORT_AVAILABLE = True
    info("✅ Long/Short 전략 로드 완료")
except ImportError as e:
    LONG_SHORT_AVAILABLE = False
    long_short_strategy = None
    # 선물 전략은 경고 안 함 (선택적)

try:
    from strategies.futures_grid import futures_grid_strategy
    FUTURES_GRID_AVAILABLE = True
    info("✅ Futures Grid 전략 로드 완료")
except ImportError as e:
    FUTURES_GRID_AVAILABLE = False
    futures_grid_strategy = None

try:
    from strategies.funding_arbitrage import funding_arbitrage_strategy
    FUNDING_ARBITRAGE_AVAILABLE = True
    info("✅ Funding Arbitrage 전략 로드 완료")
except ImportError as e:
    FUNDING_ARBITRAGE_AVAILABLE = False
    funding_arbitrage_strategy = None


# ============================================================
# 🔥 현물 전략 등록부
# ============================================================

strategy_registry = {}

if MULTI_INDICATOR_AVAILABLE:
    strategy_registry['multi_indicator'] = multi_indicator_strategy

if DCA_AVAILABLE:
    strategy_registry['dca'] = dca_strategy

if GRID_AVAILABLE:
    strategy_registry['grid'] = grid_strategy

if BREAKOUT_AVAILABLE:
    strategy_registry['breakout'] = breakout_strategy

if SCALPING_AVAILABLE:
    strategy_registry['scalping'] = scalping_strategy

if TRAILING_AVAILABLE:
    strategy_registry['trailing'] = trailing_strategy


# ============================================================
# 🔥 선물 전략 등록부
# ============================================================

futures_strategy_registry = {}

if LONG_SHORT_AVAILABLE:
    futures_strategy_registry['long_short'] = long_short_strategy

if FUTURES_GRID_AVAILABLE:
    futures_strategy_registry['futures_grid'] = futures_grid_strategy

if FUNDING_ARBITRAGE_AVAILABLE:
    futures_strategy_registry['funding_arbitrage'] = funding_arbitrage_strategy


# ============================================================
# 유틸리티 함수
# ============================================================

def get_available_spot_strategies():
    """사용 가능한 현물 전략 목록"""
    return list(strategy_registry.keys())


def get_available_futures_strategies():
    """사용 가능한 선물 전략 목록"""
    return list(futures_strategy_registry.keys())


def is_strategy_available(strategy_name, is_futures=False):
    """전략 사용 가능 여부"""
    if is_futures:
        return strategy_name in futures_strategy_registry
    else:
        return strategy_name in strategy_registry


def get_strategy(strategy_name, is_futures=False):
    """전략 인스턴스 가져오기"""
    if is_futures:
        return futures_strategy_registry.get(strategy_name)
    else:
        return strategy_registry.get(strategy_name)


def print_available_strategies():
    """등록된 전략 목록 출력"""
    print("\n" + "=" * 60)
    print("📊 등록된 전략 목록")
    print("=" * 60)

    print("\n🟢 현물 전략:")
    if strategy_registry:
        for name, strategy in strategy_registry.items():
            print(f"  ✅ {name:<20} → {strategy.name if hasattr(strategy, 'name') else '???'}")
    else:
        print("  ❌ 등록된 전략 없음")

    print("\n🔵 선물 전략:")
    if futures_strategy_registry:
        for name, strategy in futures_strategy_registry.items():
            print(f"  ✅ {name:<20} → {strategy.name if hasattr(strategy, 'name') else '???'}")
    else:
        print("  ❌ 등록된 전략 없음")

    print("\n📈 전략 통계:")
    print(f"  현물: {len(strategy_registry)}개")
    print(f"  선물: {len(futures_strategy_registry)}개")
    print(f"  총합: {len(strategy_registry) + len(futures_strategy_registry)}개")

    print("=" * 60 + "\n")


# ============================================================
# 초기화 로그
# ============================================================

info("=" * 60)
info("📊 전략 시스템 초기화 완료")
info("=" * 60)
info(f"✅ 현물 전략: {len(strategy_registry)}개 등록")
for name in strategy_registry.keys():
    info(f"   - {name}")

if futures_strategy_registry:
    info(f"✅ 선물 전략: {len(futures_strategy_registry)}개 등록")
    for name in futures_strategy_registry.keys():
        info(f"   - {name}")
else:
    info("📝 선물 전략: 등록 없음 (현물만 사용)")

info("=" * 60)


# ============================================================
# 전략 추가 가이드
# ============================================================

"""
🎯 새로운 전략 추가 방법:

1. strategies/ 폴더에 전략 파일 생성
   예: strategies/my_strategy.py

2. 전략 클래스 구현:

# strategies/my_strategy.py
class MyStrategy:
    def __init__(self, timeframe='1h'):
        self.timeframe = timeframe
        self.name = f"MyStrategy-{timeframe}"
    
    def analyze(self, coin):
        # 분석 로직
        return {
            'signal': 'BUY/SELL/HOLD',
            'score': float,
            'confidence': float,
            'reasons': []
        }
    
    def execute(self, coin):
        # 실행 로직
        return result

# 인스턴스 생성
my_strategy = MyStrategy('1h')

3. 이 파일(__init__.py)에 임포트 추가:

try:
    from strategies.my_strategy import my_strategy
    MY_STRATEGY_AVAILABLE = True
    info("✅ My Strategy 전략 로드 완료")
except ImportError as e:
    MY_STRATEGY_AVAILABLE = False
    my_strategy = None
    warning(f"⚠️ My Strategy 전략 로드 실패: {e}")

4. 등록부에 추가:

if MY_STRATEGY_AVAILABLE:
    strategy_registry['my_strategy'] = my_strategy

5. 완료! main.py는 수정 불필요 ✅
"""


# ============================================================
# 모듈 초기화
# ============================================================

if __name__ == "__main__":
    print("🧪 전략 등록부 테스트\n")
    print_available_strategies()

    # 테스트
    print("\n" + "=" * 60)
    print("🧪 전략 사용 가능 여부 테스트")
    print("=" * 60)

    test_strategies = [
        ('multi_indicator', False),
        ('dca', False),
        ('grid', False),
        ('breakout', False),
        ('scalping', False),
        ('trailing', False),
        ('long_short', True)
    ]

    for strategy_name, is_futures in test_strategies:
        available = is_strategy_available(strategy_name, is_futures)
        strategy_type = "선물" if is_futures else "현물"
        status = "✅ 사용 가능" if available else "❌ 사용 불가"
        print(f"  {strategy_name:<20} ({strategy_type}): {status}")

    print("=" * 60)