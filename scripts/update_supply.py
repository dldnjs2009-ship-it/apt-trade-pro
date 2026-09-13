import os
import re
import requests
import pandas as pd

EXCEL_SEED_PATH = "전국과거분양자료.xlsx"
CSV_PATH = "supply_data.csv"
API_URL = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail"

COLUMNS = ["sido", "city", "gu", "dong", "apt", "supply_year", "supply_month", "households", "pyeong_info", "brand"]

GYEONGGI_CITIES = [
    "수원시", "성남시", "용인시", "화성시", "고양시", "안양시", "부천시", "안산시",
    "평택시", "남양주시", "하남시", "시흥시", "파주시", "김포시", "광명시", "광주시",
    "군포시", "오산시", "이천시", "구리시", "안성시", "의왕시", "과천시", "양주시",
    "포천시", "여주시", "동두천시", "가평군", "양평군", "연천군", "의정부시"
]

def clean_date(d_str):
    m = re.search(r'(\d{4})년\s*(\d{1,2})월', str(d_str))
    if m:
        y = int(m.group(1))
        m_num = int(m.group(2))
        return y, f"{y}-{m_num:02d}"
    return None, None

def clean_households(h_str):
    m = re.search(r'([\d,]+)세대', str(h_str))
    if m:
        return int(m.group(1).replace(',', ''))
    return 0

# ── 1. 엑셀 과거 시드 주소 파싱 엔진 ────────────────────────
def resolve_gyeonggi(tokens):
    sido = "경기도"
    second = tokens[1] if len(tokens) > 1 else ""
    city = None
    gu = None
    dong = "기타"

    for c in GYEONGGI_CITIES:
        stem = c.replace("시", "").replace("군", "")
        if second.startswith(stem):
            city = c
            break
    if not city:
        city = second if second.endswith("시") or second.endswith("군") else f"{second}시"

    for t in tokens[2:]:
        if t.endswith("구"):
            gu = t
        elif t.endswith("동") or t.endswith("읍") or t.endswith("면") or t.endswith("리"):
            dong = t

    if not gu:
        gu = f"{city} 전체"

    return sido, city, gu, dong

def parse_excel_loc(loc_str):
    tokens = loc_str.split()
    if not tokens:
        return "기타", "기타", "기타", "기타"

    p = tokens[0]

    if p == "서울":
        return "서울특별시", "서울특별시", tokens[1] if len(tokens) > 1 else "", tokens[2] if len(tokens) > 2 else "기타"

    metro_map = {
        "인천": "인천광역시", "부산": "부산광역시", "대구": "대구광역시",
        "대전": "대전광역시", "울산": "울산광역시"
    }
    if p in metro_map:
        return metro_map[p], metro_map[p], tokens[1] if len(tokens) > 1 else "", tokens[2] if len(tokens) > 2 else "기타"

    if p == "세종":
        return "세종특별자치시", "세종특별자치시", "세종특별자치시", tokens[2] if len(tokens) > 2 else (tokens[1] if len(tokens) > 1 else "기타")

    if p == "전남광주":
        second = tokens[1] if len(tokens) > 1 else ""
        if second.endswith("구"):
            return "전남광주통합특별시", "전남광주통합특별시", second, tokens[2] if len(tokens) > 2 else "기타"
        else:
            city = second if second.endswith("시") or second.endswith("군") else f"{second}시"
            return "전남광주통합특별시", city, f"{city} 전체", tokens[2] if len(tokens) > 2 else "기타"

    if p == "경기":
        return resolve_gyeonggi(tokens)

    prov_map = {
        "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
        "전북": "전북특별자치도", "경북": "경상북도", "경남": "경상남도", "제주": "제주특별자치도"
    }
    sido = prov_map.get(p, p)
    second = tokens[1] if len(tokens) > 1 else ""
    city = second if second.endswith("시") or second.endswith("군") else f"{second}시"

    gu = None
    dong = "기타"
    for t in tokens[2:]:
        if t.endswith("구"):
            gu = t
        elif t.endswith("동") or t.endswith("읍") or t.endswith("면") or t.endswith("리"):
            dong = t
    if not gu:
        gu = f"{city} 전체"

    return sido, city, gu, dong

def load_historical_from_excel():
    if not os.path.exists(EXCEL_SEED_PATH):
        print(f"안내: {EXCEL_SEED_PATH} 파일이 없어 엑셀 시드 로드를 건너뜁니다.")
        return pd.DataFrame(columns=COLUMNS)

    print(f"📖 {EXCEL_SEED_PATH} 파일로부터 전국 과거 입주 단지 파싱 시작...")
    df_full = pd.read_excel(EXCEL_SEED_PATH, sheet_name=0, header=None)
    records = []

    for start_col in range(3, 67, 4):
        sub = df_full.iloc[7:, start_col:start_col+4].dropna(how='all')
        for idx, row in sub.iterrows():
            loc = row.iloc[0]
            apt = row.iloc[1]
            date_str = row.iloc[2]
            h_str = row.iloc[3]
            if pd.isna(loc) or pd.isna(apt) or pd.isna(date_str):
                continue
            sido, city, gu, dong = parse_excel_loc(str(loc).strip())
            y, m_str = clean_date(str(date_str).strip())
            h = clean_households(str(h_str).strip())
            if y and h > 0:
                records.append({
                    "sido": sido, "city": city, "gu": gu, "dong": dong,
                    "apt": str(apt).strip(), "supply_year": y, "supply_month": m_str,
                    "households": h, "pyeong_info": "일반/국평형", "brand": "민간/공공"
                })

    df_excel = pd.DataFrame(records)
    print(f"  - 엑셀에서 총 {len(df_excel)}개 단지 추출 완료.")
    return df_excel

# ── 2. 청약홈 API 호출 주소 파싱 엔진 (도로명 버그 차단) ─────────
def parse_api_address(addr: str):
    if not addr or not isinstance(addr, str):
        return None, None, None, None

    tokens = addr.strip().split()
    if len(tokens) < 2:
        return None, None, None, None

    sido_raw = tokens[0]
    sido_map = {
        "서울": "서울특별시", "서울특별시": "서울특별시", "경기": "경기도", "경기도": "경기도",
        "인천": "인천광역시", "인천광역시": "인천광역시", "부산": "부산광역시", "부산광역시": "부산광역시",
        "대구": "대구광역시", "대구광역시": "대구광역시", "대전": "대전광역시", "대전광역시": "대전광역시",
        "광주": "전남광주통합특별시", "전남": "전남광주통합특별시", "전남광주": "전남광주통합특별시",
        "울산": "울산광역시", "울산광역시": "울산광역시", "세종": "세종특별자치시", "세종특별자치시": "세종특별자치시",
        "강원": "강원특별자치도", "강원특별자치도": "강원특별자치도", "충북": "충청북도", "충청북도": "충청북도",
        "충남": "충청남도", "충남": "충청남도", "전북": "전북특별자치도", "전북특별자치도": "전북특별자치도",
        "경북": "경상북도", "경남": "경상남도", "제주": "제주특별자치도"
    }
    sido = sido_map.get(sido_raw, sido_raw)

    dong = "기타"
    paren_match = re.search(r'\(([가-힣0-9]+(?:동|읍|면|리|가))\)', addr)
    if paren_match:
        dong = paren_match.group(1)
    else:
        dong_candidates = re.findall(r'([가-힣0-9]+(?:동|읍|면|리|가))(?=[\s\d,\)]|$)', addr)
        valid_dongs = [d for d in dong_candidates if not (d.endswith('로') or d.endswith('길') or d.endswith('대로'))]
        if valid_dongs:
            dong = valid_dongs[-1]

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
        second = tokens[1] if len(tokens) > 1 else ""
        city = second if (second.endswith("시") or second.endswith("군")) else f"{second}시"
        gu = f"{city} 전체"
        if len(tokens) >= 3 and tokens[2].endswith("구"):
            gu = tokens[2]

    return sido, city, gu, dong

def fetch_applyhome_api(api_key: str):
    records = []
    page = 1
    per_page = 100

    print("📡 한국부동산원 청약홈 API로부터 최신 분양 단지 수집 시작...")
    while True:
        params = {"page": page, "perPage": per_page, "serviceKey": api_key}
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

                if 2020 <= s_year <= 2032:
                    sido, city, gu, dong = parse_api_address(addr)
                    if sido and city:
                        try:
                            h_count = int(tot_hshld)
                        except (ValueError, TypeError):
                            h_count = 0

                        if h_count > 0:
                            records.append({
                                "sido": sido, "city": city, "gu": gu, "dong": dong,
                                "apt": house_nm, "supply_year": s_year, "supply_month": s_month,
                                "households": h_count, "pyeong_info": "일반/국평형", "brand": brand
                            })

        print(f"  - {page}페이지 수집 완료 ({len(items)}건 조회)")
        if len(items) < per_page or page >= 300:
            break
        page += 1

    print(f"청약홈 API에서 총 {len(records)}개 단지 수집 완료.")
    return records

# ── 3. 3중 통합 병합 및 CSV 자동 생성 ────────────────────────
def update_csv():
    api_key = os.environ.get("DATA_GO_KR_SERVICE_KEY")

    # 1) 엑셀 시드(2015~2024년 전국 5,757개 단지) 로드
    df_excel = load_historical_from_excel()

    # 2) 기존 CSV가 존재하면 로드
    df_csv = pd.DataFrame(columns=COLUMNS)
    if os.path.exists(CSV_PATH):
        try:
            df_csv = pd.read_csv(CSV_PATH)
        except Exception:
            pass

    # 3) 청약홈 API 호출 (최신 미래 분양 단지)
    api_records = fetch_applyhome_api(api_key) if api_key else []
    df_api = pd.DataFrame(api_records) if api_records else pd.DataFrame(columns=COLUMNS)

    # 4) [엑셀 시드 + 기존 CSV + 청약홈 API] 3중 병합
    combined = pd.concat([df_excel, df_csv, df_api], ignore_index=True)

    for col in COLUMNS:
        if col not in combined.columns:
            combined[col] = ""
    combined = combined[COLUMNS]

    combined['supply_year'] = pd.to_numeric(combined['supply_year'], errors='coerce').fillna(0).astype(int)
    combined['households'] = pd.to_numeric(combined['households'], errors='coerce').fillna(0).astype(int)
    combined = combined[(combined['supply_year'] >= 2015) & (combined['households'] > 0)]

    # 중복 제거 (시군, 구, 단지명, 입주월 기준)
    combined.drop_duplicates(subset=["city", "gu", "apt", "supply_month"], keep="last", inplace=True)
    combined.sort_values(by=["supply_month", "households"], ascending=[False, False], inplace=True)

    # supply_data.csv 자동 생성 및 저장
    combined.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"🎉 성공: {CSV_PATH} 자동 생성 및 갱신 완료 (총 {len(combined)}개 단지 적재 / 2015~2030년 전국 지원)")

if __name__ == "__main__":
    update_csv()
