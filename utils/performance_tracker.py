"""
성과 추적기
실제 거래 + 놓친 기회 + 회피한 손실 + 실패 원인 분석 + 자동 파라미터 조정
"""
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
from datetime import datetime, timedelta
from collections import defaultdict
from utils.logger import info, warning

class PerformanceTracker:
    """성과 추적기 (실패 원인 분석 + 자동 조정 포함)"""

    def __init__(self, data_file='data/performance.json'):
        self.data_file = data_file
        self.data = self._load_data()

    def _load_data(self):
        """데이터 로드"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass

        return {
            'actual_trades': [],
            'missed_opportunities': [],
            'avoided_losses': [],
            'signals_tracked': {},
            'start_date': datetime.now().isoformat()
        }

    def _save_data(self):
        """데이터 저장"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)

        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def record_actual_trade(self, exchange, coin, action, entry_price, exit_price,
                           quantity, pnl, reason, entry_time=None,
                           news_decision=None, news_urgency=0.0):
        """
        실제 거래 기록 + 자동 파라미터 조정

        Args:
            exchange: 'spot' or 'futures'
            coin: "KRW-BTC" or "BTCUSDT"
            action: 'BUY' or 'SELL'
            entry_price: 진입가
            exit_price: 청산가
            quantity: 수량
            pnl: 손익
            reason: 진입/청산 사유
            entry_time: 진입 시간
            news_decision: 'NEWS_PRIORITY' / 'CHART_PRIORITY' / 'BALANCED'
            news_urgency: 뉴스 중요도 (0~10)
        """
        trade = {
            'type': 'ACTUAL',
            'exchange': exchange,
            'coin': coin,
            'action': action,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'pnl': pnl,
            'success': pnl > 0,
            'return_percent': ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0,
            'reason': reason,
            'entry_time': entry_time or datetime.now().isoformat(),
            'exit_time': datetime.now().isoformat(),

            # 뉴스 관련 추가
            'news_decision': news_decision,
            'news_urgency': news_urgency,
            'failure_type': self._analyze_failure_type(pnl, news_decision, news_urgency)
        }

        self.data['actual_trades'].append(trade)
        self._save_data()

        # 로그
        status = '✅ 수익' if pnl > 0 else '❌ 손실'
        info(f"{status} 기록: {coin} {pnl:+,.0f}원 ({trade['return_percent']:+.2f}%)")

        # 실패 원인 로그 + 자동 파라미터 조정
        if trade['failure_type']:
            warning(f"⚠️ 실패 원인: {self._get_failure_name(trade['failure_type'])}")

            # 🔥 자동 파라미터 조정 시도 (조건부!)
            try:
                from config.master_config import adjust_param_on_failure
                adjusted = adjust_param_on_failure(trade['failure_type'])

                if adjusted:
                    info("⚙️ 파라미터 자동 조정 완료")
            except Exception as e:
                warning(f"⚠️ 파라미터 조정 오류: {e}")

    def _analyze_failure_type(self, pnl, news_decision, news_urgency):
        """
        실패 원인 분석

        Returns:
            str: 실패 원인 타입
        """
        if pnl >= 0:
            return None  # 성공

        # 손실인 경우 원인 분석
        if news_urgency >= 7.0:
            # 뉴스 중요도 높음
            if news_decision == 'NEWS_PRIORITY':
                return 'NEWS_OVERRELIANCE'  # 뉴스를 너무 따랐다
            else:
                return 'NEWS_IGNORED'  # 중요한 뉴스를 무시했다

        elif news_urgency <= 3.0:
            # 뉴스 중요도 낮음
            if news_decision == 'CHART_PRIORITY':
                return 'CHART_OVERRELIANCE'  # 차트만 봤다
            else:
                return 'CHART_IGNORED'  # 차트를 무시했다 (드물지만)

        else:
            # 중간 (3~7)
            return 'BALANCED_FAILURE'  # 균형있게 판단했지만 실패

    def _get_failure_name(self, failure_type):
        """실패 타입 한글명"""
        names = {
            'NEWS_OVERRELIANCE': '뉴스 과신 (뉴스를 너무 따랐다)',
            'NEWS_IGNORED': '뉴스 무시 (중요 뉴스를 안 따랐다)',
            'CHART_OVERRELIANCE': '차트 과신 (차트만 봤다)',
            'CHART_IGNORED': '차트 무시 (차트를 안 봤다)',
            'BALANCED_FAILURE': '균형 실패 (적절히 판단했으나 실패)'
        }
        return names.get(failure_type, failure_type)

    def track_signal(self, exchange, coin, signal, score, reasons):
        """
        신호 추적 시작

        Args:
            exchange: 'spot' or 'futures'
            coin: 코인
            signal: 'BUY' or 'SELL'
            score: 신호 점수
            reasons: 신호 근거

        Returns:
            str: tracking_id
        """
        tracking_id = f"{exchange}_{coin}_{datetime.now().timestamp()}"

        self.data['signals_tracked'][tracking_id] = {
            'exchange': exchange,
            'coin': coin,
            'signal': signal,
            'score': score,
            'reasons': reasons,
            'signal_price': None,
            'signal_time': datetime.now().isoformat(),
            'executed': False,
            'skip_reason': None,
            'outcome_checked': False
        }

        self._save_data()
        return tracking_id

    def mark_signal_executed(self, tracking_id, executed=True, skip_reason=None):
        """신호 실행 여부 마킹"""
        if tracking_id in self.data['signals_tracked']:
            self.data['signals_tracked'][tracking_id]['executed'] = executed
            self.data['signals_tracked'][tracking_id]['skip_reason'] = skip_reason
            self._save_data()

    def check_missed_opportunity(self, tracking_id, current_price, hours_later=1):
        """놓친 기회 체크 (신호 후 N시간 뒤)"""
        if tracking_id not in self.data['signals_tracked']:
            return

        signal_data = self.data['signals_tracked'][tracking_id]

        # 이미 체크했으면 스킵
        if signal_data['outcome_checked']:
            return

        # 실행했으면 스킵
        if signal_data['executed']:
            signal_data['outcome_checked'] = True
            self._save_data()
            return

        # 신호 가격 설정 (첫 체크 시)
        if signal_data['signal_price'] is None:
            signal_data['signal_price'] = current_price
            self._save_data()
            return

        # 시간 체크
        signal_time = datetime.fromisoformat(signal_data['signal_time'])
        if datetime.now() - signal_time < timedelta(hours=hours_later):
            return

        # 가상 손익 계산
        signal_price = signal_data['signal_price']

        if signal_data['signal'] == 'BUY':
            would_be_return = (current_price - signal_price) / signal_price * 100
            would_be_pnl = 100000 * (would_be_return / 100)
        else:
            would_be_return = (signal_price - current_price) / signal_price * 100
            would_be_pnl = 100000 * (would_be_return / 100)

        # 결과에 따라 분류
        if would_be_pnl > 0:
            self._record_missed_opportunity(signal_data, would_be_pnl, would_be_return)
        else:
            self._record_avoided_loss(signal_data, would_be_pnl, would_be_return)

        signal_data['outcome_checked'] = True
        self._save_data()

    def _record_missed_opportunity(self, signal_data, would_be_pnl, would_be_return):
        """놓친 기회 기록"""
        missed = {
            'type': 'MISSED',
            'exchange': signal_data['exchange'],
            'coin': signal_data['coin'],
            'signal': signal_data['signal'],
            'score': signal_data['score'],
            'reasons': signal_data['reasons'],
            'skip_reason': signal_data['skip_reason'],
            'would_be_pnl': would_be_pnl,
            'would_be_return': would_be_return,
            'signal_time': signal_data['signal_time'],
            'check_time': datetime.now().isoformat(),
            'error_type': 'Type 2 (False Negative)'
        }

        self.data['missed_opportunities'].append(missed)
        self._save_data()

        warning(f"📉 놓친 기회: {signal_data['coin']} {would_be_pnl:+,.0f}원 ({would_be_return:+.2f}%)")
        warning(f"   사유: {signal_data['skip_reason']}")

    def _record_avoided_loss(self, signal_data, would_be_loss, would_be_return):
        """회피한 손실 기록"""
        avoided = {
            'type': 'AVOIDED',
            'exchange': signal_data['exchange'],
            'coin': signal_data['coin'],
            'signal': signal_data['signal'],
            'score': signal_data['score'],
            'reasons': signal_data['reasons'],
            'skip_reason': signal_data['skip_reason'],
            'would_be_loss': abs(would_be_loss),
            'would_be_return': would_be_return,
            'signal_time': signal_data['signal_time'],
            'check_time': datetime.now().isoformat(),
            'decision': 'Good Decision!'
        }

        self.data['avoided_losses'].append(avoided)
        self._save_data()

        info(f"✅ 손실 회피: {signal_data['coin']} {would_be_loss:+,.0f}원 ({would_be_return:+.2f}%)")
        info(f"   사유: {signal_data['skip_reason']}")

    def get_performance_report(self, days=30):
        """성과 리포트 생성 (실패 원인 포함)"""
        cutoff_date = datetime.now() - timedelta(days=days)

        # 기간 필터링
        actual = [t for t in self.data['actual_trades']
                 if datetime.fromisoformat(t['exit_time']) > cutoff_date]

        missed = [m for m in self.data['missed_opportunities']
                 if datetime.fromisoformat(m['check_time']) > cutoff_date]

        avoided = [a for a in self.data['avoided_losses']
                  if datetime.fromisoformat(a['check_time']) > cutoff_date]

        # 실제 거래 분석
        total_trades = len(actual)
        winning_trades = len([t for t in actual if t['success']])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        total_pnl = sum(t['pnl'] for t in actual)

        # 실패 원인 분류
        failure_types = defaultdict(int)
        for t in actual:
            if not t['success'] and t.get('failure_type'):
                failure_types[t['failure_type']] += 1

        # 놓친 기회 분석
        missed_count = len(missed)
        missed_profits = sum(m['would_be_pnl'] for m in missed)

        # 놓친 이유별 분류
        missed_reasons = defaultdict(int)
        for m in missed:
            missed_reasons[m['skip_reason']] += 1

        # 회피한 손실 분석
        avoided_count = len(avoided)
        avoided_losses = sum(a['would_be_loss'] for a in avoided)

        # 종합
        potential_pnl = total_pnl + missed_profits
        efficiency = (total_pnl / potential_pnl * 100) if potential_pnl > 0 else 0

        return {
            'period_days': days,
            'actual_trades': {
                'total': total_trades,
                'winning': winning_trades,
                'losing': total_trades - winning_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'failure_types': dict(failure_types)
            },
            'missed_opportunities': {
                'count': missed_count,
                'missed_profits': missed_profits,
                'reasons': dict(missed_reasons)
            },
            'avoided_losses': {
                'count': avoided_count,
                'avoided_amount': avoided_losses
            },
            'summary': {
                'actual_pnl': total_pnl,
                'potential_pnl': potential_pnl,
                'efficiency': efficiency,
                'net_performance': total_pnl + avoided_losses - missed_profits
            }
        }

    def print_report(self, days=30):
        """리포트 출력 (실패 원인 포함)"""
        report = self.get_performance_report(days)

        print("\n" + "="*60)
        print(f"📊 성과 분석 리포트 (최근 {days}일)")
        print("="*60)

        # 실제 거래
        actual = report['actual_trades']
        print(f"\n📈 실제 거래:")
        print(f"  총 거래: {actual['total']}회")
        print(f"  승리: {actual['winning']}회 | 패배: {actual['losing']}회")
        print(f"  승률: {actual['win_rate']:.1f}%")
        print(f"  실제 수익: {actual['total_pnl']:+,.0f}원")

        # 실패 원인 분석
        failure_types = actual.get('failure_types', {})
        if failure_types:
            print(f"\n📉 실패 원인 분석:")

            failure_names = {
                'NEWS_OVERRELIANCE': '뉴스 과신 (뉴스를 너무 따랐다)',
                'NEWS_IGNORED': '뉴스 무시 (중요 뉴스를 안 따랐다)',
                'CHART_OVERRELIANCE': '차트 과신 (차트만 봤다)',
                'CHART_IGNORED': '차트 무시 (차트를 안 봤다)',
                'BALANCED_FAILURE': '균형 실패 (적절히 판단했으나 실패)'
            }

            for ftype, count in sorted(failure_types.items(),
                                       key=lambda x: x[1], reverse=True):
                name = failure_names.get(ftype, ftype)
                percentage = (count / actual['losing'] * 100) if actual['losing'] > 0 else 0
                print(f"  - {name}: {count}회 ({percentage:.1f}%)")

        # 놓친 기회
        missed = report['missed_opportunities']
        print(f"\n📉 놓친 기회 (Type 2 Error):")
        print(f"  놓친 횟수: {missed['count']}회")
        print(f"  놓친 수익: +{missed['missed_profits']:,.0f}원")
        if missed['reasons']:
            print(f"  주요 원인:")
            for reason, count in sorted(missed['reasons'].items(),
                                       key=lambda x: x[1], reverse=True):
                print(f"    - {reason}: {count}회")

        # 회피한 손실
        avoided = report['avoided_losses']
        print(f"\n✅ 회피한 손실 (Good Decision!):")
        print(f"  회피 횟수: {avoided['count']}회")
        print(f"  피한 손실: {avoided['avoided_amount']:,.0f}원")

        # 종합
        summary = report['summary']
        print(f"\n💰 종합:")
        print(f"  실제 PnL: {summary['actual_pnl']:+,.0f}원")
        print(f"  잠재 PnL: {summary['potential_pnl']:+,.0f}원 (놓친 기회 포함)")
        print(f"  순 성과: {summary['net_performance']:+,.0f}원 (회피 포함)")
        print(f"  ")
        print(f"📊 효율성: {summary['efficiency']:.1f}%")
        print(f"   (실제 수익 / 잠재 수익)")

        print("\n" + "="*60)


# 전역 인스턴스
performance_tracker = PerformanceTracker()


# 사용 예시
if __name__ == "__main__":
    print("🧪 Performance Tracker 테스트 (자동 파라미터 조정)\n")

    # 1. 성공 거래
    print("1️⃣ 성공 거래 (차트 우선)...")
    performance_tracker.record_actual_trade(
        exchange='spot',
        coin='KRW-BTC',
        action='BUY',
        entry_price=95000000,
        exit_price=97000000,
        quantity=0.001,
        pnl=50000,
        reason='Multi-Indicator',
        news_decision='CHART_PRIORITY',
        news_urgency=2.5
    )

    # 2. 실패 - 뉴스 과신
    print("\n2️⃣ 손실 거래 (뉴스 과신)...")
    performance_tracker.record_actual_trade(
        exchange='spot',
        coin='KRW-ETH',
        action='BUY',
        entry_price=3000000,
        exit_price=2900000,
        quantity=0.01,
        pnl=-30000,
        reason='뉴스: 대규모 투자 발표',
        news_decision='NEWS_PRIORITY',
        news_urgency=8.5
    )

    # 3. 실패 - 뉴스 무시
    print("\n3️⃣ 손실 거래 (뉴스 무시)...")
    performance_tracker.record_actual_trade(
        exchange='spot',
        coin='KRW-XRP',
        action='BUY',
        entry_price=1000,
        exit_price=950,
        quantity=100,
        pnl=-5000,
        reason='차트: RSI 과매도',
        news_decision='CHART_PRIORITY',
        news_urgency=9.0
    )

    # 4. 실패 - 차트 과신
    print("\n4️⃣ 손실 거래 (차트 과신)...")
    performance_tracker.record_actual_trade(
        exchange='spot',
        coin='KRW-DOGE',
        action='BUY',
        entry_price=200,
        exit_price=190,
        quantity=500,
        pnl=-5000,
        reason='차트: MACD 골든크로스',
        news_decision='CHART_PRIORITY',
        news_urgency=1.5
    )

    # 5. 실패 - 균형 실패
    print("\n5️⃣ 손실 거래 (균형 실패)...")
    performance_tracker.record_actual_trade(
        exchange='spot',
        coin='KRW-ADA',
        action='BUY',
        entry_price=500,
        exit_price=480,
        quantity=200,
        pnl=-4000,
        reason='차트+뉴스 종합 판단',
        news_decision='BALANCED',
        news_urgency=5.0
    )

    # 6. 리포트 출력
    performance_tracker.print_report(days=30)

    print("\n✅ 테스트 완료!")