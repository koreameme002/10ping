import asyncio
import random
import os
import re
import config
from playwright.async_api import async_playwright

async def login_to_tenping(page):
    """
    제공된 계정 정보를 사용하여 텐핑에 로그인합니다.
    """
    try:
        print("[추출기] 텐핑 로그인 시도 중...")
        await page.goto("https://tenping.kr/Account/Login")
        await page.fill("#MemberID", config.TENPING_ID)
        await page.fill("#MemberPW", config.TENPING_PW)
        await page.click("button:has-text('로그인'), .btn_login")
        await page.wait_for_load_state("networkidle")
        
        # 주소 확인 (로그인 성공 시 메인으로 이동)
        if "Login" not in page.url:
            print("[추출기] 텐핑 로그인 성공!")
            # 세션 저장
            await page.context.storage_state(path=config.TENPING_SESSION_PATH)
            return True
        else:
            print("[추출기] 텐핑 로그인 실패 (정보 확인 필요)")
            return False
    except Exception as e:
        print(f"[추출기] 텐핑 로그인 오류: {e}")
        return False

async def get_campaign_list():
    """
    고단가 목록에서 상위 캠페인 리스트(제목, URL)를 가져옵니다.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        storage_path = config.TENPING_SESSION_PATH if os.path.exists(config.TENPING_SESSION_PATH) else None
        context = await browser.new_context(
            storage_state=storage_path,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            target_url = "https://tenping.kr/Home/List?Campaign_Category=0&CampaignType=578&FavoriteStatus=8702"
            print(f"[추출기] 캠페인 목록 불러오는 중: {target_url}")
            
            await page.goto(target_url, timeout=45000)
            await page.wait_for_selector("#campaign-list > li", timeout=15000)
            await asyncio.sleep(2) 
            
            # 확신 있는 셀렉터 사용
            items = page.locator("#campaign-list > li")
            count = await items.count()
            print(f"[추출기] '#campaign-list > li' 셀렉터로 {count}개 발견")
            
            if count == 0:
                # 백업 셀렉터들
                selectors = [".camp_list li", ".camp_list > ul > li", ".camp_item", ".list_area li"]
                for selector in selectors:
                    items = page.locator(selector)
                    count = await items.count()
                    if count > 0:
                        print(f"[추출기] '{selector}' 셀렉터로 {count}개 발견")
                        break
            
            if count == 0:
                print("[추출기] 목록 추출 실패.")
                return []

            campaigns = []
            seen_ids = set()
            
            for i in range(count):
                if len(campaigns) >= 10: break
                
                item = items.nth(i)
                # 링크 추출 (.btn-detailView가 확실함)
                link_el = item.locator(".btn-detailView").first
                href = await link_el.get_attribute("href")
                
                if not href:
                    link_el = item.locator("a[href*='CampaignID=']").first
                    href = await link_el.get_attribute("href")
                
                if href:
                    # CampaignID 추출
                    match = re.search(r'CampaignID=([^&]+)', href)
                    cid = match.group(1) if match else href
                    
                    if cid not in seen_ids:
                        seen_ids.add(cid)
                        
                        # 제목 추출
                        title = "제목 없음"
                        title_selectors = ["h3", ".tit", ".subject", "strong"]
                        for ts in title_selectors:
                            el = item.locator(ts).first
                            if await el.count() > 0:
                                title = await el.inner_text()
                                if title.strip(): break
                        
                        full_url = f"https://tenping.kr{href}" if href.startswith("/") else href
                        campaigns.append({"title": title.strip(), "url": full_url})
            
            return campaigns
        except Exception as e:
            print(f"[추출기] 목록 가져오기 오류: {e}")
            return []
        finally:
            await browser.close()

async def get_popular_campaign_url():
    """
    기존 호환성을 위해 리스트의 첫 번째를 반환합니다.
    """
    list = await get_campaign_list()
    return list[0]["url"] if list else None

async def extract_tenping_info(campaign_url=None):
    """
    텐핑 상세 정보(제목, 설명, 홍보 링크, 이미지, 유튜브, 도움말 등)를 추출합니다.
    """
    if not campaign_url:
        campaign_url = await get_popular_campaign_url()
        
    if not campaign_url:
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        storage_path = config.TENPING_SESSION_PATH if os.path.exists(config.TENPING_SESSION_PATH) else None
        context = await browser.new_context(
            storage_state=storage_path,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            print(f"[추출기] 상세 정보 추출 중: {campaign_url}")
            await page.goto(campaign_url, timeout=45000)
            await asyncio.sleep(3)
            
            # 1. 제목 추출
            title = "추천 제휴 캠페인"
            try:
                # 더 폭넓은 제목 셀렉터 시도
                title_selectors = [
                    ".camp_info .tit", "h2.tit", ".detail_header h2", 
                    "h2", ".subject", "title"
                ]
                for sel in title_selectors:
                    try:
                        title_text = await page.inner_text(sel, timeout=2000)
                        if title_text.strip() and title_text.strip() != "텐핑":
                            title = title_text.strip()
                            break
                    except: continue
            except: pass
            
            # 2. 메시지 복사하기 내용 및 홍보 링크 추출
            message_content = ""
            affiliate_url = ""
            try:
                # 홍보 문구 추출 (id가 textMessage인 경우가 많음)
                message_selectors = ["#textMessage", ".msg_box", ".copy_text"]
                for sel in message_selectors:
                    try:
                        message_content = await page.inner_text(sel, timeout=3000)
                        if message_content.strip(): break
                    except: continue

                # iryan.kr 또는 tenping.kr 링크 추출
                if message_content:
                    url_match = re.search(r'https?://(?:iryan\.kr|tenping\.kr/i/)[^\s]+', message_content)
                    if url_match:
                        affiliate_url = url_match.group(0)
                
                # 별도로 링크 버튼에서 추출 시도
                if not affiliate_url:
                    link_btn = page.locator("a[href*='iryan.kr'], a[href*='tenping.kr/i/']").first
                    if await link_btn.count() > 0:
                        affiliate_url = await link_btn.get_attribute("href")
            except: pass
            
            # 3. 유튜브 링크 추출
            youtube_url = ""
            try:
                # iframe src 또는 유튜브 링크 텍스트 찾기
                youtube_iframe = page.locator("iframe[src*='youtube.com']")
                if await youtube_iframe.count() > 0:
                    youtube_url = await youtube_iframe.get_attribute("src")
                    # embed 형태면 일반 링크로 변환 시도
                    if "/embed/" in youtube_url:
                        vid = youtube_url.split("/embed/")[1].split("?")[0]
                        youtube_url = f"https://www.youtube.com/watch?v={vid}"
            except: pass

            # 4. 이미지 크리에이티브 추출
            image_urls = []
            try:
                # 이미지 리스트 내의 다운로드 가능한 이미지들
                images = page.locator(".creative_list img, .img_area img")
                count = await images.count()
                for i in range(min(count, 5)): # 최대 5개
                    src = await images.nth(i).get_attribute("src")
                    if src and src.startswith("http") and "qr" not in src.lower():
                        image_urls.append(src)
            except: pass

            # 5. QR 코드 추출
            qr_url = ""
            try:
                qr_img = page.locator("img[src*='qr'], .qr_area img").first
                if await qr_img.count() > 0:
                    qr_url = await qr_img.get_attribute("src")
            except: pass

            # 6. 추천 단어 (태그)
            recommended_tags = []
            try:
                tags = await page.inner_text(".tag_area, .recommend_word", timeout=2000)
                recommended_tags = [t.strip() for t in tags.replace("#", "").split(",") if t.strip()]
            except: pass

            # 7. 주의사항 (사후 캐시 차감 조건 등)
            precautions = ""
            try:
                precautions = await page.inner_text(".notice_area, .caution_area", timeout=2000)
            except: pass

            # 8. 소문 배너 퍼가기 HTML 코드 추출
            banner_html = ""
            try:
                # 텐핑 상세 페이지에서 배너 코드가 있는 textarea 찾기
                # 보통 textarea#html_url, .textarea_copy 또는 <a><img>가 포함된 코드 블록
                banner_selectors = ["textarea#html_url", ".textarea_copy", "textarea"]
                for sel in banner_selectors:
                    els = page.locator(sel)
                    count = await els.count()
                    for i in range(count):
                        val = await els.nth(i).input_value(timeout=1000)
                        if val and "<a href" in val and "<img" in val:
                            banner_html = val.strip()
                            break
                    if banner_html: break
            except: pass

            print(f"[추출기] 추출 완료: {title[:20]}...")
            return {
                "title": title,
                "message": message_content,
                "url": affiliate_url,
                "youtube": youtube_url,
                "images": image_urls,
                "qr": qr_url,
                "tags": recommended_tags,
                "precautions": precautions,
                "banner_html": banner_html
            }
        except Exception as e:
            print(f"[추출기] 정보 추출 실패: {e}")
            return None
        finally:
            await browser.close()

if __name__ == "__main__":
    async def test():
        info = await extract_tenping_info()
        print(info)
    asyncio.run(test())
