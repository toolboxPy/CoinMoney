"""
글로벌 리스크 관리자
최후의 방어선 - 계좌 전체 보호
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import datetime
from config.master_config import GLOBAL_RISK, TOTAL_INVESTMENT
from utils.logger import info, warning, error, risk_alert
from utils.state_manager import state_manager


class GlobalRiskManager:
    """글로벌 리스크 관리자"""

    def __init__(self):
        self.config = GLOBAL_RISK
        self.trading_enabled = True
        self.emergency_stop_reason = None

        info("🛡️ 글로벌 리스크 관리자 초기화")
        info(f"  일일 손실 한도: {self.config['daily_loss_limit'] * 100}%")
        info(f"  최대 연속 손실: {self.config['max_consecutive_losses']}회")
        info(f"  계좌 낙폭 한도: {self.config['account_drawdown_limit'] * 100}%")

    def check_risk_limits(self):
        """
        리스크 한도 체크

        Returns:
            dict: {
                'trading_allowed': bool,
                'warnings': [],
                'emergency_stop': bool,
                'reason': str
            }
        """
        warnings_list = []
        emergency_stop = False
        stop_reason = None

        # 1. 일일 손실 한도 체크
        daily_loss = self._check_daily_loss()
        if daily_loss['exceeded']:
            emergency_stop = True
            stop_reason = f"일일 손실 한도 초과: {daily_loss['percent']:.2f}%"
            risk_alert('CRITICAL', stop_reason)
        elif daily_loss['warning']:
            warnings_list.append(f"일일 손실 경고: {daily_loss['percent']:.2f}%")
            risk_alert('MEDIUM', warnings_list[-1])

        # 2. 연속 손실 체크
        consecutive = self._check_consecutive_losses()
        if consecutive['exceeded']:
            emergency_stop = True
            stop_reason = stop_reason or f"연속 손실 {consecutive['count']}회"
            risk_alert('CRITICAL', f"연속 손실 {consecutive['count']}회")
        elif consecutive['warning']:
            warnings_list.append(f"연속 손실 경고: {consecutive['count']}회")
            risk_alert('MEDIUM', warnings_list[-1])

        # 3. 계좌 전체 낙폭 체크
        drawdown = self._check_account_drawdown()
        if drawdown['exceeded']:
            emergency_stop = True
            stop_reason = stop_reason or f"계좌 낙폭 {drawdown['percent']:.2f}%"
            risk_alert('CRITICAL', f"계좌 낙폭 한도 초과: {drawdown['percent']:.2f}%")
        elif drawdown['warning']:
            warnings_list.append(f"계좌 낙폭 경고: {drawdown['percent']:.2f}%")
            risk_alert('HIGH', warnings_list[-1])

        # 4. 포지션 수 체크
        positions = self._check_position_limits()
        if positions['spot_exceeded']:
            warnings_list.append(f"현물 포지션 초과: {positions['spot_count']}개")
        if positions['futures_exceeded']:
            warnings_list.append(f"선물 포지션 초과: {positions['futures_count']}개")

        # 5. 일일 거래 횟수 체크
        trades = self._check_trade_limits()
        if trades['spot_exceeded']:
            warnings_list.append(f"현물 거래 한도 초과: {trades['spot_count']}회")
        if trades['futures_exceeded']:
            warnings_list.append(f"선물 거래 한도 초과: {trades['futures_count']}회")

        # 긴급 중단 처리
        if emergency_stop:
            self.emergency_stop(stop_reason)

        return {
            'trading_allowed': self.trading_enabled and not emergency_stop,
            'warnings': warnings_list,
            'emergency_stop': emergency_stop,
            'reason': stop_reason
        }

    def _check_daily_loss(self):
        """일일 손실 체크"""
        risk_stats = state_manager.get_risk_stats()
        daily_loss_percent = abs(risk_stats['daily_loss_percent'])

        limit = self.config['daily_loss_limit']
        warning_threshold = limit * 0.7  # 70% 도달 시 경고

        return {
            'percent': daily_loss_percent * 100,
            'exceeded': daily_loss_percent >= limit,
            'warning': daily_loss_percent >= warning_threshold
        }

    def _check_consecutive_losses(self):
        """연속 손실 체크"""
        risk_stats = state_manager.get_risk_stats()
        consecutive = risk_stats['consecutive_losses']

        limit = self.config['max_consecutive_losses']
        warning_threshold = limit - 1

        return {
            'count': consecutive,
            'exceeded': consecutive >= limit,
            'warning': consecutive >= warning_threshold
        }

    def _check_account_drawdown(self):
        """계좌 낙폭 체크"""
        risk_stats = state_manager.get_risk_stats()
        max_drawdown = risk_stats['max_drawdown']

        limit = self.config['account_drawdown_limit']
        warning_threshold = limit * 0.7

        return {
            'percent': max_drawdown * 100,
            'exceeded': max_drawdown >= limit,
            'warning': max_drawdown >= warning_threshold
        }

    def _check_position_limits(self):
        """포지션 수 한도 체크"""
        spot_positions = state_manager.get_all_positions('spot')
        futures_positions = state_manager.get_all_positions('futures')

        spot_count = len(spot_positions)
        futures_count = len(futures_positions)

        return {
            'spot_count': spot_count,
            'spot_exceeded': spot_count >= self.config['max_positions']['spot'],
            'futures_count': futures_count,
            'futures_exceeded': futures_count >= self.config['max_positions']['futures']
        }

    def _check_trade_limits(self):
        """일일 거래 횟수 체크"""
        daily_stats = state_manager.get_daily_stats()

        return {
            'spot_count': daily_stats['spot_trades'],
            'spot_exceeded': daily_stats['spot_trades'] >= self.config['max_trades_per_day']['spot'],
            'futures_count': daily_stats['futures_trades'],
            'futures_exceeded': daily_stats['futures_trades'] >= self.config['max_trades_per_day']['futures']
        }

    def emergency_stop(self, reason):
        """
        긴급 중단

        Args:
            reason: 중단 사유
        """
        if not self.trading_enabled:
            return  # 이미 중단됨

        self.trading_enabled = False
        self.emergency_stop_reason = reason

        error("\n" + "=" * 60)
        error("🚨 긴급 중단 발동! 🚨")
        error("=" * 60)
        error(f"사유: {reason}")
        error(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        error("모든 거래가 중단되었습니다!")
        error("=" * 60 + "\n")

        # TODO: 텔레그램 긴급 알림
        # TODO: 모든 포지션 즉시 청산 (선택)

    def resume_trading(self):
        """거래 재개 (수동)"""
        info("\n🟢 거래 재개")
        self.trading_enabled = True
        self.emergency_stop_reason = None

    def can_open_position(self, exchange):
        """
        포지션 열기 가능 여부

        Args:
            exchange: 'spot' or 'futures'

        Returns:
            tuple: (가능여부, 사유)
        """
        if not self.trading_enabled:
            return False, f"긴급 중단: {self.emergency_stop_reason}"

        # 리스크 체크
        risk_check = self.check_risk_limits()
        if not risk_check['trading_allowed']:
            return False, risk_check['reason']

        # 포지션 수 체크
        positions = self._check_position_limits()
        if exchange == 'spot' and positions['spot_exceeded']:
            return False, f"현물 포지션 한도 초과 ({positions['spot_count']}개)"
        if exchange == 'futures' and positions['futures_exceeded']:
            return False, f"선물 포지션 한도 초과 ({positions['futures_count']}개)"

        # 거래 횟수 체크
        trades = self._check_trade_limits()
        if exchange == 'spot' and trades['spot_exceeded']:
            return False, f"현물 일일 거래 한도 초과 ({trades['spot_count']}회)"
        if exchange == 'futures' and trades['futures_exceeded']:
            return False, f"선물 일일 거래 한도 초과 ({trades['futures_count']}회)"

        return True, "OK"

    def get_status(self):
        """현재 리스크 상태"""
        risk_check = self.check_risk_limits()

        return {
            'trading_enabled': self.trading_enabled,
            'emergency_stop': risk_check['emergency_stop'],
            'warnings': risk_check['warnings'],
            'daily_loss': self._check_daily_loss(),
            'consecutive_losses': self._check_consecutive_losses(),
            'drawdown': self._check_account_drawdown(),
            'positions': self._check_position_limits(),
            'trades': self._check_trade_limits()
        }

    def get_statistics(self):
        """통계 정보 반환 (간단 버전)"""
        status = self.get_status()

        return {
            'daily_pnl': status['daily_loss']['percent'],
            'consecutive_losses': status['consecutive_losses']['count'],
            'max_drawdown': status['drawdown']['percent'],
            'spot_positions': status['positions']['spot_count'],
            'futures_positions': status['positions']['futures_count'],
            'spot_trades': status['trades']['spot_count'],
            'futures_trades': status['trades']['futures_count']
        }


# 전역 인스턴스
global_risk = GlobalRiskManager()

# 사용 예시
if __name__ == "__main__":
    print("🧪 Global Risk Manager 테스트\n")

    # 현재 상태
    status = global_risk.get_status()

    print("=" * 60)
    print("🛡️ 리스크 상태")
    print("=" * 60)
    print(f"\n거래 가능: {status['trading_enabled']}")
    print(f"긴급 중단: {status['emergency_stop']}")

    if status['warnings']:
        print(f"\n⚠️ 경고:")
        for w in status['warnings']:
            print(f"  - {w}")

    print(f"\n📊 일일 손실: {status['daily_loss']['percent']:.2f}%")
    print(f"🔄 연속 손실: {status['consecutive_losses']['count']}회")
    print(f"📉 최대 낙폭: {status['drawdown']['percent']:.2f}%")

    print(f"\n📦 포지션:")
    print(f"  현물: {status['positions']['spot_count']}/{global_risk.config['max_positions']['spot']}개")
    print(f"  선물: {status['positions']['futures_count']}/{global_risk.config['max_positions']['futures']}개")

    print(f"\n📈 거래 횟수:")
    print(f"  현물: {status['trades']['spot_count']}/{global_risk.config['max_trades_per_day']['spot']}회")
    print(f"  선물: {status['trades']['futures_count']}/{global_risk.config['max_trades_per_day']['futures']}회")

    print("\n" + "=" * 60)

    # 포지션 열기 가능 여부
    print("\n🔍 포지션 열기 테스트:")
    can_spot, reason_spot = global_risk.can_open_position('spot')
    print(f"  현물: {'✅ 가능' if can_spot else f'❌ 불가 - {reason_spot}'}")

    can_futures, reason_futures = global_risk.can_open_position('futures')
    print(f"  선물: {'✅ 가능' if can_futures else f'❌ 불가 - {reason_futures}'}")

    print("\n✅ 테스트 완료!")