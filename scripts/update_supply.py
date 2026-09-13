import os
import re
import requests
import pandas as pd

CSV_PATH = "supply_data.csv"
API_URL = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail"

COLUMNS = ["sido", "city", "gu", "dong", "apt", "supply_year", "supply_month", "households", "pyeong_info", "brand"]

# ── 1. 도로명주소 오인 방지 정규식 주소 파싱 엔진 ─────────────────
def parse_korean_address_robust(addr: str):
    """
    공급위치 주소 문자열에서 시·도, 시·군, 구, 법정동을 추출.
    도로명(세지로, 정조로, 덕영대로 등)이 법정동으로 잡히는 버그를 차단.
    """
    if not addr or not isinstance(addr, str):
        return None, None, None, None

    tokens = addr.strip().split()
    if len(tokens) < 2:
        return None, None, None, None

    sido_raw = tokens[0]
    
    # 광역 시·도 표준화
    sido_map = {
        "서울": "서울특별시", "서울특별시": "서울특별시",
        "경기": "경기도", "경기도": "경기도",
        "인천": "인천광역시", "인천광역시": "인천광역시",
        "부산": "부산광역시", "부산광역시": "부산광역시",
        "대구": "대구광역시", "대구광역시": "대구광역시",
        "대전": "대전광역시", "대전광역시": "대전광역시",
        "광주": "전남광주통합특별시", "전남": "전남광주통합특별시", "전남광주": "전남광주통합특별시",
        "울산": "울산광역시", "울산광역시": "울산광역시",
        "세종": "세종특별자치시", "세종특별자치시": "세종특별자치시",
        "강원": "강원특별자치도", "강원특별자치도": "강원특별자치도", "강원도": "강원특별자치도",
        "충북": "충청북도", "충청북도": "충청북도",
        "충남": "충청남도", "충청남도": "충청남도",
        "전북": "전북특별자치도", "전북특별자치도": "전북특별자치도",
        "경북": "경상북도", "경북경상북도": "경상북도",
        "경남": "경상남도", "경상남도": "경상남도",
        "제주": "제주특별자치도", "제주특별자치도": "제주특별자치도", "제주도": "제주특별자치도"
    }
    sido = sido_map.get(sido_raw, sido_raw)

    # 1) 괄호 안 법정동 우선 추출: 예) "... 정조로 760 (팔달로3가)" -> 팔달로3가
    dong = "기타"
    paren_match = re.search(r'\(([가-힣0-9]+(?:동|읍|면|리|가))\)', addr)
    if paren_match:
        dong = paren_match.group(1)
    else:
        # 2) 주소 전체에서 도로명(로/길/대로)이 아닌 순수 동·읍·면·리·가 매칭
        dong_candidates = re.findall(r'([가-힣0-9]+(?:동|읍|면|리|가))(?=[\s\d,\)]|$)', addr)
        valid_dongs = [d for d in dong_candidates if not (d.endswith('로') or d.endswith('길') or d.endswith('대로'))]
        if valid_dongs:
            dong = valid_dongs[-1]

    # 3) 시·군·구 매핑
    if sido == "서울특별시":
        city = "서울특별시"
        gu = tokens[1] if len(tokens) > 1 else ""
    elif sido in ["인천광역시", "부산광역시", "대구광역시", "대전광역시", "울산광역시"]:
        city = sido
        gu = tokens[1] if len(tokens) > 1 else ""
    elif sido == "세종특별자치시":
        city = "세종특별자치시"
        gu = "세종특별자치시"
    elif sido == "전남광주통합특별시":
        second = tokens[1] if len(tokens) > 1 else ""
        if second.endswith("구"):
            city = "전남광주통합특별시"
            gu = second
        else:
            city = second if (second.endswith("시") or second.endswith("군")) else f"{second}시"
            gu = f"{city} 전체"
    else:
        # 경기도 및 도 단위
        second = tokens[1] if len(tokens) > 1 else ""
        city = second if (second.endswith("시") or second.endswith("군")) else f"{second}시"
        gu = f"{city} 전체"
        if len(tokens) >= 3 and tokens[2].endswith("구"):
            gu = tokens[2]

    return sido, city, gu, dong


# ── 2. 청약홈 API 호출 파이프라인 (2020~2030년 분양 수집) ─────────
def fetch_applyhome_api(api_key: str):
    records = []
    page = 1
    per_page = 100

    print("📡 한국부동산원 청약홈 API로부터 최신 분양 단지 수집 시작...")

    while True:
        params = {
            "page": page,
            "perPage": per_page,
            "serviceKey": api_key
        }

        try:
            res = requests.get(API_URL, params=params, timeout=15)
        except Exception as e:
            print(f"API 요청 실패: {e}")
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

            if len(mvn_ym) >= 6:
                try:
                    s_year = int(mvn_ym[:4])
                    s_month = f"{mvn_ym[:4]}-{mvn_ym[4:6]}"
                except ValueError:
                    continue

                # 2020년 이후 입주 예정 단지 수집
                if 2020 <= s_year <= 2032:
                    sido, city, gu, dong = parse_korean_address_robust(addr)
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
        if len(items) < per_page or page >= 300:
            break
        page += 1

    print(f"청약홈 API에서 총 {len(records)}개의 유효 단지를 수집했습니다.")
    return records


# ── 3. 하이브리드 시드 병합 및 CSV 저장 ───────────────────────
def update_csv():
    api_key = os.environ.get("DATA_GO_KR_SERVICE_KEY")

    # 1) 기존 supply_data.csv 로드 (2015~2019년 전국 확정 데이터 보존)
    if os.path.exists(CSV_PATH):
        try:
            df_existing = pd.read_csv(CSV_PATH)
            print(f"기존 CSV 로드 성공: {len(df_existing)}개 레코드 보존 중")
        except Exception:
            df_existing = pd.DataFrame(columns=COLUMNS)
    else:
        df_existing = pd.DataFrame(columns=COLUMNS)

    # 2) 청약홈 최신 API 데이터 호출 (2020~2030년)
    api_records = fetch_applyhome_api(api_key) if api_key else []
    df_api = pd.DataFrame(api_records) if api_records else pd.DataFrame(columns=COLUMNS)

    # 3) 기존 과거 데이터 + API 신규 데이터 병합
    combined = pd.concat([df_existing, df_api], ignore_index=True)

    # 유효 컬럼 보정
    for col in COLUMNS:
        if col not in combined.columns:
            combined[col] = ""
    combined = combined[COLUMNS]

    # 결측치 및 세대수 타입 정제
    combined['supply_year'] = pd.to_numeric(combined['supply_year'], errors='coerce').fillna(0).astype(int)
    combined['households'] = pd.to_numeric(combined['households'], errors='coerce').fillna(0).astype(int)
    combined = combined[(combined['supply_year'] >= 2015) & (combined['households'] > 0)]

    # 동일 단지 중복 제거 (시군, 구, 단지명, 입주월 기준 최신 데이터 유지)
    combined.drop_duplicates(subset=["city", "gu", "apt", "supply_month"], keep="last", inplace=True)
    combined.sort_values(by=["supply_month", "households"], ascending=[False, False], inplace=True)

    # CSV 파일 덮어쓰기 저장
    combined.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"🎉 성공: {CSV_PATH} 갱신 완료 (총 {len(combined)}개 단지 적재 / 2015~2030년 전국 지원)")

if __name__ == "__main__":
    update_csv()
