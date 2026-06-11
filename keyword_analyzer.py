"""
keyword_analyzer.py
카테고리(health / ai_news / latest_issue)에 따라 키워드를 수집하는 분석기.
- health    : KBS·MBC 아침 건강 방송 크롤링 + 내장 사전 Fallback
- ai_news   : Google 뉴스 RSS에서 AI·인공지능 최신 헤드라인 수집
- latest_issue : Google 트렌드 RSS에서 실시간 급상승 이슈 수집
"""

import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
import random
import logging
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class KeywordAnalyzer:

    # ── 건강 방송 단골 키워드 사전 (크롤링 차단 대비 Fallback) ──
    HEALTH_KEYWORDS = [
        "콘드로이친", "보스웰리아", "MSM", "상어연골", "초록입홍합",
        "유산균", "프로바이오틱스", "프리바이오틱스", "포스트바이오틱스",
        "콜라겐", "글루타치온", "히알루론산",
        "산양유단백질", "유청단백질", "초유단백질",
        "루테인", "아스타잔틴", "지아잔틴",
        "알티지오메가3", "크릴오일", "오메가3",
        "쏘팔메토", "옥타코사놀",
        "멀티비타민", "비타민D", "비타민C", "마그네슘", "밀크씨슬",
        "안마의자", "저주파마사지기", "족욕기", "혈압계",
    ]

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def _headers(self) -> dict:
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.5",
        }

    # ──────────────────────────────────────────
    # ① 건강 방송 크롤러
    # ──────────────────────────────────────────
    def _fetch_kbs_topics(self) -> list:
        url = "https://program.kbs.co.kr/1tv/culture/ask/pc/list.html"
        try:
            r = requests.get(url, headers=self._headers(), timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            return [t.get_text(strip=True) for t in soup.select(".title,.subject") if len(t.get_text(strip=True)) > 4]
        except Exception as e:
            logging.warning(f"KBS 수집 실패: {e}")
            return []

    def _fetch_mbc_topics(self) -> list:
        url = "https://program.imbc.com/Gibu"
        try:
            r = requests.get(url, headers=self._headers(), timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            return [t.get_text(strip=True) for t in soup.select(".title,.txt,.subject") if len(t.get_text(strip=True)) > 4]
        except Exception as e:
            logging.warning(f"MBC 수집 실패: {e}")
            return []

    def _extract_health_keyword(self, topics: list) -> str | None:
        for topic in topics:
            for kw in self.HEALTH_KEYWORDS:
                if kw in topic:
                    return kw
        return None

    def get_health_keyword(self) -> str:
        """아침 방송 → 건강 키워드 추출. 실패 시 사전에서 Fallback."""
        topics = self._fetch_kbs_topics() + self._fetch_mbc_topics()
        kw = self._extract_health_keyword(topics)
        if kw:
            logging.info(f"[건강] 방송 매칭 성공: {kw}")
            return kw
        kw = random.choice(self.HEALTH_KEYWORDS)
        logging.info(f"[건강] Fallback 키워드: {kw}")
        return kw

    # ──────────────────────────────────────────
    # ② AI 뉴스 크롤러
    # ──────────────────────────────────────────
    def get_ai_news_topic(self) -> dict:
        """
        Google 뉴스 RSS에서 AI·인공지능 최신 헤드라인을 가져온다.
        반환: {"title": str, "summary": str, "link": str}
        """
        feeds = [
            "https://news.google.com/rss/search?q=인공지능+AI&hl=ko&gl=KR&ceid=KR:ko",
            "https://news.google.com/rss/search?q=AI+chatgpt+gemini&hl=ko&gl=KR&ceid=KR:ko",
        ]
        items = []
        for url in feeds:
            try:
                r = requests.get(url, headers=self._headers(), timeout=10)
                root = ET.fromstring(r.content)
                for item in root.findall(".//item"):
                    title_el = item.find("title")
                    desc_el  = item.find("description")
                    link_el  = item.find("link")
                    if title_el is not None and title_el.text:
                        # 태그 제거
                        title = re.sub(r"<[^>]+>", "", title_el.text).strip()
                        desc  = re.sub(r"<[^>]+>", "", desc_el.text or "").strip() if desc_el is not None else ""
                        link  = link_el.text.strip() if link_el is not None else ""
                        items.append({"title": title, "summary": desc[:200], "link": link})
            except Exception as e:
                logging.warning(f"AI 뉴스 RSS 수집 실패 ({url}): {e}")

        if items:
            chosen = random.choice(items[:10])
            logging.info(f"[AI 뉴스] 선정: {chosen['title'][:40]}...")
            return chosen

        # Fallback
        fallback = {
            "title": "2026년 AI 인공지능 최신 동향 – 오늘 꼭 알아야 할 핵심 3가지",
            "summary": "세계 AI 기업들의 최신 모델 업데이트와 국내 도입 사례를 한눈에 정리했습니다.",
            "link": ""
        }
        logging.info("[AI 뉴스] Fallback 사용")
        return fallback

    # ──────────────────────────────────────────
    # ③ 최신 이슈 크롤러
    # ──────────────────────────────────────────
    def get_latest_issue_topic(self) -> dict:
        """
        Google 트렌드 RSS에서 실시간 급상승 이슈를 가져온다.
        반환: {"title": str, "summary": str}
        """
        url = "https://trends.google.com/trending/rss?geo=KR"
        try:
            r = requests.get(url, headers=self._headers(), timeout=10)
            root = ET.fromstring(r.content)
            items = []
            for item in root.findall(".//item"):
                title_el = item.find("title")
                desc_el  = item.find("{https://trends.google.com/trends/trendingsearches/daily}traffic")
                approx   = item.find("{https://trends.google.com/trends/trendingsearches/daily}approx_traffic")
                if title_el is not None and title_el.text:
                    items.append({
                        "title": title_el.text.strip(),
                        "summary": f"현재 검색량: {approx.text if approx is not None else '급상승 중'}",
                    })
            if items:
                chosen = random.choice(items[:15])
                logging.info(f"[최신 이슈] 선정: {chosen['title']}")
                return chosen
        except Exception as e:
            logging.warning(f"구글 트렌드 RSS 수집 실패: {e}")

        fallback = {
            "title": "오늘 가장 화제가 된 뉴스 이슈 정리",
            "summary": "지금 대한민국에서 가장 많이 검색된 실시간 이슈를 빠르게 확인하세요."
        }
        logging.info("[최신 이슈] Fallback 사용")
        return fallback

    # ──────────────────────────────────────────
    # ④ 통합 진입점
    # ──────────────────────────────────────────
    def get_topic(self, category: str) -> dict:
        """
        category: "health" | "ai_news" | "latest_issue"
        반환: {"keyword": str, "title": str, "summary": str, ...}
        """
        if category == "health":
            kw = self.get_health_keyword()
            return {"keyword": kw, "title": kw, "summary": ""}
        elif category == "ai_news":
            data = self.get_ai_news_topic()
            data["keyword"] = data["title"]
            return data
        elif category == "latest_issue":
            data = self.get_latest_issue_topic()
            data["keyword"] = data["title"]
            return data
        else:
            raise ValueError(f"지원하지 않는 카테고리: {category}")


if __name__ == "__main__":
    analyzer = KeywordAnalyzer()
    for cat in ["health", "ai_news", "latest_issue"]:
        print(f"\n[{cat}] →", analyzer.get_topic(cat))
