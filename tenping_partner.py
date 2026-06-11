import os
import time
import json
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TenpingPartnerAPI:
    """텐핑(Tenping) Open API 연동 및 광고 리스트 수집 클래스"""

    def __init__(self):
        # 사용자가 제공한 MemberID 우선 사용
        self.member_id = os.getenv("TENPING_MEMBER_ID", "1fOatP7hU1IVcRiOaclGuk4ALWPi5SfkNAig5ZaxEUDZOTsMyotbTRFnJwvTR8Bh")
        self.domain = "http://tenping.kr"

    def search_products(self, keyword: str = "", limit: int = 5) -> list:
        """텐핑 API로 제휴 광고 목록을 조회하고, 키워드 매칭 및 개수 제한에 맞게 반환"""
        
        # MemberID가 누락된 경우 Fallback 보호
        if not self.member_id or self.member_id == "your_tenping_member_id_here":
            logging.warning("텐핑 MemberID가 설정되지 않았습니다. 테스트 모의(Mock) 데이터를 반환합니다.")
            return self._get_mock_campaigns(keyword, limit)

        # 텐핑 API URL 설정 (PageSize는 limit보다 여유있게 가져와서 필터링할 수 있도록 30개로 지정)
        path = "/adbox/list"
        query_string = f"MemberID={self.member_id}&PageSize=30&CampaignType=0&MinClickPoint=0&MinCurrentPoint=0"
        url = f"{self.domain}{path}?{query_string}"

        try:
            logging.info(f"텐핑 API 호출 시도: {url}")
            response = requests.get(url, timeout=15)
            
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get("ResultCode") == 200 and "List" in res_data:
                    raw_list = res_data["List"]
                    logging.info(f"텐핑 API 광고 목록 수신 성공: 총 {len(raw_list)}개")
                    
                    # 수집된 데이터를 공통 규격으로 변환
                    campaigns = []
                    for item in raw_list:
                        title = item.get("ContentTitle", "")
                        memo = item.get("ContentMemo", "")
                        link = item.get("Link", "")
                        
                        # 썸네일 이미지 매핑 (LImage -> MImage -> SImage -> Images 상세 순)
                        image = item.get("LImage") or item.get("MImage") or item.get("SImage")
                        if not image and item.get("Images"):
                            img_obj = item.get("Images")
                            image = img_obj.get("size512x512") or img_obj.get("size360x240") or img_obj.get("size320x160")
                        
                        if not image:
                            image = "https://img.tenping.kr/Content/Upload/Images/10ping-icon-1200x1200.png" # 기본 로고
                            
                        campaigns.append({
                            "productName": title,
                            "productPrice": item.get("ClickPoint", 0), # 텐핑의 경우 적립 포인트 정보
                            "productImage": image,
                            "productUrl": link,
                            "discountRate": 0, # 텐핑은 할인율이 없으므로 0 고정
                            "productMemo": memo
                        })
                    
                    # 키워드 필터링 적용 (키워드가 제목 또는 설명에 들어있는지 확인)
                    filtered = []
                    if keyword:
                        for c in campaigns:
                            if keyword.lower() in c["productName"].lower() or keyword.lower() in c["productMemo"].lower():
                                filtered.append(c)
                        
                        logging.info(f"키워드 '{keyword}' 매칭 결과: {len(filtered)}개 매칭됨")
                    
                    # 필터링 결과가 없거나 부족할 경우, 전체 리스트에서 인기 광고로 보충
                    if len(filtered) < limit:
                        needed = limit - len(filtered)
                        for c in campaigns:
                            if c not in filtered:
                                filtered.append(c)
                                if len(filtered) >= limit:
                                    break
                                    
                    return filtered[:limit]
                else:
                    logging.error(f"텐핑 API 응답 오류 (ResultCode: {res_data.get('ResultCode')})")
            else:
                logging.error(f"텐핑 API HTTP 오류: {response.status_code} - {response.text}")
        except Exception as e:
            logging.error(f"텐핑 API 호출 중 예외 발생: {e}")

        # API 호출 실패 시 Fallback 처리
        logging.info("텐핑 API 통신 실패로 모의 데이터를 반환합니다.")
        return self._get_mock_campaigns(keyword, limit)

    def _get_mock_campaigns(self, keyword: str = "", limit: int = 5) -> list:
        """텐핑 API 미작동 혹은 미설정 시 제공할 대체 모의 데이터 생성기"""
        mock_templates = [
            {
                "productName": f"[대박 할인] 2026 최신형 {keyword or '스마트기기'} 특별 기획전 오픈!",
                "productPrice": 3500,
                "productImage": "https://img.tenping.kr/Content/Upload/Images/10ping-icon-1200x1200.png",
                "productUrl": "http://yimay.kr/mockTenping1",
                "discountRate": 0,
                "productMemo": "최신 인기 전자기기부터 생활용품까지 초특가 할인 혜택을 드립니다. 무료 배송 및 즉시 할인 혜택을 지금 확인해보세요!"
            },
            {
                "productName": f"[무료 가입] 하루 10분 건강 습관, {keyword or '유산균'} 100원 체험단 선착순 모집",
                "productPrice": 2500,
                "productImage": "https://img.tenping.kr/Content/Upload/Images/10ping-icon-1200x1200.png",
                "productUrl": "http://yimay.kr/mockTenping2",
                "discountRate": 0,
                "productMemo": "아침 방송 화제의 건강 솔루션! 선착순 100분께 건강 관리 무료 상담 및 무료 샘플 키트를 즉시 발송해 드립니다."
            },
            {
                "productName": f"[이벤트] 금융 우대 금리 혜택 및 무료 자산설계 컨설팅 신청하기",
                "productPrice": 4800,
                "productImage": "https://img.tenping.kr/Content/Upload/Images/10ping-icon-1200x1200.png",
                "productUrl": "http://yimay.kr/mockTenping3",
                "discountRate": 0,
                "productMemo": "직장인 및 주부를 위한 특별 금융 우대 혜택 총정리! 내 숨은 자산 찾기부터 똑똑한 재테크 포트폴리오를 무료로 받아보세요."
            }
        ]
        
        campaigns = []
        for i in range(min(limit, len(mock_templates))):
            template = mock_templates[i].copy()
            campaigns.append(template)
        return campaigns

if __name__ == "__main__":
    partner = TenpingPartnerAPI()
    result = partner.search_products("건강", 2)
    print("텐핑 광고 검색 결과:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
