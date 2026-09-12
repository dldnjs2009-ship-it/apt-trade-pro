import os
import re
import requests
import pandas as pd

CSV_PATH = "supply_data.csv"
API_URL = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail"

COLUMNS = ["sido", "city", "gu", "dong", "apt", "supply_year", "supply_month", "households", "pyeong_info", "brand"]

def parse_korean_address(addr: str):
    """
    공급위치 주소(예: '경기도 수원시 영통구 망포동 123' 또는 '서울특별시 강동구 둔촌동')를
    sido, city, gu, dong 형태로 분해
    """
    if not addr or not isinstance(addr, str):
        return None, None, None, None

    tokens = addr.strip().split()
    if len(tokens) < 2:
        return None, None, None, None

    sido = tokens[0]
    city = tokens[1]
    gu = ""
    dong = ""

    # 서울/광역시인 경우: 예) 서울특별시 강남구 역삼동
    if sido in ["서울특별시", "인천광역시", "부산광역시", "대구광역시", "대전광역시", "광주광역시", "울산광역시"]:
        gu = tokens[1] if len(tokens) > 1 else ""
        city = sido
        dong = tokens[2] if len(tokens) > 2 else "기타"
    # 경기도 및 도 단위인 경우: 예) 경기도 수원시 영통구 망포동
    else:
        if len(tokens) >= 3 and tokens[2].endswith("구"):
            gu = tokens[2]
            dong = tokens[3] if len(tokens) > 3 else "기타"
        else:
            gu = f"{city} 전체"
            dong = tokens[2] if len(tokens) > 2 else "기타"

    # 읍/면/동 정제
    dong_match = re.search(r'([가-힣0-9]+[동|읍|면|리])', dong)
    dong_clean = dong_match.group(1) if dong_match else dong

    return sido, city, gu, dong_clean

def fetch_applyhome_api(api_key: str):
    """한국부동산원 청약홈 APT 분양상세정보 오픈 API 실제 호출"""
    records = []
    page = 1
    per_page = 100
    MAX_PAGES = 300  # ← 15에서 대폭 상향: 과거(2015~) 데이터까지 누락 없이 모두 수집하기 위함
    oldest_seen = None
    newest_seen = None

    print("📡 한국부동산원 청약홈 공식 API로부터 입주예정 단지 수집 시작...")

    while True:
        params
