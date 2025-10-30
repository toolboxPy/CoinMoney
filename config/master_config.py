"""
마스터 설정 파일 (v3.3 - 동적 예산)
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
# 투자 설정 (🔥 동적 예산으로 변경!)
# ============================================================

# 🔥 정적 예산 제거 - 실시간 잔고 사용!
# TOTAL_INVESTMENT = 1000000  # ❌ 사용 안 함
# SPOT_ALLOCATION = 0.6
# FUTURES_ALLOCATION = 0.4
# SPOT_BUDGET = ...  # ❌ 삭제됨!

# ✅ 포트폴리오는 실시간 KRW 잔고에서 자동 계산됨
# main.py에서 upbit.get_balance("KRW")로 조회

# ============================================================
# 시간 프레임 & 체크 주기
# ============================================================

TIMEFRAMES = {
    'spot': {
        'primary': 'minute30',
        'secondary': 'minute15',
        'long_term': 'minute60'
    },
    'futures': {
        'primary': 'minute60',
        'secondary': 'minute30',
        'long_term': 'minute240'
    }
}

# 메인 루프 체크 주기 (초)
CHECK_INTERVALS = {
    'main_loop': 30,
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
FUTURES_MARGIN_MODE = "ISOLATED"

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
        'take_profit_1': 0.015,
        'take_profit_2': 0.025,
        'stop_loss': -0.02,
        'trailing_stop': 0.01
    },
    'futures_minute60': {
        'take_profit_1': 0.02,
        'take_profit_2': 0.03,
        'stop_loss': -0.015,
        'trailing_stop': 0.01
    }
}

# ============================================================
# 글로벌 리스크 관리
# ============================================================

GLOBAL_RISK = {
    'daily_loss_limit': 0.05,
    'max_consecutive_losses': 4,
    'account_drawdown_limit': 0.15,

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
        'percent_per_trade': 0.15
    },
    'futures': {
        'min_investment': 10000,
        'max_investment': 80000,
        'percent_per_trade': 0.2
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
    'providers': ['claude', 'openai', 'gemini'],
    'voting_method': 'majority',
    'weights': {
        'claude': 0.4,
        'openai': 0.3,
        'gemini': 0.3
    },
    'min_confidence': 0.7,
    'timeout': 10,
    'fallback_on_failure': True,
    'max_failure_count': 3
}

# ============================================================
# AI 호출 트리거 (v3.0 이벤트 드리븐)
# ============================================================

AI_TRIGGER_CONFIG = {
    'price_change_5m': 3.0,
    'price_change_1h': 5.0,
    'volume_surge': 2.5,
    'volatility': 5.0,
    'pattern_score': 7.0,
    'support_resistance': 0.02,
    'indicator_conflict': 3.0,
    'news_urgency': 6.5,
    'news_count_1h': 5,
    'position_risk': 0.8,
    'pnl_critical': 0.02,
    'call_threshold': 50.0
}

AI_MIN_INTERVAL = 180

# ============================================================
# AI 토론 설정 (v2.0)
# ============================================================

AI_DEBATE_V2_CONFIG = {
    'rounds': 2,
    'compression': True,
    'min_agreement': 0.7,
    'adaptive_ai_selection': True,
    'ai_selection_rules': {
        'normal': ['gemini'],
        'important': ['claude', 'gemini'],
        'emergency': ['claude', 'openai', 'gemini']
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
    'approval_mode': 'opt_out',
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
    'delays': [3, 10, 30, 60]
}

LOGGING = {
    'level': 'INFO',
    'file': 'data/logs/trading.log',
    'max_size': 10 * 1024 * 1024,
    'backup_count': 5
}

# ============================================================
# 시스템 버전
# ============================================================

SYSTEM_VERSION = "v3.3_dynamic_budget"
SYSTEM_NAME = "CoinMoney AI Trading Bot"


# ============================================================
# 유틸리티 함수
# ============================================================

def validate_config():
    """설정 유효성 검증"""
    errors = []

    if not UPBIT_ACCESS_KEY or not UPBIT_SECRET_KEY:
        errors.append("업비트 API 키 누락")

    ai_keys_present = bool(CLAUDE_API_KEY or OPENAI_API_KEY or GEMINI_API_KEY)
    if AI_CONFIG['enabled'] and not ai_keys_present:
        errors.append("AI 활성화되었으나 API 키 없음")

    return len(errors) == 0, errors


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
   예산: 실시간 KRW 잔고 사용 (동적)

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


if __name__ == "__main__":
    print("🧪 설정 파일 검증\n")
    is_valid, errors = validate_config()

    if is_valid:
        print("✅ 설정 유효성 검증 통과\n")
        print(get_config_summary())
    else:
        print("❌ 설정 오류:\n")
        for error in errors:
            print(f"  - {error}")
        print("\n.env 파일을 확인하세요!")