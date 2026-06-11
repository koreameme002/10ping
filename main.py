import os
import requests
import logging
import re
import argparse
from datetime import datetime, timedelta, timezone

def _now_kst():
    """GitHub Actions(UTC 환경) 및 로컬 모두에서 KST 시간을 정확히 반환"""
    return datetime.now(timezone.utc) + timedelta(hours=9)
from dotenv import load_dotenv

# 모듈 로드
from keyword_analyzer import KeywordAnalyzer
from tenping_partner import TenpingPartnerAPI
from content_writer import ContentWriter
from telegram_notifier import TelegramNotifier

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class AutoPublisherController:
    """전체 자동화 수익 블로그 발행 단계를 총괄하는 컨트롤러"""

    def __init__(self):
        self.analyzer = KeywordAnalyzer()
        self.tenping = TenpingPartnerAPI()
        self.writer = ContentWriter()
        self.notifier = TelegramNotifier()
        self.image_dir = "assets/images/posts"
        self.post_dir = "_posts"

    def _get_jekyll_baseurl(self) -> str:
        """_config.yml에서 baseurl 설정을 파싱하여 반환"""
        baseurl = ""
        try:
            config_path = "_config.yml"
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("baseurl:"):
                            parts = line.split(":", 1)
                            if len(parts) > 1:
                                val = parts[1].strip().strip('"').strip("'")
                                if val and val != "/":
                                    baseurl = val
                                    break
                logging.info(f"Jekyll baseurl 감지됨: {baseurl}")
        except Exception as e:
            logging.error(f"Jekyll baseurl 읽기 중 오류 발생: {e}")
        return baseurl

    def _ensure_directories(self):
        """이미지 및 포스팅 폴더 생성 보장"""
        if not os.path.exists(self.image_dir):
            os.makedirs(self.image_dir)
            logging.info(f"이미지 디렉터리 생성: {self.image_dir}")
        if not os.path.exists(self.post_dir):
            os.makedirs(self.post_dir)
            logging.info(f"포스팅 디렉터리 생성: {self.post_dir}")

    def _download_product_images(self, keyword: str, products: list) -> list:
        """[방안 B] 상품 썸네일 이미지를 다운로드하여 로컬 assets 폴더에 저장하고 상대 경로로 업데이트"""
        self._ensure_directories()
        date_str = _now_kst().strftime("%Y-%m-%d")
        
        # 파일명 정제 (한글/영어/숫자 외 제거)
        safe_keyword = re.sub(r'[^a-zA-Z0-9가-힣_-]', '_', keyword)
        baseurl = self._get_jekyll_baseurl()

        updated_products = []
        for idx, prod in enumerate(products, 1):
            original_img_url = prod.get("productImage")
            # 기본 쿠팡 이미지 또는 dummy 이미지일 경우 통과
            if not original_img_url or "dummy.com" in original_img_url:
                updated_products.append(prod)
                continue

            # 파일명 규칙: YYYY-MM-DD-keyword-{index}.jpg
            img_filename = f"{date_str}-{safe_keyword}-{idx}.jpg"
            local_img_path = os.path.join(self.image_dir, img_filename)
            
            # 마크다운 본문에 삽입될 블로그 루트 기준의 경로 (baseurl 접두사 추가)
            blog_relative_path = f"{baseurl}/assets/images/posts/{img_filename}"

            try:
                logging.info(f"상품 이미지 다운로드 시도 ({idx}): {original_img_url}")
                # 쿠팡 이미지 서버의 차단을 피하기 위한 기본 헤더 설정
                headers = {"User-Agent": "Mozilla/5.0"}
                img_res = requests.get(original_img_url, headers=headers, timeout=10)
                
                if img_res.status_code == 200:
                     with open(local_img_path, "wb") as f:
                         f.write(img_res.content)
                     logging.info(f"이미지 로컬 저장 성공: {local_img_path}")
                     # 복사하여 이미지 경로 수정
                     updated_prod = prod.copy()
                     updated_prod["productImage"] = blog_relative_path
                     updated_products.append(updated_prod)
                else:
                     logging.warning(f"이미지 다운로드 실패 (HTTP {img_res.status_code}) - 원본 링크를 유지합니다.")
                     updated_products.append(prod)
            except Exception as e:
                logging.error(f"이미지 다운로드 예외 발생: {e} - 원본 링크를 유지합니다.")
                updated_products.append(prod)
        return updated_products

    def run_pipeline(self, category: str):
        """자동화 파이프라인의 전체 실행 컨트롤"""
        logging.info("=========================================")
        logging.info(f"자동화 포스팅 파이프라인 실행 시작: {category}")
        logging.info("=========================================")

        # 1단계: 오늘의 타겟 키워드/이슈 선정
        topic = self.analyzer.get_topic(category)
        target_keyword = topic["keyword"]
        logging.info(f"선정된 오늘의 주제: {topic}")

        if category == "health":
            # 2단계: 텐핑 API 광고/상품 수집
            products = self.tenping.search_products(target_keyword, limit=3)
            if not products:
                logging.error("추천할 상품 리스트를 수집하지 못했습니다. 파이프라인을 종료합니다.")
                return

            # 3단계: 이미지 로컬 다운로드 가동 [방안 B]
            processed_products = self._download_product_images(target_keyword, products)

            # 4단계: AI 콘텐츠 초안 생성 (OpenAI API 또는 Fallback)
            raw_content = self.writer.generate_blog_post(category, topic, processed_products)
        else:
            # AI 뉴스 및 최신 이슈 카테고리는 슬라이드 배너에 들어갈 실시간 광고 수집 (키워드 매칭 없이 상위 광고)
            products = self.tenping.search_products("", limit=5)
            # 이미지 다운로드는 하지 않고 텐핑 서버 이미지를 그대로 배너에 사용하므로 바로 전달
            raw_content = self.writer.generate_blog_post(category, topic, products)

        # 5단계: Jekyll/Hugo 포스팅 마크다운 파일로 영구 기록
        saved_file, slug = self.writer.write_to_markdown_file(category, target_keyword, raw_content)

        logging.info("=========================================")
        logging.info(f"파이프라인 성공 완료. 생성된 포스트: {saved_file}")
        logging.info("=========================================")

        # 6단계: 텔레그램 발행 완료 알림 전송
        if saved_file and slug:
            post_url = f"https://koreameme002.github.io/10ping/posts/{slug}/"
            
            msg = (
                f"🎉 <b>[10ping] 신규 콘텐츠 발행 완료!</b>\n\n"
                f"수집된 데이터와 AI 분석을 기반으로 고품질의 포스팅이 블로그에 자동 배포되었습니다.\n\n"
                f"📌 <b>포스팅 정보</b>\n"
                f"• <b>타겟 키워드</b>: {target_keyword}\n"
                f"• <b>카테고리</b>: {category}\n"
                f"• <b>발행 일시</b>: {_now_kst().strftime('%Y-%m-%d %H:%M:%S')} (KST)\n\n"
                f"🔗 <b>생성된 블로그 포스트 보기</b>\n"
                f"<a href=\"{post_url}\">{post_url}</a>\n\n"
                f"✅ GitHub Actions 저장소 동기화가 진행 중이며, 잠시 후 위 링크에서 확인하실 수 있습니다."
            )
            self.notifier.send_message(msg)

def determine_category_by_time() -> str:
    from datetime import datetime, timedelta, timezone
    # GitHub Actions 등 UTC 환경을 고려하여 KST 구하기
    kst = datetime.now(timezone.utc) + timedelta(hours=9)
    hour = kst.hour
    
    logging.info(f"현재 KST 시각: {kst.strftime('%Y-%m-%d %H:%M:%S')} (시간대: {hour}시)")

    # 1. 아침 시간대 (05:00 ~ 11:59): 건강 (아침방송 연동 및 종합)
    if 5 <= hour < 12:
        return "health"
    # 2. 점심 시간대 (12:00): AI 뉴스
    elif hour == 12:
        return "ai_news"
    # 3. 오후 1시 (13:00): 최신 이슈
    elif hour == 13:
        return "latest_issue"
    # 4. 오후 2~3시 (14:00~15:59): AI 뉴스 (14:30 스케줄 대응)
    elif hour in [14, 15]:
        return "ai_news"
    # 5. 오후 4시 (16:00): 최신 이슈
    elif hour == 16:
        return "latest_issue"
    # 6. 오후 5시 (17:00~17:59): AI 뉴스 (17:30 스케줄 대응)
    elif hour == 17:
        return "ai_news"
    # 7. 오후 6시 (18:00~18:59): 최신 이슈 (18:30 스케줄 대응)
    elif hour == 18:
        return "latest_issue"
    # 8. 오후 7시 (19:00~19:59): AI 뉴스 (19:30 스케줄 대응)
    elif hour == 19:
        return "ai_news"
    # 9. 오후 8시 (20:00): 최신 이슈
    elif hour == 20:
        return "latest_issue"
    # 10. 오후 9시 (21:00): 건강
    elif hour == 21:
        return "health"
    # 11. 야간 (22:00 ~ 04:59): 최신 이슈 또는 건강
    else:
        return "latest_issue"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto Revenue Blog Publisher Pipeline")
    parser.add_argument(
        "--category",
        type=str,
        default="auto",
        choices=["auto", "health", "ai_news", "latest_issue"],
        help="Category of the post to generate (default: auto)"
    )
    args = parser.parse_args()

    category = args.category
    if category == "auto":
        category = determine_category_by_time()

    controller = AutoPublisherController()
    controller.run_pipeline(category)
