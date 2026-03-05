import asyncio
import auto_poster
import os
import json
import re

async def run_posting():
    # 캠페인 정보 
    info = {
        "title": "나의 건강 유형과 가장 잘 맞는 내 짝은 누구? 간단한 테스트!",
        "message": "[건강MBTI] 나의 건강 유형과 가장 잘 맞는 내 짝은 누구? 간단한 테스트!\n진행하기 : https://iryan.kr/t8m3j6v7u9",
        "url": "https://iryan.kr/t8m3j6v7u9",
        "youtube": "",
        "images": [
            "https://tenping.kr/Home/GetCreativeImage?CreativeID=2026022408360001&Type=1",
            "https://tenping.kr/Home/GetCreativeImage?CreativeID=2026022408360001&Type=2"
        ],
        "qr": "https://tenping.kr/Home/GetQRCode?CampaignID=2026022408360001",
        "tags": ["건강", "MBTI", "테스트"],
        "precautions": ""
    }

    print("\n[AI 본문 생성 중...]")
    # generate_content는 async이며 campaign_info만 인자로 받음
    generated_text = await auto_poster.generate_content(info)
    
    # 생성된 텍스트에서 TITLE, CONTENT, TAGS 추출
    try:
        title_match = re.search(r'TITLE:\s*(.*)', generated_text)
        content_match = re.search(r'CONTENT:\s*(.*)', generated_text, re.DOTALL)
        tags_match = re.search(r'TAGS:\s*(.*)', generated_text)
        
        final_title = title_match.group(1).strip() if title_match else f"[추천] {info['title']}"
        # CONTENT부터 TAGS 직전까지 추출 (TAGS가 있다면)
        raw_content = content_match.group(1).strip() if content_match else generated_text
        final_content = raw_content.split("TAGS:")[0].strip()
        final_tags = tags_match.group(1).strip() if tags_match else ",".join(info['tags'])
    except:
        final_title = f"[추천] {info['title']}"
        final_content = generated_text
        final_tags = ",".join(info['tags'])

    # 1. 네이버 포스팅
    print("\n[네이버 블로그 포스팅 시작]")
    print(f"제목: {final_title}")
    try:
        await auto_poster.post_to_naver(final_title, final_content, info)
        print("네이버 포스팅 완료 (임시저장 확인 필요)")
    except Exception as e:
        print(f"네이버 오류: {e}")

    # 2. 티스토리 포스팅
    print("\n[티스토리 블로그 포스팅 시작]")
    try:
        await auto_poster.post_to_tistory(final_title, final_content, final_tags)
        print("티스토리 포스팅 완료")
    except Exception as e:
        print(f"티스토리 오류: {e}")

if __name__ == "__main__":
    asyncio.run(run_posting())
