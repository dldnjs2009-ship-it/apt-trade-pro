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

    print("📡 한국부동산원 청약홈 공식 API로부터 입주예정 단지 수집 시작...")

    while True:
        params = {
            "page": page,
            "perPage": per_page,
            "serviceKey": api_key
        }
        
        try:
            res = requests.get(API_URL, params=params, timeout=15)
        except Exception as e:
            print(f"API 요청 오류 발생: {e}")
            break

        if res.status_code != 200:
            print(f"API 응답 실패 (HTTP {res.status_code})")
            break

        try:
            data = res.json()
        except Exception:
            print("JSON 응답 파싱 실패")
            break

        items = data.get("data", [])
        if not items:
            break

        for item in items:
            house_nm = str(item.get("HOUSE_NM", "")).strip()
            addr = str(item.get("HSSPLY_ADRES", "")).strip()
            mvn_ym = str(item.get("MVN_PREARNGE_YM", "")).strip().replace(".", "").replace("-", "")
            tot_hshld = item.get("TOT_SUPLY_HSHLDCO", 0)
            brand = str(item.get("BSNS_MBY_NM", "")).strip() or "민간분양"

            # 2015년 ~ 2030년 사이 유효 입주연월 필터링
            if len(mvn_ym) >= 6:
                try:
                    s_year = int(mvn_ym[:4])
                    s_month = f"{mvn_ym[:4]}-{mvn_ym[4:6]}"
                except ValueError:
                    continue

                if 2015 <= s_year <= 2030:
                    sido, city, gu, dong = parse_korean_address(addr)
                    if sido and city:
                        try:
                            h_count = int(tot_hshld)
                        except (ValueError, TypeError):
                            h_count = 0

                        if h_count > 0:
                            records.append({
                                "sido": sido,
                                "city": city,
                                "gu": gu,
                                "dong": dong,
                                "apt": house_nm,
                                "supply_year": s_year,
                                "supply_month": s_month,
                                "households": h_count,
                                "pyeong_info": "일반/국평형",
                                "brand": brand
                            })

        print(f"  - {page}페이지 수집 완료 ({len(items)}건 조회)")
        # 전체 데이터 건수를 채웠거나 더 이상 없으면 중단 (최대 15페이지 탐색)
        if len(items) < per_page or page >= 15:
            break
        page += 1

    print(f"총 {len(records)}개의 유효 신축 분양 단지가 수집되었습니다.")
    return records

def update_csv():
    api_key = os.environ.get("DATA_GO_KR_SERVICE_KEY")
    if not api_key:
        print("경고: DATA_GO_KR_SERVICE_KEY 환경변수가 설정되지 않았습니다.")
        return

    # 1. API 데이터 수집
    api_records = fetch_applyhome_api(api_key)

    # 2. 기존 CSV 로드
    if os.path.exists(CSV_PATH):
        try:
            df_old = pd.read_csv(CSV_PATH)
        except Exception:
            df_old = pd.DataFrame(columns=COLUMNS)
    else:
        df_old = pd.DataFrame(columns=COLUMNS)

    # 3. 데이터 병합 및 중복 정리
    if api_records:
        df_new = pd.DataFrame(api_records)
        combined = pd.concat([df_old, df_new], ignore_index=True)
    else:
        combined = df_old

    if not combined.empty:
        # 단지명, 입주예정월, 세대수 기준 중복 제거
        combined.drop_duplicates(subset=["city", "gu", "apt", "supply_month"], keep="last", inplace=True)
        combined.sort_values(by=["supply_month", "households"], ascending=[False, False], inplace=True)
        combined.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
        print(f"🎉 성공: supply_data.csv 갱신 완료 (총 {len(combined)}개 단지 적재)")
    else:
        print("적재할 데이터가 없습니다.")

if __name__ == "__main__":
    update_csv()
