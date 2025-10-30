"""
뉴스 수집기 (감성 분석 제거)
단순히 뉴스만 수집해서 AI에게 전달
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import requests
from datetime import datetime, timedelta
from typing import List, Dict
from utils.logger import info, warning, error


class NewsCollector:
    """뉴스 수집기 (감성 분석 없음)"""

    def __init__(self):
        # News API
        self.news_api_key = os.getenv('NEWS_API_KEY', '')
        self.news_url = "https://newsapi.org/v2/everything"

        info("📰 뉴스 수집기 초기화")
        if self.news_api_key:
            info("  ✅ News API 연결됨")
        else:
            warning("  ⚠️ News API 키 없음")

    def fetch_crypto_news(self, hours=24, max_results=20):
        """
        암호화폐 뉴스 수집

        Args:
            hours: 최근 N시간 (기본 24시간)
            max_results: 최대 결과 수

        Returns:
            List[Dict]: 뉴스 리스트
        """
        if not self.news_api_key:
            warning("⚠️ News API 키 없음")
            return []

        try:
            # 시간 설정
            from_time = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

            # API 요청
            params = {
                'q': 'bitcoin OR cryptocurrency OR crypto',
                'from': from_time,
                'sortBy': 'publishedAt',
                'language': 'en',
                'pageSize': max_results,
                'apiKey': self.news_api_key
            }

            response = requests.get(self.news_url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])

                # 포맷팅
                news_list = []
                for article in articles:
                    news_list.append({
                        'title': article.get('title', ''),
                        'description': article.get('description', ''),
                        'source': article.get('source', {}).get('name', 'Unknown'),
                        'publishedAt': article.get('publishedAt', '')
                    })

                info(f"✅ 뉴스 {len(news_list)}개 수집 완료")
                return news_list

            else:
                warning(f"⚠️ News API 오류: {response.status_code}")
                return []

        except Exception as e:
            error(f"❌ 뉴스 수집 오류: {e}")
            return []

    def format_news_for_ai(self, news_list, max_count=10):
        """AI에게 전달할 형식으로 포맷팅"""
        if not news_list:
            return "최근 뉴스 없음"

        formatted = []
        for i, news in enumerate(news_list[:max_count], 1):
            formatted.append(f"{i}. {news['title']}")
            if news.get('description'):
                formatted.append(f"   {news['description'][:100]}...")

        return '\n'.join(formatted)


# 전역 인스턴스
news_collector = NewsCollector()

# 테스트
if __name__ == "__main__":
    print("🧪 News Collector 테스트\n")

    # 뉴스 수집
    news_list = news_collector.fetch_crypto_news(hours=24, max_results=10)

    print(f"\n📰 수집된 뉴스: {len(news_list)}개\n")

    if news_list:
        # AI용 포맷
        formatted = news_collector.format_news_for_ai(news_list, max_count=5)
        print("AI에게 전달할 형식:")
        print("=" * 60)
        print(formatted)
        print("=" * 60)

    print("\n✅ 테스트 완료!")