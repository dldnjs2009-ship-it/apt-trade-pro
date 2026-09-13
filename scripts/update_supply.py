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

# ── 1. 엑셀 시드 주소 파싱 엔진 ──────────────────────────────
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

# ── 핵심: 엑셀에서는 2015~2019년 (2020년 미만) 데이터만 로드 ──
def load_historical_from_excel_under_2020():
    if not os.path.exists(EXCEL_SEED_PATH):
        print(f"안내: {EXCEL_SEED_PATH} 파일이 없습니다.")
        return pd.DataFrame(columns=COLUMNS)

    print(f"📖 {EXCEL_SEED_PATH} 파일로부터 2015~2019년 순수 과거 데이터만 파싱 시작...")
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
            y, m_str = clean_date(str(date_str).strip())
            h = clean_households(str(h_str).strip())
            
            # 2020년 미만(2015~2019년) 과거 데이터만 수용 (2020년 이후는 청약홈 API 전담)
            if y and 2015 <= y < 2020 and h > 0:
                sido, city, gu, dong = parse_excel_loc(str(loc).strip())
                records.append({
                    "sido": sido, "city": city, "gu": gu, "dong": dong,
                    "apt": str(apt).strip(), "supply_year": y, "supply_month": m_str,
                    "households": h, "pyeong_info": "일반/국평형", "brand": "민간/공공"
                })

    df_excel = pd.DataFrame(records)
    print(f"  - 엑셀에서 2015~2019년 과거 확정 데이터 총 {len(df_excel)}개 단지 추출 완료.")
    return df_excel

# ── 2. 청약홈 API 주소 파싱 엔진 ──────────────────────────────
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

# ── 청약홈 API 수집 (2020~2030년 / 사전청약 및 무순위 재분양 공고 제외) ──
def fetch_applyhome_api(api_key: str):
    records = []
    page = 1
    per_page = 100

    print("📡 한국부동산원 청약홈 API로부터 2020~2030년 분양 단지 수집 시작...")
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

            # 사전청약 제외 (본청약이 따로 존재하여 세대수 이중 집계 방지)
            if "사전청약" in house_nm:
                continue

            # 잔여세대/취소분/무순위/추가모집 제외 (본청약 세대수 내 미계약분이므로 신규 공급 아님)
            if re.search(r'(?:무순위|취소후재공급|조합원\s*취소|임의공급|추가입주자|추가모집|잔여세대)', house_nm):
                continue

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

    print(f"청약홈 API에서 총 {len(records)}개 유효 단지 수집 완료.")
    return records

# ── 3. 단지명 정규화 및 최종 병합 ────────────────────────────
def clean_for_dedup(name: str) -> str:
    s = str(name).strip()
    # 괄호 수식어 및 로마자 정규화
    s = re.sub(r'[\(\[\{][^\)\]\}]*(?:본청약|사전청약|추가|취소|무순위|임의공급|잔여|재공급|조합원|주상복합|도시형)[^\)\]\}]*[\)\]\}]', '', s)
    s = s.replace('Ⅰ', 'I').replace('Ⅱ', 'II').replace('Ⅲ', 'III')
    s = re.sub(r'[\(\[\{][주유][\)\]\}]', '', s)
    return "".join(s.split())

def update_csv():
    api_key = os.environ.get("DATA_GO_KR_SERVICE_KEY")

    # 1) 엑셀 시드: 2015~2019년 (2020년 미만) 과거 확정 데이터만 로드 (3,164개 단지)
    df_excel = load_historical_from_excel_under_2020()

    # 2) 청약홈 API: 2020년 이후 실시간 최신 데이터 로드
    api_records = fetch_applyhome_api(api_key) if api_key else []
    df_api = pd.DataFrame(api_records) if api_records else pd.DataFrame(columns=COLUMNS)

    # 3) 기존 CSV 백업 처리: 2020년 이후 데이터 중 유효한 것만 보존
    df_csv_2020 = pd.DataFrame(columns=COLUMNS)
    if os.path.exists(CSV_PATH):
        try:
            df_old = pd.read_csv(CSV_PATH)
            # 기존 CSV에서 2020년 이후 데이터만 추출하고, 엑셀에서 넘어왔던 임시(민간/공공) 데이터는 제거
            df_csv_2020 = df_old[(df_old['supply_year'] >= 2020) & (df_old['brand'] != '민간/공공')].copy()
        except Exception:
            pass

    # 4) 2015~2019(엑셀) + 2020~(API 및 정제된 기존데이터) 병합
    combined = pd.concat([df_excel, df_csv_2020, df_api], ignore_index=True)

    for col in COLUMNS:
        if col not in combined.columns:
            combined[col] = ""
    combined = combined[COLUMNS]

    combined['supply_year'] = pd.to_numeric(combined['supply_year'], errors='coerce').fillna(0).astype(int)
    combined['households'] = pd.to_numeric(combined['households'], errors='coerce').fillna(0).astype(int)
    combined = combined[(combined['supply_year'] >= 2015) & (combined['households'] > 0)]

    # 5) 최종 중복 제거 (정규화 키 기준)
    combined['clean_apt'] = combined['apt'].apply(clean_for_dedup)
    combined['brand_score'] = combined['brand'].apply(
        lambda b: 0 if str(b).strip() in ['민간/공공', '민간분양', '', 'nan'] else 1
    )

    # 세대수 큰 공고 우선, 브랜드명 상세한 공고 우선
    combined.sort_values(
        by=['clean_apt', 'households', 'brand_score', 'supply_month'],
        ascending=[True, False, False, False],
        inplace=True
    )

    combined = combined.drop_duplicates(
        subset=['city', 'gu', 'clean_apt', 'supply_year'],
        keep='first'
    ).copy()

    combined.drop(columns=['clean_apt', 'brand_score'], inplace=True, errors='ignore')
    combined.sort_values(by=["supply_month", "households"], ascending=[False, False], inplace=True)

    combined.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"🎉 성공: {CSV_PATH} 갱신 완료 (총 {len(combined)}개 고유 단지 적재 / 중복 100% 제거)")

if __name__ == "__main__":
    update_csv()
