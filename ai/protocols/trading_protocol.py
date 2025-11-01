"""
트레이딩 압축 언어 프로토콜
"""
import json
import os
from datetime import datetime


class TradingProtocol:
    """트레이딩 압축 언어"""

    VERSION = "1.0"
    SAVE_PATH = "data/dynamic_protocol.json"

    # 기본 약어
    BASE_ABBREVIATIONS = {
        "SUP": "STRONG_UPTREND",
        "WUP": "WEAK_UPTREND",
        "SID": "SIDEWAYS",
        "WDN": "WEAK_DOWNTREND",
        "SDN": "STRONG_DOWNTREND",
        "RSI": "Relative Strength Index",
        "MACD": "Moving Average Convergence Divergence",
        "BB": "Bollinger Bands",
        "MA": "Moving Average",
        "VOL": "Volume",
        "BUY": "Buy signal",
        "SELL": "Sell signal",
        "HOLD": "Hold position",
        "EXIT": "Exit all",
        "BULL": "Bullish",
        "BEAR": "Bearish",
        "NEUT": "Neutral",
        "EMER": "Emergency",
        "NEWS_PRI": "News priority",
        "CHART_PRI": "Chart priority",
        "BALANCED": "Balanced"
    }

    # 동적 약어 (클래스 변수 - 모든 인스턴스 공유)
    DYNAMIC_ABBREVIATIONS = {}
    ABBREVIATION_META = {}

    def __init__(self):
        """초기화 + 파일에서 로드"""
        self.load_from_file()

    def get_ultra_compact_prompt(self):
        """
        초압축 프롬프트 반환

        Returns:
            str: 시스템 프롬프트 (약어 포함)
        """
        # 기본 약어
        base_abbrs = ", ".join([f"{k}={v}" for k, v in self.BASE_ABBREVIATIONS.items()])

        # 동적 약어
        dynamic_abbrs = ""
        if self.DYNAMIC_ABBREVIATIONS:
            dynamic_abbrs = "\n[추가약어] " + ", ".join([f"{k}={v}" for k, v in self.DYNAMIC_ABBREVIATIONS.items()])

        # 초압축 프롬프트
        prompt = f"""전문 암호화폐 트레이더 AI. 압축언어 사용, 토큰 최소화.

[약어] {base_abbrs}{dynamic_abbrs}

[응답] JSON만:
{{"regime":"SUP","confidence":0.85,"news_sentiment":"BULL","news_urgency":8.5,"emergency":false,"reason":"RSI과매수+VOL급증"}}

약어제안시(선택):
{{"...","suggested_abbreviations":[{{"abbr":"RLVH","meaning":"RSI Low Volume High","reason":"자주사용"}}]}}

[규칙] 1)약어필수 2)JSON만 3)reason<150토큰 4)소수점2자리 5)suggested_abbreviations는 필요시만"""

        return prompt

    def add_abbreviation(self, abbr, meaning, reason="AI suggested", ai_name="unknown"):
        """
        동적 약어 추가 + 자동 저장

        Args:
            abbr: 약어
            meaning: 의미
            reason: 추가 이유
            ai_name: AI 이름

        Returns:
            bool: 성공 여부
        """
        # 중복 체크
        if abbr in self.BASE_ABBREVIATIONS or abbr in self.DYNAMIC_ABBREVIATIONS:
            return False

        # 추가
        self.DYNAMIC_ABBREVIATIONS[abbr] = meaning

        # 메타데이터
        self.ABBREVIATION_META[abbr] = {
            'meaning': meaning,
            'reason': reason,
            'ai_name': ai_name,
            'added_at': datetime.now().isoformat(),
            'usage_count': 0
        }

        # 버전 증가
        major, minor = self.VERSION.split('.')
        self.VERSION = f"{major}.{int(minor) + 1}"

        print(f"✅ 약어 추가: {abbr} = {meaning} (by {ai_name})")

        # 자동 저장
        self.save_to_file()

        return True

    def save_to_file(self):
        """파일로 저장"""
        try:
            os.makedirs(os.path.dirname(self.SAVE_PATH), exist_ok=True)

            data = {
                'version': self.VERSION,
                'updated_at': datetime.now().isoformat(),
                'dynamic_abbreviations': self.DYNAMIC_ABBREVIATIONS,
                'metadata': self.ABBREVIATION_META
            }

            with open(self.SAVE_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"💾 프로토콜 저장: {self.SAVE_PATH}")

        except Exception as e:
            print(f"❌ 저장 실패: {e}")

    def load_from_file(self):
        """파일에서 로드"""
        if not os.path.exists(self.SAVE_PATH):
            print(f"📋 프로토콜 파일 없음 (신규)")
            return

        try:
            with open(self.SAVE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 클래스 변수 업데이트
            TradingProtocol.VERSION = data.get('version', '1.0')
            TradingProtocol.DYNAMIC_ABBREVIATIONS = data.get('dynamic_abbreviations', {})
            TradingProtocol.ABBREVIATION_META = data.get('metadata', {})

            print(f"📂 프로토콜 로드: v{self.VERSION} ({len(self.DYNAMIC_ABBREVIATIONS)}개 약어)")

        except Exception as e:
            print(f"❌ 로드 실패: {e}")

    def get_stats(self):
        """통계"""
        return {
            'version': self.VERSION,
            'base_count': len(self.BASE_ABBREVIATIONS),
            'dynamic_count': len(self.DYNAMIC_ABBREVIATIONS),
            'total_count': len(self.BASE_ABBREVIATIONS) + len(self.DYNAMIC_ABBREVIATIONS)
        }


# 전역 인스턴스 (모든 곳에서 사용)
trading_protocol = TradingProtocol()