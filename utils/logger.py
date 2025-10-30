"""
로깅 시스템
모든 거래 내역과 시스템 로그를 기록
"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from config.master_config import LOGGING

class TradingLogger:
    """트레이딩 로거"""

    _instance = None
    _initialized = False

    def __new__(cls):
        """싱글톤 패턴"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """초기화 (한 번만 실행)"""
        if self._initialized:
            return

        self._initialized = True

        # 로그 디렉토리 생성
        log_dir = os.path.dirname(LOGGING['file'])
        os.makedirs(log_dir, exist_ok=True)

        # 로거 설정
        self.logger = logging.getLogger('CoinMoney')
        self.logger.setLevel(getattr(logging, LOGGING['level']))

        # 기존 핸들러 제거 (중복 방지)
        self.logger.handlers.clear()

        # 파일 핸들러 (회전 로그)
        file_handler = RotatingFileHandler(
            LOGGING['file'],
            maxBytes=LOGGING['max_size'],
            backupCount=LOGGING['backup_count'],
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)

        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 포맷 설정
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # 핸들러 추가
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.logger.info("=" * 60)
        self.logger.info("🤖 CoinMoney Bot 로거 초기화 완료")
        self.logger.info("=" * 60)

    def info(self, message):
        """정보 로그"""
        self.logger.info(message)

    def warning(self, message):
        """경고 로그"""
        self.logger.warning(message)

    def error(self, message):
        """에러 로그"""
        self.logger.error(message)

    def debug(self, message):
        """디버그 로그"""
        self.logger.debug(message)

    def trade(self, action, coin, price, amount, reason=''):
        """
        거래 로그 (특별 포맷)

        Args:
            action: BUY, SELL, STOP_LOSS, TAKE_PROFIT
            coin: 코인 이름
            price: 가격
            amount: 수량
            reason: 이유
        """
        emoji = {
            'BUY': '📈',
            'SELL': '💰',
            'STOP_LOSS': '🛡️',
            'TAKE_PROFIT': '🎯'
        }.get(action, '📊')

        message = f"{emoji} [{action}] {coin} @ {price:,.0f}원 | 수량: {amount:.8f}"
        if reason:
            message += f" | 사유: {reason}"

        self.logger.info(message)

    def risk_alert(self, level, message):
        """
        리스크 경고

        Args:
            level: LOW, MEDIUM, HIGH, CRITICAL
            message: 경고 메시지
        """
        emoji = {
            'LOW': '⚠️',
            'MEDIUM': '🚨',
            'HIGH': '☠️',
            'CRITICAL': '💥'
        }.get(level, '⚠️')

        self.logger.warning(f"{emoji} [RISK-{level}] {message}")

    def ai_analysis(self, provider, regime, confidence):
        """
        AI 분석 로그

        Args:
            provider: claude, openai, gemini
            regime: 시장 국면
            confidence: 신뢰도
        """
        self.logger.info(
            f"🤖 [AI-{provider.upper()}] 시장: {regime} | "
            f"신뢰도: {confidence*100:.0f}%"
        )

    def system_event(self, event, details=''):
        """
        시스템 이벤트

        Args:
            event: START, STOP, ERROR, RESTART
            details: 상세 정보
        """
        emoji = {
            'START': '🚀',
            'STOP': '⏸️',
            'ERROR': '❌',
            'RESTART': '🔄'
        }.get(event, '📌')

        message = f"{emoji} [SYSTEM-{event}]"
        if details:
            message += f" {details}"

        self.logger.info(message)

    def daily_summary(self, stats):
        """
        일일 요약 로그

        Args:
            stats: 통계 딕셔너리
        """
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📊 일일 거래 요약")
        self.logger.info("=" * 60)
        self.logger.info(f"총 거래: {stats.get('total_trades', 0)}회")
        self.logger.info(f"승리: {stats.get('wins', 0)}회 | 패배: {stats.get('losses', 0)}회")
        self.logger.info(f"승률: {stats.get('win_rate', 0)*100:.1f}%")
        self.logger.info(f"손익: {stats.get('pnl', 0):+,.0f}원")
        self.logger.info(f"수익률: {stats.get('return', 0)*100:+.2f}%")
        self.logger.info("=" * 60 + "\n")


# 전역 로거 인스턴스
logger = TradingLogger()


# 편의 함수들
def info(message):
    """정보 로그"""
    logger.info(message)


def warning(message):
    """경고 로그"""
    logger.warning(message)


def error(message):
    """에러 로그"""
    logger.error(message)


def debug(message):
    """디버그 로그"""
    logger.debug(message)


def trade_log(action, coin, price, amount, reason=''):
    """거래 로그"""
    logger.trade(action, coin, price, amount, reason)


def risk_alert(level, message):
    """리스크 경고"""
    logger.risk_alert(level, message)


def ai_log(provider, regime, confidence):
    """AI 분석 로그"""
    logger.ai_analysis(provider, regime, confidence)


def system_log(event, details=''):
    """시스템 이벤트"""
    logger.system_event(event, details)


def daily_summary(stats):
    """일일 요약"""
    logger.daily_summary(stats)


# 사용 예시
if __name__ == "__main__":
    # 테스트
    info("로거 테스트 시작")
    trade_log('BUY', 'KRW-BTC', 95000000, 0.00105, 'RSI 과매도')
    risk_alert('MEDIUM', '일일 손실 -3%')
    ai_log('claude', 'STRONG_UPTREND', 0.85)
    system_log('START', '봇 시작')

    daily_summary({
        'total_trades': 10,
        'wins': 6,
        'losses': 4,
        'win_rate': 0.6,
        'pnl': 15000,
        'return': 0.015
    })