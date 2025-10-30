"""
마스터 설정 파일 (v3.0 - 이벤트 드리븐 최적화)
"""
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# ============================================================
# API 키
# ============================================================

UPBIT_ACCESS_KEY = os.getenv('UPBIT_ACCESS_KEY', '')
UPBIT_SECRET_KEY = os.getenv('UPBIT_SECRET_KEY', '')

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')

# AI API 키
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# 뉴스 API (선택)
NEWS_API_KEY = os.getenv('NEWS_API_KEY', '')

# 텔레그램
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# ============================================================
# 투자 설정
# ============================================================

TOTAL_INVESTMENT = 1000000  # 100만원
SPOT_ALLOCATION = 0.6  # 60% 현물
FUTURES_ALLOCATION = 0.4  # 40% 선물

SPOT_BUDGET = TOTAL_INVESTMENT * SPOT_ALLOCATION
FUTURES_BUDGET = TOTAL_INVESTMENT * FUTURES_ALLOCATION

# ============================================================
# 시간 프레임 & 체크 주기
# ============================================================

TIMEFRAMES = {
    'spot': {
        'primary': 'minute30',  # 30분봉
        'secondary': 'minute15',
        'long_term': 'minute60'
    },
    'futures': {
        'primary': 'minute60',  # 1시간봉
        'secondary': 'minute30',
        'long_term': 'minute240'
    }
}

# 메인 루프 체크 주기 (초)
CHECK_INTERVALS = {
    'main_loop': 30,  # 30초마다 로컬 분석
    'spot': 180,
    'futures': 300
}

# ============================================================
# 거래 코인
# ============================================================

TRADING_COINS = {
    'spot': ['KRW-BTC', 'KRW-ETH'],
    'futures': ['BTCUSDT', 'ETHUSDT']
}

# ============================================================
# 선물 설정
# ============================================================

FUTURES_LEVERAGE = 5
FUTURES_MARGIN_MODE = "ISOLATED"  # 격리 마진

# ============================================================
# 수수료
# ============================================================

FEES = {
    'spot': {
        'maker': 0.0005,
        'taker': 0.00139
    },
    'futures': {
        'maker': 0.0002,
        'taker': 0.0005,
        'funding': 0.0001
    }
}

# ============================================================
# 익절/손절
# ============================================================

PROFIT_TARGETS = {
    'spot_minute30': {
        'take_profit_1': 0.015,  # 1.5%
        'take_profit_2': 0.025,  # 2.5%
        'stop_loss': -0.02,  # -2%
        'trailing_stop': 0.01  # 1%
    },
    'futures_minute60': {
        'take_profit_1': 0.02,  # 2%
        'take_profit_2': 0.03,  # 3%
        'stop_loss': -0.015,  # -1.5%
        'trailing_stop': 0.01  # 1%
    }
}

# ============================================================
# 글로벌 리스크 관리
# ============================================================

GLOBAL_RISK = {
    'daily_loss_limit': 0.05,  # 일일 손실 5%
    'max_consecutive_losses': 4,  # 연속 손실 4회
    'account_drawdown_limit': 0.15,  # 계좌 손실 15%

    'max_positions': {
        'spot': 2,
        'futures': 1
    },

    'max_trades_per_day': {
        'spot': 15,
        'futures': 10
    }
}

# ============================================================
# 포지션 크기
# ============================================================

POSITION_SIZING = {
    'spot': {
        'min_investment': 10000,
        'max_investment': 100000,
        'percent_per_trade': 0.15  # 15%
    },
    'futures': {
        'min_investment': 10000,
        'max_investment': 80000,
        'percent_per_trade': 0.2  # 20%
    }
}

# ============================================================
# 활성화 전략
# ============================================================

ENABLED_STRATEGIES = {
    'spot': ['multi_indicator', 'trailing'],
    'futures': ['long_short']
}

# ============================================================
# 기술적 지표
# ============================================================

TECHNICAL_INDICATORS = {
    'rsi': {
        'period': 14,
        'oversold': 35,
        'overbought': 65
    },
    'macd': {
        'fast': 12,
        'slow': 26,
        'signal': 9
    },
    'bollinger': {
        'period': 20,
        'std': 2
    },
    'ma': {
        'fast': 7,
        'medium': 25,
        'slow': 99
    },
    'volume': {
        'period': 20,
        'surge_multiplier': 2.0
    }
}

# ============================================================
# AI 시스템 설정 (v3.0 - 이벤트 드리븐)
# ============================================================

AI_CONFIG = {
    'enabled': True,

    # 사용 가능한 AI
    'providers': ['claude', 'openai', 'gemini'],

    # 투표/가중치 (단순 투표 시)
    'voting_method': 'majority',
    'weights': {
        'claude': 0.4,
        'openai': 0.3,
        'gemini': 0.3
    },

    # 신뢰도 & 타임아웃
    'min_confidence': 0.7,
    'timeout': 10,
    'fallback_on_failure': True,

    # 실패 허용
    'max_failure_count': 3  # 3회 연속 실패 시 비활성화
}

# ============================================================
# AI 호출 트리거 (v3.0 이벤트 드리븐)
# ============================================================

AI_TRIGGER_CONFIG = {
    # 시장 급변 트리거
    'price_change_5m': 3.0,       # 5분간 3% 이상
    'price_change_1h': 5.0,       # 1시간 5% 이상
    'volume_surge': 2.5,          # 평균 대비 2.5배
    'volatility': 5.0,            # 변동성 5%

    # 기술적 이벤트
    'pattern_score': 7.0,
    'support_resistance': 0.02,   # 2% 이내
    'indicator_conflict': 3.0,

    # 뉴스 이벤트
    'news_urgency': 6.5,          # 중요도 6.5 이상
    'news_count_1h': 5,           # 1시간 5개 이상

    # 포지션 위기
    'position_risk': 0.8,         # 리스크 80%
    'pnl_critical': 0.02,         # 손익 ±2%

    # 🎯 AI 호출 임계값 (핵심!)
    'call_threshold': 50.0        # 50점 이상이면 호출
}

# 최소 호출 간격 (초)
AI_MIN_INTERVAL = 180  # 3분 (긴급 제외)

# ============================================================
# AI 토론 설정 (v2.0)
# ============================================================

AI_DEBATE_V2_CONFIG = {
    'rounds': 2,                    # 2라운드 (빠르고 효율적)
    'compression': True,            # 압축 프로토콜
    'min_agreement': 0.7,           # 합의 임계값

    # 🔥 AI 선택적 사용 (비용 최적화)
    'adaptive_ai_selection': True,
    'ai_selection_rules': {
        'normal': ['gemini'],                       # 평상시 (저렴)
        'important': ['claude', 'gemini'],          # 중요 (품질)
        'emergency': ['claude', 'openai', 'gemini'] # 긴급 (전부)
    }
}

# ============================================================
# 텔레그램 알림
# ============================================================

TELEGRAM = {
    'enabled': True,
    'bot_token': TELEGRAM_BOT_TOKEN,
    'chat_id': TELEGRAM_CHAT_ID,

    'notify': {
        'trade': True,
        'risk': True,
        'system': True,
        'ai': True,
        'daily_report': True
    },

    # 승인 모드
    'approval_mode': 'opt_out',  # 'opt_in' | 'opt_out' | 'none'
    'approval_timeout': 10,
    'approval_threshold': {
        'spot': 50000,
        'futures': 50000
    }
}

# ============================================================
# 상태 관리 & 로깅
# ============================================================

STATE_FILE = 'data/state.json'

CONNECTION_RETRY = {
    'max_retries': 4,
    'delays': [3, 10, 30, 60]  # 초
}

LOGGING = {
    'level': 'INFO',
    'file': 'data/logs/trading.log',
    'max_size': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5
}

# ============================================================
# 시스템 버전
# ============================================================

SYSTEM_VERSION = "v3.0_event_driven"
SYSTEM_NAME = "CoinMoney AI Trading Bot"


# ============================================================
# 유틸리티 함수
# ============================================================

def validate_config():
    """설정 유효성 검증"""
    errors = []

    # API 키 체크
    if not UPBIT_ACCESS_KEY or not UPBIT_SECRET_KEY:
        errors.append("업비트 API 키 누락")

    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        errors.append("바이낸스 API 키 누락")

    # AI 키 체크
    ai_keys_present = bool(CLAUDE_API_KEY or OPENAI_API_KEY or GEMINI_API_KEY)
    if AI_CONFIG['enabled'] and not ai_keys_present:
        errors.append("AI 활성화되었으나 API 키 없음")

    # 투자 설정 체크
    if SPOT_ALLOCATION + FUTURES_ALLOCATION != 1.0:
        errors.append(f"현물+선물 배분 합계 != 100% ({SPOT_ALLOCATION + FUTURES_ALLOCATION})")

    if errors:
        return False, errors

    return True, []


def get_ai_model_string(provider):
    """AI 제공자별 모델 문자열"""
    models = {
        'claude': 'claude-sonnet-4-5-20250929',
        'openai': 'gpt-4o',
        'gemini': 'gemini-1.5-pro'
    }
    return models.get(provider)


def get_config_summary():
    """설정 요약 출력"""
    summary = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{SYSTEM_NAME} ({SYSTEM_VERSION})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 투자 설정:
   총 투자금: {TOTAL_INVESTMENT:,}원
   현물: {SPOT_BUDGET:,}원 ({SPOT_ALLOCATION*100:.0f}%)
   선물: {FUTURES_BUDGET:,}원 ({FUTURES_ALLOCATION*100:.0f}%)

🎯 거래 코인:
   현물: {', '.join(TRADING_COINS['spot'])}
   선물: {', '.join(TRADING_COINS['futures'])}

🤖 AI 시스템:
   활성화: {'✅' if AI_CONFIG['enabled'] else '❌'}
   제공자: {', '.join(AI_CONFIG['providers'])}
   이벤트 드리븐: ✅
   AI 호출 임계값: {AI_TRIGGER_CONFIG['call_threshold']}점
   최소 간격: {AI_MIN_INTERVAL//60}분

📊 전략:
   현물: {', '.join(ENABLED_STRATEGIES['spot'])}
   선물: {', '.join(ENABLED_STRATEGIES['futures'])}

⚠️ 리스크:
   일일 손실 한도: {GLOBAL_RISK['daily_loss_limit']*100:.0f}%
   연속 손실 한도: {GLOBAL_RISK['max_consecutive_losses']}회
   계좌 손실 한도: {GLOBAL_RISK['account_drawdown_limit']*100:.0f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return summary


# ============================================================
# 테스트/검증
# ============================================================

if __name__ == "__main__":
    print("🧪 설정 파일 검증\n")

    # 설정 유효성 검증
    is_valid, errors = validate_config()

    if is_valid:
        print("✅ 설정 유효성 검증 통과\n")
        print(get_config_summary())
    else:
        print("❌ 설정 오류:\n")
        for error in errors:
            print(f"  - {error}")
        print("\n.env 파일을 확인하세요!")