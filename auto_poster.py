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

async def generate_content(campaign_info, platform="naver"):
    """
    참조 블로그(cobe_fair) 스타일을 반영하여 고품질 원고를 생성합니다.
    platform: "naver" 또는 "tistory"
    """
    
    platform_name = "네이버 블로그" if platform == "naver" else "티스토리"
    
    prompt = f"""
    당신은 전문 블로거이자 제휴 마케터입니다. 
    아래의 캠페인 정보와 참조 블로그 스타일을 바탕으로 {platform_name}에 최적화된 고품질 포스팅 원고를 작성해 주세요.
    
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
    
    [작성 지침 ({platform_name}용)]
    1. 제목은 반드시 [지역/행사명]을 포함하되 클릭을 유도하는 후크를 넣으세요.
    2. 본문 중간에 자연스럽게 [신청 링크]를 '직접 클릭 가능한 형태'로 2~3번 언급하세요.
    3. 유튜브 링크가 있다면 "영상으로 미리보기" 섹션을 만들어 언급하세요.
    4. 마지막에는 반드시 공정위 문구("이 포스팅은 소정의 수익이 발생할 수 있습니다")를 포함하세요.
    {"5. 네이버 블로그는 이모지를 더 적극적으로 사용하고, 티스토리는 조금 더 정돈된 레이아웃을 선호합니다." if platform == "tistory" else ""}
    
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

def format_html_content(content, campaign_info):
    """생성된 텍스트 본문을 HTML 형식으로 변환하고 각종 요소를 삽입합니다."""
    # 1. 기본 줄바꿈 처리
    html_content = content.replace('\n', '<br>')
    
    # 2. 이미지 삽입 (상단에 모아서 배치)
    images_html = ""
    if campaign_info.get('images'):
        for img in campaign_info['images'][:3]: # 최대 3개
            images_html += f'<div style="text-align:center; margin:20px 0;"><img src="{img}" style="max-width:100%;"></div>'
            
    if images_html:
        html_content = images_html + "<br><br>" + html_content
        
    # 3. 제휴 링크 버튼화
    if campaign_info.get('url'):
        btn_html = f'''<div style="text-align:center; margin:30px 0;">
            <a href="{campaign_info['url']}" target="_blank" style="display:inline-block; padding:15px 30px; background-color:#1cc800; color:#fff; font-size:20px; font-weight:bold; border-radius:10px; text-decoration:none;">👉 상세 혜택 확인 및 신청하기 👈</a></div>'''
        
        # 본문 내에 링크 텍스트가 있으면 치환 시도
        if campaign_info['url'] in html_content:
            html_content = html_content.replace(campaign_info['url'], btn_html)
        else:
            # 없으면 맨 뒤에 추가
            html_content += "<br><br>" + btn_html

    # 4. 소문 배너 삽입 (마지막)
    if campaign_info.get('banner_html'):
        html_content += f'<div style="text-align:center; margin-top:50px;">{campaign_info["banner_html"]}</div>'
        
    return html_content

async def post_to_tistory(title, content, tags=None, campaign_info=None):
    if campaign_info is None: campaign_info = {}
    p = await async_playwright().start()
    if not os.path.exists(config.TISTORY_SESSION_PATH):
        print("티스토리 세션 파일이 없습니다.")
        return None

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
        editor_frame = page.frame_locator("#editor-tistory_ifr")
        
        # 서식 초기화 및 HTML 주입
        html_to_insert = format_html_content(content, campaign_info)
        
        # iframe 내부 document에 접근하여 HTML 삽입
        await editor_frame.locator("body#tinymce").evaluate(f'''(body) => {{
            body.focus();
            document.execCommand('insertHTML', false, `{html_to_insert}`);
        }}''')
        
        await asyncio.sleep(1)
        
        # 3. 태그 입력
        if tags:
            print("[티스토리] 태그 입력 중...")
            await page.fill("#tagText", tags)
            await page.keyboard.press("Enter")

        print(f"[티스토리] 입력 완료 (수동 확인 필요)")
        print("[티스토리] 브라우저를 유지합니다.")
        return browser # 브라우저 객체 반환
    except Exception as e:
        print(f"[티스토리] 오류: {e}")
        return None

async def post_to_naver(title, content, campaign_info):
    p = await async_playwright().start()
    if not os.path.exists(config.NAVER_SESSION_PATH):
        print("네이버 세션 파일이 없습니다.")
        return None

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
        
        html_to_insert = format_html_content(content, campaign_info)
        
        for sel in content_selectors:
            try:
                el = main_frame.locator(sel).first
                if await el.is_visible():
                    await el.click()
                    await asyncio.sleep(0.5)
                    
                    # 네이버 에디터는 iframe 밖에서 iframe 안의 contenteditable 요소에 접근
                    await el.evaluate(f'''(el) => {{
                        document.execCommand('removeFormat', false, null); // 기존 서식(취소선 등) 제거
                        document.execCommand('insertHTML', false, `{html_to_insert}`);
                    }}''')
                    
                    success = True
                    break
            except: continue

        if not success:
            print("[네이버] 본문 입력 영역을 찾지 못해 Tab 이동 후 입력을 시도합니다.")
            await page.keyboard.press("Tab") # 제목 다음은 본문
            await asyncio.sleep(0.5)
            # 현재 활성화된 요소(포커스)에 HTML 삽입
            await main_frame.evaluate(f'''() => {{
                document.execCommand('removeFormat', false, null);
                document.execCommand('insertHTML', false, `{html_to_insert}`);
            }}''')
        
        print(f"[네이버] 포스팅 입력 완료 (임시저장 확인 필요)")
        print("[네이버] 브라우저를 유지합니다.")
        return browser
    except Exception as e:
        print(f"[네이버] 오류: {e}")
        return None

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
