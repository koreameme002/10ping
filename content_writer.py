"""
content_writer.py
카테고리별로 최적화된 마크다운 포스팅을 자동 생성한다.
- health       : 텐핑 제휴 캠페인 섹션 포함
- ai_news      : HTML 자동 슬라이드 배너 삽입 (텐핑 링크 3개 회전)
- latest_issue : HTML 자동 슬라이드 배너 삽입
"""

import os
import re
import hashlib
import logging
from datetime import datetime, timedelta, timezone

def _now_kst():
    """GitHub Actions(UTC 환경) 및 로컬 모두에서 KST 시간을 정확히 반환"""
    return datetime.now(timezone.utc) + timedelta(hours=9)

def _make_description(body: str, max_len: int = 155) -> str:
    """본문에서 SEO용 meta description 자동 추출 (이모지·마크다운 제거)"""
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', body)
    # 마크다운 이미지/링크 제거
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\(.*?\)', r'\1', text)
    # 마크다운 기호 제거
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'[*_`~>#\-]', '', text)
    # 이모지 제거 (유니코드 대역 기반)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    # 불필요한 공백/개행 정리
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return ""

    # 문장 구분을 위해 온점으로 쪼개어 첫 번째 의미 있는 문장을 찾는다.
    for part in text.split('.'):
        part = part.strip()
        if len(part) > 20:
            desc = (part[:max_len] + '...') if len(part) > max_len else part + '.'
            return desc.replace('"', "'")

    # 의미 있는 긴 문장이 없으면 그냥 잘라서 반환
    desc = (text[:max_len] + '...') if len(text) > max_len else text
    return desc.replace('"', "'")

from dotenv import load_dotenv
from openai import OpenAI
from google import genai

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ─── 슬라이드 배너에 들어갈 Tenping 제휴 링크 (AI·이슈 포스팅용 고정 및 대체용) ───
SLIDE_BANNER_LINKS = [
    {"label": "✨ 화제의 재테크 및 무료 자산설계 신청하기",  "url": "http://yimay.kr/t8f3hngxlq"},
    {"label": "📚 내 영어 실력 무료 진단 및 수강 혜택",        "url": "http://yimay.kr/t8gpwr4gfl"},
    {"label": "🎁 [이벤트] 선착순 사은품 증정 혜택 참여하기", "url": "http://yimay.kr/t8gpwr30z3"},
]

SLIDE_BANNER_HTML = """
<style>
.cp-banner-wrap{{position:relative;overflow:hidden;border-radius:12px;
  background:linear-gradient(135deg,#20b2aa,#008080);padding:4px;margin:2em 0;}}
.cp-banner{{display:flex;transition:transform .5s ease;}}
.cp-banner-item{{min-width:100%;box-sizing:border-box;
  background:#fff;border-radius:10px;padding:20px 24px;text-align:center;}}
.cp-banner-item a{{display:block;font-weight:700;font-size:1.05rem;
  color:#008080;text-decoration:none;letter-spacing:-.3px;}}
.cp-banner-item a:hover{{text-decoration:underline;}}
.cp-banner-dots{{text-align:center;margin-top:6px;}}
.cp-banner-dots span{{display:inline-block;width:8px;height:8px;margin:0 3px;
  border-radius:50%;background:#ccc;cursor:pointer;}}
.cp-banner-dots span.active{{background:#008080;}}
.cp-notice{{font-size:.72rem;color:#999;text-align:center;margin-top:4px;}}
</style>
<div class="cp-banner-wrap">
  <div class="cp-banner" id="cpBanner">
    {slides}
  </div>
</div>
<div class="cp-banner-dots" id="cpDots">{dots}</div>
<p class="cp-notice">※ 이 배너는 텐핑 제휴 마케팅 링크를 포함하며, 참여 시 일정액의 수수료를 제공받을 수 있습니다.</p>
<script>
(function(){{
  var items=document.querySelectorAll('#cpBanner .cp-banner-item');
  var dots=document.querySelectorAll('#cpDots span');
  var idx=0;
  function go(n){{
    idx=(n+items.length)%items.length;
    document.getElementById('cpBanner').style.transform='translateX(-'+idx*100+'%)';
    dots.forEach(function(d,i){{d.className=i===idx?'active':'';}}); 
  }}
  dots.forEach(function(d,i){{d.addEventListener('click',function(){{go(i);}});}});
  setInterval(function(){{go(idx+1);}},3500);
}})();
</script>
"""


def _build_slide_banner(campaigns: list = None) -> str:
    """텐핑 캠페인 목록이 주어지면 해당 링크로, 없으면 기본 SLIDE_BANNER_LINKS로 배너 생성"""
    links = []
    if campaigns:
        for c in campaigns[:5]:  # 최대 5개
            links.append({"label": f"🔥 {c['productName']}", "url": c['productUrl']})

    if not links:
        links = SLIDE_BANNER_LINKS

    slides = "\n".join(
        f'<div class="cp-banner-item"><a href="{item["url"]}" target="_blank" rel="noopener">{item["label"]}</a></div>'
        for item in links
    )
    dots = "\n".join(
        f'<span class="{"active" if i == 0 else ""}"></span>'
        for i in range(len(links))
    )
    return SLIDE_BANNER_HTML.format(slides=slides, dots=dots)


def _parse_ai_response(response_text: str, keyword: str) -> dict:
    """AI 응답 텍스트에서 [TITLE], [SLUG], [BODY]를 파싱하여 반환한다."""
    title = keyword
    slug = ""
    body = response_text

    # 대소문자 구분 없이 매칭하고 앞뒤 공백 제거
    title_match = re.search(r'\[TITLE\]\s*(.*?)\s*(?=\[SLUG\]|\[BODY\]|$)', response_text, re.IGNORECASE | re.DOTALL)
    slug_match = re.search(r'\[SLUG\]\s*(.*?)\s*(?=\[TITLE\]|\[BODY\]|$)', response_text, re.IGNORECASE | re.DOTALL)
    body_match = re.search(r'\[BODY\]\s*(.*?)\s*(?=\[TITLE\]|\[SLUG\]|$)', response_text, re.IGNORECASE | re.DOTALL)

    if title_match:
        title = title_match.group(1).strip().replace('"', '\\"')
    if slug_match:
        raw_slug = slug_match.group(1).strip().lower()
        slug = re.sub(r'[^a-z0-9-]', '-', raw_slug)
        slug = re.sub(r'-+', '-', slug).strip('-')
    if body_match:
        body = body_match.group(1).strip()

    if not slug:
        h = hashlib.md5(response_text.encode('utf-8')).hexdigest()[:6]
        slug = f"post-{h}"

    # 제목이 마크다운 헤더로 시작하면 # 제거
    if title.startswith("# "):
        title = title[2:].strip().replace('"', '\\"')

    # 구분자가 전혀 없을 때의 폴백: 첫 번째 라인을 제목으로 파싱하고 본문에서 제거
    if not title_match and body.startswith("# "):
        lines = body.split("\n")
        first_line = lines[0]
        title = first_line[2:].strip().replace('"', '\\"')
        body = "\n".join(lines[1:]).strip()

    return {"title": title, "slug": slug, "body": body}


FORMAT_INSTRUCTION = """
반드시 아래와 같은 포맷으로만 출력하세요. 다른 인사말이나 설명은 일절 생략하세요:

[TITLE]
(여기에 후킹성이 강한 매력적인 국문 제목을 작성)
[SLUG]
(여기에 제목이나 키워드에 어울리는 3~5단어 내외의 영문 소문자 및 하이픈(-) 조합의 URL 슬러그를 작성. 예: goat-milk-protein)
[BODY]
(여기에 마크다운 형식의 블로그 본문을 작성. 마크다운 첫 줄에 제목(#)은 넣지 마세요.)
"""


class ContentWriter:

    def __init__(self):
        # OpenAI 세팅
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key) if api_key and api_key != "your_openai_api_key_here" else None

        # Gemini 세팅
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_client = None
        self.gemini_enabled = False
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            try:
                self.gemini_client = genai.Client(api_key=gemini_key)
                self.gemini_enabled = True
                logging.info("Google Gemini API 초기화 성공")
            except Exception as e:
                logging.error(f"Google Gemini API 초기화 실패: {e}")

    # ────────────────────────────────────────────────
    # 공개 메서드
    # ────────────────────────────────────────────────
    def generate_blog_post(self, category: str, topic: dict, products: list = None) -> str:
        """카테고리에 따라 적합한 포스팅 본문(마크다운)을 생성한다."""
        if category == "health":
            return self._generate_health_post(topic["keyword"], products or [])
        elif category == "ai_news":
            return self._generate_ai_news_post(topic, products)
        elif category == "latest_issue":
            return self._generate_latest_issue_post(topic, products)
        else:
            raise ValueError(f"지원하지 않는 카테고리: {category}")

    def write_to_markdown_file(self, category: str, keyword: str, content: str) -> tuple:
        """Jekyll Front Matter를 부착해 _posts 폴더에 파일 저장."""
        output_dir = "_posts"
        os.makedirs(output_dir, exist_ok=True)

        now = _now_kst()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%Y-%m-%d %H:%M:%S +0900")

        parsed = _parse_ai_response(content, keyword)
        title = parsed["title"]
        slug = parsed["slug"]
        body = parsed["body"]

        filename = f"{date_str}-{slug}.md"
        file_path = os.path.join(output_dir, filename)

        cat_map = {"health": "health", "ai_news": "ai-news", "latest_issue": "latest-issue"}
        tag_map = {
            "health": f"{keyword}, 텐핑, 제휴마케팅, 추천정보",
            "ai_news": "AI뉴스, 인공지능, 최신AI트렌드",
            "latest_issue": "이슈, 실시간트렌드, 핫뉴스",
        }

        # ─── 대표 이미지(썸네일) 파싱 및 기본 이미지 매핑 로직 ───
        img_match = re.search(r'!\[.*?\]\((.*?)\)', body)
        image_path = ""
        if img_match:
            raw_img_path = img_match.group(1).strip()
            # baseurl 제거 처리 (예: /10ping/assets/images/... -> assets/images/...)
            baseurl = "/10ping"
            if raw_img_path.startswith(f"{baseurl}/"):
                image_path = raw_img_path[len(baseurl)+1:]
            elif raw_img_path.startswith("/"):
                image_path = raw_img_path[1:]
            else:
                image_path = raw_img_path
        else:
            # 본문에 이미지가 없을 때 (ai_news, latest_issue 등)
            # title 해시값 기반으로 assets/images/1.jpg ~ 17.jpg 중 하나 지정
            h_val = int(hashlib.md5(title.encode('utf-8')).hexdigest(), 16)
            img_idx = (h_val % 17) + 1
            image_path = f"assets/images/{img_idx}.jpg"

        description = _make_description(body)
        front_matter = (
            f"---\n"
            f"layout: post\n"
            f"title: \"{title}\"\n"
            f"date: {time_str}\n"
            f"permalink: /posts/{slug}/\n"
            f"image: {image_path}\n"
            f"author: admin\n"
            f"description: \"{description}\"\n"
            f"categories: {cat_map.get(category, 'general')}\n"
            f"tags: [{tag_map.get(category, keyword)}]\n"
            f"---\n\n"
        )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(front_matter + body)

        logging.info(f"포스팅 저장 완료: {file_path} (대표 이미지: {image_path})")
        return file_path, slug

    # ────────────────────────────────────────────────
    # 텐핑 제휴 포스팅 (캠페인 정보 포함)
    # ────────────────────────────────────────────────
    def _generate_health_post(self, keyword: str, products: list) -> str:
        if self.client:
            return self._gpt_health_post(keyword, products)
        elif self.gemini_enabled:
            return self._gemini_health_post(keyword, products)
        return self._fallback_health_post(keyword, products)

    def _gemini_health_post(self, keyword: str, products: list) -> str:
        product_info = "\n".join(
            f"{i+1}. {p['productName']} | 혜택/포인트:{p['productPrice']} "
            f"| 이미지:{p['productImage']} | 링크:{p['productUrl']}\n   상세안내: {p.get('productMemo','')}"
            for i, p in enumerate(products)
        )
        system = (
            "대한민국 최고 바이럴 마케터·SEO 카피라이터. "
            "사용자의 참여와 가입을 유도하는 후킹성 강한 제목과 스토리텔링 본문으로 구성된 마크다운 포스팅을 작성한다."
        )
        user = f"""
키워드: {keyword}
텐핑 제휴 캠페인 목록:
{product_info}

규칙:
1. 제목(#): 독자의 이목과 호기심을 유도하는 후킹성 강한 문구 작성. 예 → "난리난 그 정보! {keyword} 혜택 및 신청 방법 요약"
2. 서론: 해당 주제(키워드)의 최근 이슈 언급 + 독자들의 공감대나 필요성 강조
3. 상품별: 각 제휴 서비스/상품의 혜택 및 장점을 친절하고 신뢰성 높게 정보 전달형 스토리텔링으로 소개
         각 제휴 캠페인 하단: ![서비스명](이미지) 및 <a href="링크" target="_blank" rel="noopener noreferrer">▶ 상세 혜택 확인 및 신청하기</a>
4. 결론: 나에게 어울리는 서비스 추천 및 즉각 참여 유도
5. 맨 마지막: 텐핑 소속 마케터 제휴 수수료 안내 문구
{FORMAT_INSTRUCTION}
"""
        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system
                )
            )
            return response.text.strip()
        except Exception as e:
            logging.error(f"Gemini API 호출 실패(health): {e}")
            return self._fallback_health_post(keyword, products)

    def _gpt_health_post(self, keyword: str, products: list) -> str:
        product_info = "\n".join(
            f"{i+1}. {p['productName']} | 혜택/포인트:{p['productPrice']} "
            f"| 이미지:{p['productImage']} | 링크:{p['productUrl']}\n   상세안내: {p.get('productMemo','')}"
            for i, p in enumerate(products)
        )
        system = (
            "대한민국 최고 바이럴 마케터·SEO 카피라이터. "
            "사용자의 참여와 가입을 유도하는 후킹성 강한 제목과 스토리텔링 본문으로 구성된 마크다운 포스팅을 작성한다."
        )
        user = f"""
키워드: {keyword}
텐핑 제휴 캠페인 목록:
{product_info}

규칙:
1. 제목(#): 독자의 이목과 호기심을 유도하는 후킹성 강한 문구 작성. 예 → "난리난 그 정보! {keyword} 혜택 및 신청 방법 요약"
2. 서론: 해당 주제(키워드)의 최근 이슈 언급 + 독자들의 공감대나 필요성 강조
3. 상품별: 각 제휴 서비스/상품의 혜택 및 장점을 친절하고 신뢰성 높게 정보 전달형 스토리텔링으로 소개
         각 제휴 캠페인 하단: ![서비스명](이미지) 및 <a href="링크" target="_blank" rel="noopener noreferrer">▶ 상세 혜택 확인 및 신청하기</a>
4. 결론: 나에게 어울리는 서비스 추천 및 즉각 참여 유도
5. 맨 마지막: 텐핑 소속 마케터 제휴 수수료 안내 문구
{FORMAT_INSTRUCTION}
"""
        try:
            res = self.client.chat.completions.create(
                model="gpt-4o", temperature=0.8, max_tokens=2500,
                messages=[{"role":"system","content":system},{"role":"user","content":user}]
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"OpenAI 호출 실패: {e}")
            return self._fallback_health_post(keyword, products)

    def _fallback_health_post(self, keyword: str, products: list) -> str:
        labels = ["주목할 만한 제휴 혜택 🥇", "인기 급상승 추천 서비스 🏆", "강력 추천 유용한 정보 🎁"]
        prods_md = ""
        for i, p in enumerate(products):
            label = labels[i] if i < len(labels) else "추천 아이템"
            memo_summary = p.get("productMemo", "많은 사람들이 참여하고 만족한 실시간 인기 캠페인입니다.")
            memo_summary = memo_summary.replace('\r\n', ' ').replace('\n', ' ')[:200]
            prods_md += f"""
### ⭐ {i+1}위: {p['productName']} ({label})
* **상세 안내**: {memo_summary}
* **주요 혜택**: 쉽고 빠르게 참여하여 즉시 특별 혜택을 받으실 수 있는 신뢰성 높은 제휴 서비스입니다.

![{p['productName']}]({p['productImage']})

<a href="{p['productUrl']}" target="_blank" rel="noopener noreferrer">▶ 상세 혜택 및 무료 신청 바로가기</a>

---
"""
        title = f"\"놓치면 나만 손해?\" 최근 화제인 {keyword} 상세 혜택 및 신청 방법 완전 정리 TOP 3"

        h = hashlib.md5(keyword.encode('utf-8')).hexdigest()[:6]
        slug = f"tenping-{h}-top3"

        body = f"""
최근 인터넷과 소셜 미디어 상에서 가장 뜨거운 관심을 받고 있는 정보가 있습니다. 바로 **{keyword}** 관련 혜택 소식인데요.
많은 정보가 쏟아지고 있지만, 그중에서 실속 있고 유용한 정보만 골라내는 것은 쉽지 않습니다.

독자 여러분을 위해 텐핑 실시간 인기 캠페인을 분석하여 가장 평판이 좋고 참여율이 높은 대표 서비스 3가지를 정리해 드립니다.

---

## 🔍 실패 없는 정보 선별 3가지 핵심 팁
1. **신뢰할 수 있는 플랫폼**: 공식 검증 절차를 거친 믿을 수 있는 제휴 서비스인지 확인
2. **무료 혜택 유무**: 가입 또는 자격 충족 시 즉각적인 혜택이 주어지는지 체크
3. **사용자 평판**: 실제 참여자들의 긍정적인 피드백이 많은지 비교

---

## 🏆 놓치면 아쉬운 {keyword} 실시간 인기 제휴 정보
{prods_md}

## 💡 에디터의 최종 한 줄 추천
* 쉽고 빠른 신청 선호 → **1위** 추천
* 더 넓고 깊은 전문 상담 선호 → **2위** 추천

"유용한 정보와 기회는 기다려주지 않습니다. 지금 바로 특별한 혜택을 만나보세요!"

<br>

---
*이 포스팅은 텐핑 소속 마케터 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받을 수 있습니다.*
""".strip()
        return f"[TITLE]\n{title}\n[SLUG]\n{slug}\n[BODY]\n{body}"

    # ────────────────────────────────────────────────
    # AI 뉴스 포스팅 (슬라이드 배너)
    # ────────────────────────────────────────────────
    def _generate_ai_news_post(self, topic: dict, products: list = None) -> str:
        title = topic.get("title", "오늘의 AI 뉴스")
        summary = topic.get("summary", "")
        source_link = topic.get("link", "")
        banner = _build_slide_banner(products)

        if self.client:
            system = (
                "AI·기술 전문 블로거. SEO 최적화된 후킹성 제목과 읽기 쉬운 "
                "뉴스 해설 본문(마크다운)을 작성한다."
            )
            user = f"""
뉴스 제목: {title}
요약: {summary}
원문 링크: {source_link}

규칙:
1. 제목(#): 클릭 유도 강한 후킹 문구로 변환 (예 → "전 세계가 주목! ...")
2. 서론: 뉴스 핵심을 2~3문장으로 임팩트 있게 요약
3. 본문: 배경·의미·독자에게 미치는 영향을 3개 소제목으로 상세 설명
4. 결론: 앞으로 주목해야 할 포인트 + 독자 행동 유도
5. 마크다운 본문만 출력 (슬라이드 배너 HTML은 직접 삽입할 것이므로 제외)
{FORMAT_INSTRUCTION}
"""
            try:
                res = self.client.chat.completions.create(
                    model="gpt-4o", temperature=0.75, max_tokens=2000,
                    messages=[{"role":"system","content":system},{"role":"user","content":user}]
                )
                body_raw = res.choices[0].message.content.strip()
            except Exception as e:
                logging.error(f"OpenAI 호출 실패(ai_news): {e}")
                body_raw = self._fallback_ai_news_body(title, summary)
        elif self.gemini_enabled:
            body_raw = self._gemini_ai_news_body(title, summary, source_link)
        else:
            body_raw = self._fallback_ai_news_body(title, summary)

        parsed = _parse_ai_response(body_raw, title)
        banner_body = parsed["body"] + f"\n\n---\n\n## 🛒 오늘의 제휴 이벤트 배너\n\n{banner}"

        return f"[TITLE]\n{parsed['title']}\n[SLUG]\n{parsed['slug']}\n[BODY]\n{banner_body}"

    def _gemini_ai_news_body(self, title: str, summary: str, source_link: str) -> str:
        system = (
            "AI·기술 전문 블로거. SEO 최적화된 후킹성 제목과 읽기 쉬운 "
            "뉴스 해설 본문(마크다운)을 작성한다."
        )
        user = f"""
뉴스 제목: {title}
요약: {summary}
원문 링크: {source_link}

규칙:
1. 제목(#): 클릭 유도 강한 후킹 문구로 변환 (예 → "전 세계가 주목! ...")
2. 서론: 뉴스 핵심을 2~3문장으로 임팩트 있게 요약
3. 본문: 배경·의미·독자에게 미치는 영향을 3개 소제목으로 상세 설명
4. 결론: 앞으로 주목해야 할 포인트 + 독자 행동 유도
{FORMAT_INSTRUCTION}
"""
        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system
                )
            )
            return response.text.strip()
        except Exception as e:
            logging.error(f"Gemini API 호출 실패(ai_news): {e}")
            return self._fallback_ai_news_body(title, summary)

    def _fallback_ai_news_body(self, title: str, summary: str) -> str:
        h = hashlib.md5(title.encode('utf-8')).hexdigest()[:6]
        slug = f"ai-news-{h}"
        body = f"""
지금 AI·IT 업계에서 가장 뜨거운 이슈가 터졌습니다.
{summary or "인공지능 기술이 또 한 번 패러다임을 바꾸는 소식이 들려오고 있습니다."}

---

## 📌 핵심 내용 요약

AI 기술의 발전 속도가 점점 빨라지면서 일상과 산업 전반에 걸친 변화가 가속화되고 있습니다.
이번 뉴스는 그중에서도 특히 **실생활 적용 가능성**이 높은 내용으로, 전문가들 사이에서 큰 반향을 일으키고 있습니다.

## 🔍 이 뉴스가 중요한 이유

1. **산업 변화**: 기존 업무 방식과 비즈니스 모델에 직접적인 영향을 미칩니다.
2. **일상 적용**: 일반 소비자도 곧 체감할 수 있는 실질적인 변화가 예상됩니다.
3. **글로벌 경쟁**: 국내외 기업들이 발 빠르게 대응 전략을 수립 중입니다.

## 💡 앞으로 주목해야 할 포인트

AI 트렌드는 단순한 기술 이슈를 넘어 **투자·취업·교육** 전반에 영향을 미칩니다.
지금 이 흐름을 놓치지 않도록, 최신 AI 뉴스를 매일 팔로우하세요!
""".strip()
        return f"[TITLE]\n🤖 전 세계가 주목! {title}\n[SLUG]\n{slug}\n[BODY]\n{body}"

    # ────────────────────────────────────────────────
    # 최신 이슈 포스팅 (슬라이드 배너)
    # ────────────────────────────────────────────────
    def _generate_latest_issue_post(self, topic: dict, products: list = None) -> str:
        title = topic.get("title", "오늘의 핫이슈")
        summary = topic.get("summary", "")
        banner = _build_slide_banner(products)

        if self.client:
            system = "바이럴 콘텐츠 전문가. 후킹성 강한 제목과 몰입감 있는 이슈 해설 마크다운을 작성한다."
            user = f"""
이슈 키워드: {title}
검색 동향: {summary}

규칙:
1. 제목(#): 호기심 폭발 후킹 문구 (예 → "왜 갑자기 모두가 '{title}'을 검색하나?")
2. 서론: 이슈의 배경과 사람들이 관심 갖는 이유를 생생하게 소개
3. 본문: 이슈의 전말·다양한 시각·향후 전망을 3개 소제목으로 상세 서술
4. 결론: 핵심 정리 + 독자에게 액션 촉구
{FORMAT_INSTRUCTION}
"""
            try:
                res = self.client.chat.completions.create(
                    model="gpt-4o", temperature=0.8, max_tokens=2000,
                    messages=[{"role":"system","content":system},{"role":"user","content":user}]
                )
                body_raw = res.choices[0].message.content.strip()
            except Exception as e:
                logging.error(f"OpenAI 호출 실패(latest_issue): {e}")
                body_raw = self._fallback_issue_body(title, summary)
        elif self.gemini_enabled:
            body_raw = self._gemini_issue_body(title, summary)
        else:
            body_raw = self._fallback_issue_body(title, summary)

        parsed = _parse_ai_response(body_raw, title)
        banner_body = parsed["body"] + f"\n\n---\n\n## 🛒 오늘의 제휴 이벤트 배너\n\n{banner}"

        return f"[TITLE]\n{parsed['title']}\n[SLUG]\n{parsed['slug']}\n[BODY]\n{banner_body}"

    def _gemini_issue_body(self, title: str, summary: str) -> str:
        system = "바이럴 콘텐츠 전문가. 후킹성 강한 제목과 몰입감 있는 이슈 해설 마크다운을 작성한다."
        user = f"""
이슈 키워드: {title}
검색 동향: {summary}

규칙:
1. 제목(#): 호기심 폭발 후킹 문구 (예 → "왜 갑자기 모두가 '{title}'을 검색하나?")
2. 서론: 이슈의 배경과 사람들이 관심 갖는 이유를 생생하게 소개
3. 본문: 이슈의 전말·다양한 시각·향후 전망을 3개 소제목으로 상세 서술
4. 결론: 핵심 정리 + 독자에게 액션 촉구
{FORMAT_INSTRUCTION}
"""
        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system
                )
            )
            return response.text.strip()
        except Exception as e:
            logging.error(f"Gemini API 호출 실패(latest_issue): {e}")
            return self._fallback_issue_body(title, summary)

    def _fallback_issue_body(self, title: str, summary: str) -> str:
        h = hashlib.md5(title.encode('utf-8')).hexdigest()[:6]
        slug = f"issue-{h}"
        body = f"""
{summary or "지금 대한민국에서 가장 뜨거운 키워드가 등장했습니다!"}
이슈 하나가 오늘 하루 온라인을 가득 채웠고, 수십만 명이 동시에 검색창에 이 단어를 입력했습니다.

---

## 📌 이슈의 핵심, 30초 만에 파악하기

**{title}** — 이 키워드가 갑자기 급상승한 데에는 분명한 이유가 있습니다.
단순한 해프닝을 넘어 많은 사람들의 공감을 이끌어낸 사회적 맥락이 담겨 있습니다.

## 🔍 다양한 시각으로 본 이번 이슈

1. **화제의 중심**: 이슈의 발단과 전개 과정을 시간순으로 정리했습니다.
2. **여론의 반응**: 각계각층의 다양한 반응과 의견이 엇갈리고 있습니다.
3. **앞으로의 전망**: 이 이슈가 어디까지 이어질지, 전문가 시각을 담았습니다.

## 💬 당신의 생각은?

매일 새로운 이슈가 터지는 세상, 중요한 건 빠른 판단입니다.
오늘 이슈도 북마크해 두고 흐름을 놓치지 마세요!
""".strip()
        return f"[TITLE]\n🔥 왜 갑자기 모두가 '{title}'을 검색하나? 지금 바로 확인하세요\n[SLUG]\n{slug}\n[BODY]\n{body}"


if __name__ == "__main__":
    writer = ContentWriter()
    from tenping_partner import TenpingPartnerAPI
    partner = TenpingPartnerAPI()
    mock_products = partner.search_products("건강", 2)

    for cat, topic in [
        ("health",       {"keyword": "건강보험", "title": "건강보험", "summary": ""}),
        ("ai_news",      {"keyword": "ChatGPT", "title": "ChatGPT-5 출시 임박", "summary": "OpenAI가 차세대 모델 발표를 준비 중", "link": ""}),
        ("latest_issue", {"keyword": "트렌드", "title": "최근 화제의 이슈", "summary": "급상승 검색어 1위"}),
    ]:
        print(f"\n{'='*60}")
        content = writer.generate_blog_post(cat, topic, mock_products if cat == "health" else None)
        saved_file, slug = writer.write_to_markdown_file(cat, topic["keyword"], content)
        print(f"[{cat}] 저장: {saved_file} (슬러그: {slug})")
