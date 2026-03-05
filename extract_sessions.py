import asyncio
import os
from playwright.async_api import async_playwright

async def save_session(platform):
    async with async_playwright() as p:
        # 브라우저 실행 (사용자가 로그인할 수 있도록 headful 모드로 실행)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        if platform == "naver":
            import config
            url = f"https://blog.naver.com/{config.NAVER_ID}" if config.NAVER_ID != "YOUR_NAVER_ID" else "https://www.naver.com"
            file_path = "naver_session.json"
        elif platform == "tistory":
            import config
            url = f"https://{config.TISTORY_BLOG_NAME}.tistory.com/manage" if config.TISTORY_BLOG_NAME != "YOUR_TISTORY_BLOG_NAME" else "https://www.tistory.com"
            file_path = "tistory_session.json"
        elif platform == "tenping":
            import config
            url = "https://tenping.kr/Account/Login"
            file_path = config.TENPING_SESSION_PATH
        
        await page.goto(url)
        print(f"\n[{platform.upper()}] 페이지로 이동했습니다.")
        print("1. 브라우저에서 '로그인'을 진행해 주세요.")
        print("2. 로그인이 완료되어 본인의 블로그 관리 화면이 보이면")
        print("3. 터미널로 돌아와 'y'를 입력하고 Enter를 눌러주세요.")

        while True:
            user_input = input("로그인 및 블로그 접속을 완료하셨나요? (y/n): ").lower()
            if user_input == 'y':
                break

        # 세션(쿠키 및 로컬 스토리지) 저장
        await context.storage_state(path=file_path)
        print(f"성공! 세션 정보가 {file_path}에 저장되었습니다.")
        
        await browser.close()

if __name__ == "__main__":
    print("--- 블로그 자동화 세션 추출 도구 ---")
    print("1. 네이버(Naver)")
    print("2. 티스토리(Tistory)")
    choice = input("어느 플랫폼의 세션을 추출할까요? (1/2): ")

    if choice == '1':
        asyncio.run(save_session("naver"))
    elif choice == '2':
        asyncio.run(save_session("tistory"))
    else:
        print("잘못된 선택입니다.")
