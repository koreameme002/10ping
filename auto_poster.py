import asyncio
from groq import Groq
from playwright.async_api import async_playwright
import config
import os
import campaign_extractor

# Groq 설정
client = Groq(api_key=config.GROQ_API_KEY)

# === 사용자 입력 영역 ===
TARGET_CAMPAIGN_URL = None 
# ========================

async def generate_content(campaign_info):
    """
    참조 블로그(cobe_fair) 스타일을 반영하여 고품질 원고를 생성합니다.
    """
    prompt = f"""
    당신은 전문 블로거이자 제휴 마케터입니다. 
    아래의 캠페인 정보와 참조 블로그 스타일을 바탕으로 네이버 블로그에 최적화된 고품질 포스팅 원고를 작성해 주세요.
    
    [캠페인 정보]
    - 제목: {campaign_info['title']}
    - 기본 메시지: {campaign_info['message']}
    - 신청 링크: {campaign_info['url']}
    - 유튜브 링크: {campaign_info['youtube']}
    - 추천 태그: {', '.join(campaign_info['tags'])}
    - 주의사항: {campaign_info['precautions']}
    
    [참조 스타일 분석 (cobe_fair)]
    1. 제목: [지역/행사] 제목 (주요 혜택 강조) 형태. 예: [수원 코베] 베이비페어 무료입장 및 혜택 총정리!
    2. 도입부: "안녕하세요😊 코베 베이비페어 사무국입니다❤️"와 같은 친절하고 공식적인 인사말 사용.
    3. 본문 구조: 
       - 행사 개요 (날짜, 장소)
       - 주요 이벤트 및 브랜드 소개 (불렛포인트 ✨, ✅ 활용)
       - [무료입장 신청하기] 형태의 강력한 CTA 포함
    4. 톤앤매너: 친절하고 신뢰감 있는 "공식 블로그" 말투. 이모지 적극 활용.
    
    [작성 지침]
    1. 제목은 반드시 [지역/행사명]을 포함하되 클릭을 유도하는 후크를 넣으세요.
    2. 본문 중간에 자연스럽게 [신청 링크]를 '직접 클릭 가능한 형태'로 2~3번 언급하세요.
    3. 유튜브 링크가 있다면 "영상으로 미리보기" 섹션을 만들어 언급하세요.
    4. 마지막에는 반드시 공정위 문구("이 포스팅은 소정의 수익이 발생할 수 있습니다")를 포함하세요.
    
    출력 형식:
    TITLE: [제목]
    CONTENT: [본문 내용]
    TAGS: [태그1, 태그2, 태그3]
    """
    
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
    )
    return chat_completion.choices[0].message.content

async def post_to_tistory(title, content, tags):
    async with async_playwright() as p:
        if not os.path.exists(config.TISTORY_SESSION_PATH):
            print("티스토리 세션 파일이 없습니다.")
            return

        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=config.TISTORY_SESSION_PATH)
        page = await context.new_page()

        try:
            write_url = f"https://{config.TISTORY_BLOG_NAME}.tistory.com/manage/newpost/"
            await page.goto(write_url)
            await page.wait_for_load_state("networkidle")
            
            # 1. 제목 입력
            print("[티스토리] 제목 입력 중...")
            await page.wait_for_selector("#post-title-inp", timeout=10000)
            await page.fill("#post-title-inp", title)
            
            # 2. 본문 입력 (TinyMCE iframe 사용)
            print("[티스토리] 본문 입력 중...")
            # 에디터 프레임 대기
            editor_frame = page.frame_locator("#editor-tistory_ifr")
            await editor_frame.locator("body#tinymce").click()
            await asyncio.sleep(1)
            
            # 본문을 한 자씩 입력하기보다 한 번에 붙여넣기 시도 (안정성)
            # await page.keyboard.type(content, delay=1)
            # 또는 clipboard 활용이 좋지만 playwright에서는 type이 무난
            await page.keyboard.type(content)
            
            # 3. 태그 입력
            if tags:
                print("[티스토리] 태그 입력 중...")
                await page.fill("#tagText", tags)
                await page.keyboard.press("Enter")

            print(f"[티스토리] 입력 완료 (수동 확인 필요)")
            # 브라우저를 닫지 않고 유지
            print("[티스토리] 브라우저를 유지합니다. 수동으로 수정/발행 후 닫아주세요.")
        except Exception as e:
            print(f"[티스토리] 오류: {e}")
        # finally:
        #     await browser.close() # 닫지 않음

async def post_to_naver(title, content, campaign_info):
    async with async_playwright() as p:
        if not os.path.exists(config.NAVER_SESSION_PATH):
            print("네이버 세션 파일이 없습니다.")
            return

        # 디버깅을 위해 headless=False 유지
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=config.NAVER_SESSION_PATH)
        page = await context.new_page()

        try:
            # 1. 글쓰기 페이지 진입
            print("[네이버] 글쓰기 페이지 진입 중...")
            write_url = f"https://blog.naver.com/{config.NAVER_ID}?Redirect=Write"
            await page.goto(write_url)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
            
            # 2. mainFrame 찾기
            main_frame = page.frame_locator("#mainFrame")
            
            # 3. 팝업 및 도움말 제거 (이어서 쓰기 팝업 포함)
            print("[네이버] 팝업 및 도움말 제거...")
            # '이어서 쓰기' 팝업 등 네이버 기본 알럿 창 닫기 시도
            # "작성 중인 글이 있습니다. 이어서 쓰시겠습니까?" -> 취소(새로 쓰기) 클릭
            try:
                # '취소' 버튼 (새로 쓰기)
                cancel_btn = main_frame.locator(".se-popup-button-cancel, button:has-text('취소'), .btn_cancel")
                if await cancel_btn.is_visible():
                    await cancel_btn.click()
                    print("[네이버] 이어서 쓰기 팝업 취소 클릭")
                    await asyncio.sleep(1)
            except: pass

            for _ in range(3):
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                
                # 프레임 내부의 닫기 버튼들
                selectors = [
                    ".se-help-close", ".se-help-container .se-button-close", 
                    "button:has-text('도움말 닫기')", ".se-popup-button-cancel",
                    ".se-popup-button-close", ".btn_close", ".se-popup-close"
                ]
                for sel in selectors:
                    try:
                        btn = main_frame.locator(sel)
                        if await btn.is_visible():
                            await btn.click(timeout=1000)
                            print(f"[네이버] 프레임 내부 닫기 버튼 클릭: {sel}")
                    except: pass

            # 4. 제목 입력
            print("[네이버] 제목 입력 중...")
            # 제목 셀렉터 후보들
            title_selectors = [".se-documentTitle .se-placeholder", ".se-title-text", "[contenteditable='true'].se-documentTitle"]
            success = False
            for sel in title_selectors:
                try:
                    el = main_frame.locator(sel).first
                    if await el.is_visible():
                        await el.click()
                        await asyncio.sleep(0.5)
                        # 이미 텍스트가 있을 수 있으므로 모두 선택 후 삭제 시도
                        await page.keyboard.press("Control+A")
                        await page.keyboard.press("Backspace")
                        await page.keyboard.type(title, delay=20)
                        success = True
                        break
                except: continue
            
            if not success:
                print("[네이버] 제목 입력 영역을 찾지 못해 강제 입력을 시도합니다.")
                await page.keyboard.press("Tab") # 보통 첫 번째는 제목
                await page.keyboard.type(title)

            # 5. 본문 입력
            print("[네이버] 본문 입력 중...")
            content_selectors = [".se-main-container .se-placeholder", ".se-content", ".se-component-content", ".se-main-container"]
            success = False
            for sel in content_selectors:
                try:
                    el = main_frame.locator(sel).first
                    if await el.is_visible():
                        await el.click()
                        await asyncio.sleep(0.5)
                        
                        # 이미지 링크 멘트 추가
                        image_ment = ""
                        if campaign_info.get('images'):
                            image_ment = "[참고: 아래 이미지를 본문에 삽입하는 것을 추천합니다]\n" + "\n".join(campaign_info['images'][:3]) + "\n\n"
                        
                        await page.keyboard.type(image_ment + content, delay=5)
                        success = True
                        break
                except: continue

            if not success:
                print("[네이버] 본문 입력 영역을 찾지 못해 Tab 이동 후 입력을 시도합니다.")
                await page.keyboard.press("Tab") # 제목 다음은 본문
                await page.keyboard.type(content)
            
            print(f"[네이버] 포스팅 입력 완료 (임시저장 확인 필요)")
            # 브라우저를 닫지 않고 유지
            print("[네이버] 브라우저를 유지합니다. 수동으로 수정/발행 후 닫아주세요.")
        except Exception as e:
            print(f"[네이버] 오류: {e}")
        # finally:
        #     await browser.close() # 닫지 않음

if __name__ == "__main__":
    async def main():
        # 0. 캠페인 정보 추출
        if TARGET_CAMPAIGN_URL:
            campaign_info = await campaign_extractor.extract_tenping_info(TARGET_CAMPAIGN_URL)
        else:
            campaign_info = await campaign_extractor.extract_tenping_info()
        
        if not campaign_info:
            print("캠페인 정보를 가져오지 못했습니다.")
            return
            
        # 1. AI 원고 생성
        print(f"1. AI 원고 생성 중... (대상: {campaign_info['title']})")
        raw_post = await generate_content(campaign_info)
        
        # 제목 파싱
        title = campaign_info['title']
        for line in raw_post.split("\n"):
            if line.startswith("TITLE:"): title = line.replace("TITLE:", "").strip()
        
        print(f"생성 제목: {title}")
        
        # 2. 포스팅
        await post_to_naver(title, raw_post, campaign_info)
        await post_to_tistory(title, raw_post, "")

    asyncio.run(main())
