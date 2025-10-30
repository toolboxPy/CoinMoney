"""
전략 등록부 (Strategy Registry)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
새로운 전략을 추가할 때 main.py를 수정할 필요 없이,
여기에 한 줄만 추가하면 자동으로 등록됩니다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ============================================================
# 현물 전략 임포트
# ============================================================

try:
    from strategies.multi_indicator import multi_indicator_strategy

    MULTI_INDICATOR_AVAILABLE = True
except ImportError:
    MULTI_INDICATOR_AVAILABLE = False
    multi_indicator_strategy = None

try:
    from strategies.dca import dca_strategy

    DCA_AVAILABLE = True
except ImportError:
    DCA_AVAILABLE = False
    dca_strategy = None

try:
    from strategies.grid import grid_strategy

    GRID_AVAILABLE = True
except ImportError:
    GRID_AVAILABLE = False
    grid_strategy = None

try:
    from strategies.breakout import breakout_strategy

    BREAKOUT_AVAILABLE = True
except ImportError:
    BREAKOUT_AVAILABLE = False
    breakout_strategy = None

try:
    from strategies.scalping import scalping_strategy

    SCALPING_AVAILABLE = True
except ImportError:
    SCALPING_AVAILABLE = False
    scalping_strategy = None

try:
    from strategies.trailing import trailing_strategy

    TRAILING_AVAILABLE = True
except ImportError:
    TRAILING_AVAILABLE = False
    trailing_strategy = None

# ============================================================
# 선물 전략 임포트
# ============================================================

try:
    from strategies.long_short import long_short_strategy

    LONG_SHORT_AVAILABLE = True
except ImportError:
    LONG_SHORT_AVAILABLE = False
    long_short_strategy = None

try:
    from strategies.futures_grid import futures_grid_strategy

    FUTURES_GRID_AVAILABLE = True
except ImportError:
    FUTURES_GRID_AVAILABLE = False
    futures_grid_strategy = None

try:
    from strategies.funding_arbitrage import funding_arbitrage_strategy

    FUNDING_ARBITRAGE_AVAILABLE = True
except ImportError:
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


def print_available_strategies():
    """등록된 전략 목록 출력"""
    print("\n" + "=" * 60)
    print("📊 등록된 전략 목록")
    print("=" * 60)

    print("\n🟢 현물 전략:")
    if strategy_registry:
        for name in strategy_registry.keys():
            print(f"  ✅ {name}")
    else:
        print("  ❌ 등록된 전략 없음")

    print("\n🔵 선물 전략:")
    if futures_strategy_registry:
        for name in futures_strategy_registry.keys():
            print(f"  ✅ {name}")
    else:
        print("  ❌ 등록된 전략 없음")

    print("=" * 60 + "\n")


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
    def run(self, coin, analysis):
        # 전략 로직
        if 매수_조건:
            return 'BUY'
        elif 매도_조건:
            return 'SELL'
        else:
            return 'HOLD'

# 인스턴스 생성
my_strategy = MyStrategy()

3. 이 파일(__init__.py)에 임포트 추가:

try:
    from strategies.my_strategy import my_strategy
    MY_STRATEGY_AVAILABLE = True
except ImportError:
    MY_STRATEGY_AVAILABLE = False
    my_strategy = None

4. 등록부에 추가:

if MY_STRATEGY_AVAILABLE:
    strategy_registry['my_strategy'] = my_strategy

5. 완료! main.py는 수정 불필요 ✅

6. config/master_config.py에서 활성화:

ENABLED_STRATEGIES = {
    'spot': ['multi_indicator', 'my_strategy'],  # 추가!
    'futures': ['long_short']
}
"""

# ============================================================
# 모듈 초기화
# ============================================================

if __name__ == "__main__":
    print("🧪 전략 등록부 테스트\n")
    print_available_strategies()

    # 테스트
    print("테스트:")
    print(f"  multi_indicator 사용 가능? {is_strategy_available('multi_indicator')}")
    print(f"  dca 사용 가능? {is_strategy_available('dca')}")
    print(f"  long_short 사용 가능? {is_strategy_available('long_short', is_futures=True)}")