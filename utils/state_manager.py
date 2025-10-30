"""
상태 관리 시스템
봇 재시작 시에도 포지션 유지
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
from datetime import datetime
from config.master_config import STATE_FILE
from utils.logger import info, warning, error


class StateManager:
    """상태 저장/복구 관리자"""

    def __init__(self, state_file=None):
        self.state_file = state_file or STATE_FILE
        self.state = self._load_state()

    def _load_state(self):
        """상태 파일 로드"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    info(f"✅ 상태 복구 완료: {self.state_file}")
                    return state
            except Exception as e:
                error(f"⚠️ 상태 파일 손상: {e}")
                return self._default_state()
        else:
            info("📝 새로운 상태 파일 생성")
            return self._default_state()

    def _default_state(self):
        """기본 상태"""
        return {
            'spot': {
                'in_position': False,
                'positions': {},
                'daily_trades': 0,
                'daily_pnl': 0,
                'total_trades': 0,
                'total_pnl': 0
            },
            'futures': {
                'in_position': False,
                'positions': {},
                'daily_trades': 0,
                'daily_pnl': 0,
                'total_trades': 0,
                'total_pnl': 0
            },
            'risk': {
                'consecutive_losses': 0,
                'max_drawdown': 0,
                'daily_loss_percent': 0
            },
            'last_update': datetime.now().isoformat(),
            'last_daily_reset': datetime.now().date().isoformat()
        }

    def save_state(self):
        """상태 저장 (원자적 쓰기)"""
        try:
            self.state['last_update'] = datetime.now().isoformat()

            # 디렉토리 확인
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

            # 임시 파일에 먼저 쓰기
            temp_file = self.state_file + '.tmp'

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)

            # 원본과 교체 (원자적)
            os.replace(temp_file, self.state_file)

        except Exception as e:
            error(f"❌ 상태 저장 실패: {e}")

    def update_position(self, exchange, coin, position_data):
        """
        포지션 업데이트

        Args:
            exchange: 'spot' or 'futures'
            coin: 코인 이름
            position_data: {entry_price, quantity, ...} or None (청산)
        """
        if position_data is None:
            # 청산
            if coin in self.state[exchange]['positions']:
                del self.state[exchange]['positions'][coin]
                info(f"📤 포지션 제거: {exchange} - {coin}")
        else:
            # 진입/업데이트
            self.state[exchange]['positions'][coin] = position_data
            info(f"📥 포지션 업데이트: {exchange} - {coin}")

        # in_position 플래그 업데이트
        self.state[exchange]['in_position'] = len(self.state[exchange]['positions']) > 0

        self.save_state()

    def get_position(self, exchange, coin):
        """포지션 조회"""
        return self.state[exchange]['positions'].get(coin)

    def get_all_positions(self, exchange):
        """모든 포지션 조회"""
        return self.state[exchange]['positions']

    def is_in_position(self, exchange, coin=None):
        """포지션 보유 중인지"""
        if coin:
            return coin in self.state[exchange]['positions']
        else:
            return self.state[exchange]['in_position']

    def record_trade(self, exchange, pnl, is_win):
        """
        거래 기록

        Args:
            exchange: 'spot' or 'futures'
            pnl: 손익
            is_win: 승리 여부
        """
        self.state[exchange]['daily_trades'] += 1
        self.state[exchange]['total_trades'] += 1
        self.state[exchange]['daily_pnl'] += pnl
        self.state[exchange]['total_pnl'] += pnl

        # 연속 손실 카운트
        if is_win:
            self.state['risk']['consecutive_losses'] = 0
        else:
            self.state['risk']['consecutive_losses'] += 1

        # 일일 손실률 업데이트
        total_daily_pnl = (
                self.state['spot']['daily_pnl'] +
                self.state['futures']['daily_pnl']
        )

        from config.master_config import TOTAL_INVESTMENT
        self.state['risk']['daily_loss_percent'] = total_daily_pnl / TOTAL_INVESTMENT

        self.save_state()

    def reset_daily_stats(self):
        """일일 통계 리셋 (자정)"""
        info("\n🌅 일일 통계 리셋")
        info(f"  현물 손익: {self.state['spot']['daily_pnl']:+,.0f}원")
        info(f"  선물 손익: {self.state['futures']['daily_pnl']:+,.0f}원")
        info(f"  현물 거래: {self.state['spot']['daily_trades']}회")
        info(f"  선물 거래: {self.state['futures']['daily_trades']}회")

        self.state['spot']['daily_trades'] = 0
        self.state['spot']['daily_pnl'] = 0
        self.state['futures']['daily_trades'] = 0
        self.state['futures']['daily_pnl'] = 0
        self.state['risk']['daily_loss_percent'] = 0
        self.state['last_daily_reset'] = datetime.now().date().isoformat()

        self.save_state()

    def update_risk(self, max_drawdown=None):
        """리스크 지표 업데이트"""
        if max_drawdown is not None:
            self.state['risk']['max_drawdown'] = max(
                self.state['risk']['max_drawdown'],
                max_drawdown
            )
            self.save_state()

    def get_risk_stats(self):
        """리스크 통계 조회"""
        return self.state['risk'].copy()

    def get_daily_stats(self, exchange=None):
        """일일 통계 조회"""
        if exchange:
            return {
                'daily_trades': self.state[exchange]['daily_trades'],
                'daily_pnl': self.state[exchange]['daily_pnl']
            }
        else:
            return {
                'spot_trades': self.state['spot']['daily_trades'],
                'spot_pnl': self.state['spot']['daily_pnl'],
                'futures_trades': self.state['futures']['daily_trades'],
                'futures_pnl': self.state['futures']['daily_pnl'],
                'total_pnl': (
                        self.state['spot']['daily_pnl'] +
                        self.state['futures']['daily_pnl']
                )
            }

    def print_status(self):
        """현재 상태 출력"""
        print("\n" + "=" * 60)
        print("💼 현재 상태")
        print("=" * 60)

        # 현물
        print("\n📊 현물 (Spot)")
        print(f"  포지션: {len(self.state['spot']['positions'])}개")
        for coin, pos in self.state['spot']['positions'].items():
            print(f"  - {coin}: {pos['quantity']:.8f} @ {pos['entry_price']:,.0f}원")
        print(f"  오늘 거래: {self.state['spot']['daily_trades']}회")
        print(f"  오늘 손익: {self.state['spot']['daily_pnl']:+,.0f}원")

        # 선물
        print("\n📈 선물 (Futures)")
        print(f"  포지션: {len(self.state['futures']['positions'])}개")
        for coin, pos in self.state['futures']['positions'].items():
            side = pos.get('side', 'LONG')
            print(f"  - {coin} [{side}]: {pos['quantity']:.8f} @ {pos['entry_price']:,.0f}")
        print(f"  오늘 거래: {self.state['futures']['daily_trades']}회")
        print(f"  오늘 손익: {self.state['futures']['daily_pnl']:+,.0f}원")

        # 리스크
        print("\n⚠️ 리스크")
        print(f"  연속 손실: {self.state['risk']['consecutive_losses']}회")
        print(f"  최대 낙폭: {self.state['risk']['max_drawdown'] * 100:.2f}%")
        print(f"  일일 손실: {self.state['risk']['daily_loss_percent'] * 100:.2f}%")

        print("\n" + "=" * 60 + "\n")


# 전역 인스턴스
state_manager = StateManager()

# 사용 예시
if __name__ == "__main__":
    print("🧪 State Manager 테스트\n")

    # 현재 상태 출력
    state_manager.print_status()

    # 포지션 추가
    print("📥 테스트: BTC 포지션 추가")
    state_manager.update_position('spot', 'KRW-BTC', {
        'entry_price': 95000000,
        'quantity': 0.00105,
        'investment': 100000,
        'entry_time': datetime.now().isoformat()
    })

    # 거래 기록
    print("📝 테스트: 거래 기록")
    state_manager.record_trade('spot', 1500, True)

    # 상태 출력
    state_manager.print_status()

    # 포지션 제거
    print("📤 테스트: 포지션 청산")
    state_manager.update_position('spot', 'KRW-BTC', None)

    # 최종 상태
    state_manager.print_status()