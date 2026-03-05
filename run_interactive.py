import asyncio
import campaign_extractor
import auto_poster
import sys

async def main():
    print("\n" + "="*50)
    print(" 텐핑 캠페인 선택 및 자동 포스팅 시스템 ")
    print("="*50)
    
    # 1. 캠페인 목록 가져오기
    print("\n[1/3] 캠페인 목록을 불러오는 중입니다...")
    campaigns = await campaign_extractor.get_campaign_list()
    
    if not campaigns:
        print("캠페인 목록을 가져오지 못했습니다. 시스템을 종료합니다.")
        return

    print("\n" + "-"*30)
    print(" 현재 진행 가능한 캠페인 목록:")
    for idx, camp in enumerate(campaigns, 1):
        print(f" {idx}. {camp['title']}")
    print("-"*30)

    # 2. 사용자 선택 (터미널 입력)
    try:
        choice = input("\n포스팅할 캠페인 번호를 선택하세요 (종료하려면 q): ")
        if choice.lower() == 'q':
            print("프로그램을 종료합니다.")
            return
            
        choice_idx = int(choice) - 1
        if choice_idx < 0 or choice_idx >= len(campaigns):
            print("잘못된 번호입니다.")
            return
            
        selected_campaign = campaigns[choice_idx]
        print(f"\n선택된 캠페인: {selected_campaign['title']}")
    except ValueError:
        print("숫자만 입력해 주세요.")
        return

    # 3. 정보 추출 및 포스팅 진행
    print(f"\n[2/3] '{selected_campaign['title']}' 정보 추출 및 본문 생성 중...")
    campaign_info = await campaign_extractor.extract_tenping_info(selected_campaign['url'])
    
    if not campaign_info:
        print("정보 추출에 실패했습니다.")
        return

    # AI 본문 생성
    print("AI를 통해 블로그 본문을 생성하고 있습니다...")
    naver_title = f"[추천] {campaign_info['title']} 신청 및 혜택 총정리!"
    naver_content = await auto_poster.generate_content(campaign_info, platform="naver")
    
    tistory_title = f"{campaign_info['title']} 상세 안내 및 이벤트 참여 방법"
    tistory_content = await auto_poster.generate_content(campaign_info, platform="tistory")

    # 4. 포스팅 실행
    print("\n[3/3] 포스팅을 시작합니다.")
    
    # 네이버 포스팅
    print("\n>>> 네이버 블로그 작업 중...")
    await auto_poster.post_to_naver(naver_title, naver_content, campaign_info)
    
    # 티스토리 포스팅
    print("\n>>> 티스토리 블로그 작업 중...")
    tags = ",".join(campaign_info.get('tags', ['재테크', '정보', '이벤트']))
    await auto_poster.post_to_tistory(tistory_title, tistory_content, tags)

    print("\n" + "="*50)
    print(" 모든 작업이 완료되었습니다! ")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
