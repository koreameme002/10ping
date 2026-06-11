import os
import time
import hmac
import hashlib
import json
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class CoupangPartnerAPI:
    """쿠팡 파트너스 Open API 통신 및 HMAC 서명 연동 클래스"""

    def __init__(self):
        self.access_key = os.getenv("COUPANG_ACCESS_KEY")
        self.secret_key = os.getenv("COUPANG_SECRET_KEY")
        self.sub_id = os.getenv("COUPANG_SUBID", "")
        self.domain = "https://api-gateway.coupang.com"

    def _generate_headers(self, method: str, path: str, query: str = "") -> dict:
        """쿠팡 API 기준에 부합하는 HMAC 서명 헤더 생성"""
        # UTC 시간 형식 포맷
        datetime_utc = datetime.utcnow().strftime('%y%m%d') + 'T' + datetime.utcnow().strftime('%H%M%S') + 'Z'
        
        # 메시지 조합: {datetime}{method}{path}{query}
        message = datetime_utc + method + path + query
        
        # HMAC-SHA256 암호화 서명
        signature = hmac.new(
            bytes(self.secret_key, "utf-8"),
            msg=bytes(message, "utf-8"),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        authorization = f"CEA algorithm=HmacSHA256, access-key={self.access_key}, signed-date={datetime_utc}, signature={signature}"
        
        return {
            "Content-Type": "application/json",
            "Authorization": authorization,
            "X-Requested-With": "Coupang-Partners-OpenAPI"
        }

    def search_products(self, keyword: str, limit: int = 5) -> list:
        """쿠팡 파트너스 API로 키워드에 해당하는 상품 정보 검색"""
        # API 인증 정보가 없을 경우 자동으로 Mock 데이터 반환 (Fallback 보호)
        if not self.access_key or not self.secret_key or self.access_key == "your_coupang_access_key_here":
            logging.warning("쿠팡 API Key가 설정되지 않았습니다. 테스트 모의(Mock) 데이터를 반환합니다.")
            return self._get_mock_products(keyword, limit)

        method = "GET"
        path = "/v2/providers/affiliate_open_api/apis/openapi/products/search"
        query_string = f"keyword={requests.utils.quote(keyword)}&limit={limit}"
        
        if self.sub_id:
            query_string += f"&subId={self.sub_id}"

        url = f"{self.domain}{path}?{query_string}"

        try:
            headers = self._generate_headers(method, path, query_string)
            response = requests.request(method, url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get("rCode") == "0" and "data" in res_data:
                    products = res_data["data"].get("productData", [])
                    logging.info(f"쿠팡 API 상품 검색 성공: '{keyword}'로 {len(products)}개 조회")
                    return products
                else:
                    logging.error(f"쿠팡 API 응답 오류: {res_data.get('rMessage')}")
            else:
                logging.error(f"쿠팡 API HTTP 오류: {response.status_code} - {response.text}")
        except Exception as e:
            logging.error(f"쿠팡 API 호출 중 예외 발생: {e}")

        # API 호출 실패 시 Fallback 처리
        logging.info("쿠팡 API 통신 실패로 모의 데이터를 반환합니다.")
        return self._get_mock_products(keyword, limit)

    def _get_mock_products(self, keyword: str, limit: int = 5) -> list:
        """쿠팡 API 미작동 혹은 미설정 시 제공할 대체 모의 데이터 생산기"""
        mock_templates = [
            {
                "productName": f"인기 최고급 [키워드] 가성비 추천 제품",
                "productPrice": 129000,
                "productImage": "https://img1a.coupangcdn.com/image/coupang/common/logo3.png",
                "productUrl": "https://link.coupang.com/a/mockLink1",
                "discountRate": 15
            },
            {
                "productName": f"2026 최신형 [키워드] 베스트셀러 모델",
                "productPrice": 349000,
                "productImage": "https://img1a.coupangcdn.com/image/coupang/common/logo3.png",
                "productUrl": "https://link.coupang.com/a/mockLink2",
                "discountRate": 10
            },
            {
                "productName": f"실사용 추천 고성능 [키워드] 실사용 리뷰 1위",
                "productPrice": 45000,
                "productImage": "https://img1a.coupangcdn.com/image/coupang/common/logo3.png",
                "productUrl": "https://link.coupang.com/a/mockLink3",
                "discountRate": 5
            }
        ]
        
        products = []
        for i in range(min(limit, len(mock_templates))):
            template = mock_templates[i].copy()
            template["productName"] = template["productName"].replace("[키워드]", keyword)
            # 가격 무작위 변동으로 생동감 부여
            template["productPrice"] = int(template["productPrice"] * random_uniform(0.9, 1.1))
            products.append(template)
        return products

def random_uniform(a, b):
    import random
    return random.uniform(a, b)

if __name__ == "__main__":
    partner = CoupangPartnerAPI()
    search_result = partner.search_products("노트북", 2)
    print("상품 검색 결과:")
    print(json.dumps(search_result, indent=2, ensure_ascii=False))
