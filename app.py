import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from dateutil.relativedelta import relativedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── 1. 페이지 설정 ──────────────────────────────────────
st.set_page_config(
    page_title="전국 아파트 실거래 거래량 대시보드",
    page_icon="🏢",
    layout="wide"
)

# ── 2. 행정구역 및 법정동 코드 체계 정규화 ───────────────
DECODING_KEY = 'HFLjN2wHoX4g3U2XNaBnhqTWwhmqxMqr9B2TcPbOZV9dJn8xZlFtiiymS0QNo7vbQEnk744KO+byEhW7SOucBA=='
BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

# 광역자치단체별 행정구역 구조 (도 지역: 시/군 -> 구, 특별시/광역시: 바로 구)
REGION_STRUCTURE = {
    "경기도": {
        "수원시": {"영통구": "41117", "장안구": "41111", "권선구": "41113", "팔달구": "41115"},
        "성남시": {"분당구": "41135", "수정구": "41131", "중원구": "41133"},
        "용인시": {"수지구": "41465", "기흥구": "41463", "처인구": "41461"},
        "고양시": {"일산동구": "41285", "일산서구": "41287", "덕양구": "41281"},
        "안양시": {"동안구": "41173", "만안구": "41171"},
        "안산시": {"단원구": "41273", "상록구": "41271"},
        "부천시": {"원미구": "41192", "소사구": "41194", "오정구": "41196"},
        "평택시": {"평택시": "41220"},
        "화성시": {"화성시": "41590"},
        "하남시": {"하남시": "41450"},
        "남양주시": {"남양주시": "41360"},
        "시흥시": {"시흥시": "41390"},
        "파주시": {"파주시": "41480"},
        "김포시": {"김포시": "41570"},
        "광명시": {"광명시": "41210"},
        "군포시": {"군포시": "41410"},
        "오산시": {"오산시": "41370"},
        "이천시": {"이천시": "41500"},
        "구리시": {"구리시": "41310"},
        "안성시": {"안성시": "41550"},
        "의왕시": {"의왕시": "41430"},
        "과천시": {"과천시": "41290"},
        "양주시": {"양주시": "41630"},
        "포천시": {"포천시": "41650"},
        "여주시": {"여주시": "41670"},
        "동두천시": {"동두천시": "41250"},
        "가평군": {"가평군": "41820"},
        "양평군": {"양평군": "41830"},
        "연천군": {"연천군": "41800"}
    },
    "서울특별시": {
        "강남구": "11680", "서초구": "11650", "송파구": "11710", "강동구": "11740",
        "마포구": "11440", "용산구": "11170", "성동구": "11200", "광진구": "11215",
        "영등포구": "11560", "양천구": "11470", "동작구": "11590", "관악구": "11620",
        "강서구": "11500", "구로구": "11530", "금천구": "11545", "서대문구": "11410",
        "동대문구": "11230", "성북구": "11290", "노원구": "11350", "도봉구": "11320",
        "강북구": "11305", "중랑구": "11260", "은평구": "11380", "종로구": "11110", "중구": "11140"
    },
    "인천광역시": {
        "연수구": "28185", "남동구": "28200", "서구": "28260", "부평구": "28237",
        "미추홀구": "28177", "계양구": "28245", "중구": "28110", "동구": "28140", "강화군": "28710"
    },
    "부산광역시": {
        "해운대구": "26350", "수영구": "26500", "남구": "26290", "동래구": "26260",
        "부산진구": "26230", "연제구": "26470", "금정구": "26410", "북구": "26320",
        "사하구": "26380", "강서구": "26440", "사상구": "26530", "기장군": "26710"
    },
    "대구광역시": {
        "수성구": "27260", "달서구": "27290", "중구": "27110", "동구": "27140",
        "서구": "27170", "남구": "27200", "북구": "27230", "달성군": "27710"
    },
    "대전광역시": {
        "유성구": "30200", "서구": "30170", "중구": "30140", "동구": "30110", "대덕구": "30230"
    },
    "광주광역시": {
        "광산구": "29200", "서구": "29140", "남구": "29150", "북구": "29170", "동구": "29110"
    },
    "울산광역시": {
        "남구": "31140", "중구": "31110", "북구": "31200", "동구": "31170", "울주군": "31710"
    },
    "세종특별자치시": {
        "세종특별자치시": "36110"
    }
}

# ── 3. 단일 월/구 고속 API 수집 태스크 ────────────────────
def fetch_single_month_task(lawd_cd: str, deal_ymd: str, sido: str, city: str, gu: str):
    headers = {'User-Agent': 'Mozilla/5.0'}
    task_records = []
    page = 1
    
    while True:
        params = {
            'serviceKey': DECODING_KEY,
            'LAWD_CD': lawd_cd,
            'DEAL_YMD': deal_ymd,
            'numOfRows': '1000',
            'pageNo': str(page)
        }
        try:
            res = requests.get(BASE_URL, params=params, headers=headers, timeout=10)
            if res.status_code != 200:
                break
            root = ET.fromstring(res.content)
            
            result_code = root.find('.//resultCode')
            if result_code is not None and result_code.text not in ['00', '000']:
                break

            total_tag = root.find('.//totalCount')
            total = int(total_tag.text) if total_tag is not None and total_tag.text else 0
            
            items = root.findall('.//item')
            for item in items:
                r = {child.tag: (child.text.strip() if child.text else '') for child in item}
                
                if r.get('cdealType', '') == 'O' or r.get('cdealDay', '') != '':
                    continue
                
                task_records.append({
                    'sido': sido,
                    'city': city,
                    'gu': gu,
                    'dong': r.get('umdNm', '').strip(),
                    'apt': r.get('aptNm', '').strip(),
                    'area': float(r.get('excluUseAr', 0) or 0),
                    'price': int(str(r.get('dealAmount', '0')).replace(',', '').strip() or 0),
                    'month': f"{r.get('dealYear', '')}-{str(r.get('dealMonth', '')).zfill(2)}"
                })
            
            if len(items) >= total or len(items) == 0:
                break
            page += 1
        except Exception:
            break

    return task_records


# ── 4. 병렬 수집 및 캐싱 (광역 전체 지원) ─────────────────
@st.cache_data(ttl=86400)
def fetch_target_records(target_list_tuples):
    now = datetime.now()
    target_months = [(now - relativedelta(months=i)).strftime('%Y%m') for i in range(5, -1, -1)]

    tasks = []
    for code, sido, city, gu in target_list_tuples:
        for deal_ymd in target_months:
            tasks.append((code, deal_ymd, sido, city, gu))

    all_records = []
    # 광역 전체 조회를 위해 워커 수 20개로 확대
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_single_month_task, *task) for task in tasks]
        for future in as_completed(futures):
            try:
                res = future.result()
                if res:
                    all_records.extend(res)
            except Exception:
                pass

    return pd.DataFrame(all_records)


# ── 5. UI 및 동적 계층형 필터 ───────────────────────────
st.title("📊 전국 동네별 아파트 실거래 거래량 대시보드")
st.caption("국토교통부 실거래가 오픈 API 실시간 연동 (병렬 고속 수집 & 24시간 캐싱)")

col1, col2, col3, col4 = st.columns(4)

# [1] 시·도 선택
with col1:
    sido_list = list(REGION_STRUCTURE.keys())
    selected_sido = st.selectbox("1️⃣ 시·도", sido_list, index=sido_list.index("경기도") if "경기도" in sido_list else 0)

sido_data = REGION_STRUCTURE[selected_sido]
target_codes_to_fetch = []

# 도(Province) 단위인 경우 (경기도 등): 4단계 계층
if selected_sido == "경기도":
    with col2:
        city_options = ["경기도 전체"] + list(sido_data.keys())
        selected_city = st.selectbox("2️⃣ 시·군", city_options, index=1)  # 기본: 수원시

    if selected_city == "경기도 전체":
        with col3:
            selected_gu = st.selectbox("3️⃣ 구", ["전체"])
        # 경기도 전역 주요 시·구 전체 큐 생성
        for c_name, gu_dict in sido_data.items():
            for g_name, code in gu_dict.items():
                target_codes_to_fetch.append((code, selected_sido, c_name, g_name))
    else:
        gu_dict = sido_data[selected_city]
        gu_keys = list(gu_dict.keys())
        with col3:
            if len(gu_keys) > 1:
                gu_options = [f"{selected_city} 전체"] + gu_keys
            else:
                gu_options = gu_keys
            selected_gu = st.selectbox("3️⃣ 구", gu_options)

        if selected_gu == f"{selected_city} 전체":
            for g_name, code in gu_dict.items():
                target_codes_to_fetch.append((code, selected_sido, selected_city, g_name))
        else:
            code = gu_dict[selected_gu]
            target_codes_to_fetch.append((code, selected_sido, selected_city, selected_gu))

# 특별시/광역시/특별자치시인 경우 (서울, 인천, 부산 등): 3단계 직접 계층
else:
    with col2:
        gu_options = [f"{selected_sido} 전체"] + list(sido_data.keys())
        selected_gu_direct = st.selectbox("2️⃣ 구·군", gu_options)

    with col3:
        # 광역시는 3번째 필터 불필요 (비활성화 표시)
        st.selectbox("3️⃣ 상세 구", ["-"], disabled=True)

    if selected_gu_direct == f"{selected_sido} 전체":
        for g_name, code in sido_data.items():
            target_codes_to_fetch.append((code, selected_sido, selected_sido, g_name))
    else:
        code = sido_data[selected_gu_direct]
        target_codes_to_fetch.append((code, selected_sido, selected_sido, selected_gu_direct))

# 데이터 수집 진행
scope_name = selected_city if selected_sido == "경기도" else selected_gu_direct
with st.spinner(f"'{selected_sido} {scope_name}' 실거래 데이터를 고속 수집 중입니다..."):
    df = fetch_target_records(tuple(target_codes_to_fetch))

# [4] 읍·면·동 선택
with col4:
    if not df.empty:
        dong_list = ['전체 보기'] + sorted(list(df['dong'].unique()))
    else:
        dong_list = ['전체 보기']
    selected_dong = st.selectbox("4️⃣ 읍·면·동", dong_list)

if df.empty:
    st.warning("선택하신 지역의 최근 6개월 거래 내역이 없거나 데이터를 불러올 수 없습니다.")
    st.stop()

view_df = df if selected_dong == '전체 보기' else df[df['dong'] == selected_dong]

# ── 6. 상단 요약 메트릭 카드 ─────────────────────────────
# 동별 집계 (지역명이 겹치지 않도록 구+동 매핑)
df['full_loc'] = df['city'] + " " + df['gu'] + " " + df['dong']
loc_counts = df['full_loc'].value_counts()

top_loc_str = loc_counts.index[0] if not loc_counts.empty else '-'
top_val = loc_counts.iloc[0] if not loc_counts.empty else 0
top_pct = (top_val / len(df) * 100) if len(df) > 0 else 0

m1, m2, m3 = st.columns(3)
m1.metric("🔥 최다 거래 지역 (1위)", f"{top_loc_str}", f"{top_val:,}건 ({top_pct:.1f}%)")
m2.metric("📦 선택 구역 총 거래량", f"{len(view_df):,}건")
m3.metric("🏢 집계 대상 동 개수", f"{len(df['dong'].unique()):,}개 동")

st.divider()

# ── 7. 월별 거래량 추이 차트 및 순위표 ───────────────────
c1, c2 = st.columns([3, 2])

display_title = f"{selected_sido} {scope_name}"
if selected_dong != '전체 보기':
    display_title += f" {selected_dong}"

with c1:
    st.subheader(f"📈 {display_title} 월별 거래량 추이")
    monthly_series = view_df['month'].value_counts().sort_index()
    st.bar_chart(monthly_series)

with c2:
    st.subheader(f"🥇 {scope_name} 동별 거래량 순위")
    rank_df = df.groupby(['city', 'gu', 'dong']).size().reset_index(name='거래건수')
    rank_df = rank_df.sort_values(by='거래건수', ascending=False)
    rank_df.columns = ['시·군', '구', '동명', '거래건수']
    rank_df.index = range(1, len(rank_df) + 1)
    st.dataframe(rank_df, use_container_width=True, height=290)

st.divider()

# ── 8. 주요 아파트 단지 순위 (TOP 10) ─────────────────
st.subheader(f"🏆 {display_title} 주요 아파트 단지 순위 (TOP 10)")
apt_rank = view_df.groupby(['city', 'gu', 'dong', 'apt']).agg(
    거래건수=('price', 'count'),
    평균거래가_만원=('price', 'mean'),
    최고가_만원=('price', 'max')
).reset_index()

apt_rank = apt_rank.sort_values(by='거래건수', ascending=False).head(10)
apt_rank['평균거래가_만원'] = apt_rank['평균거래가_만원'].astype(int).apply(lambda x: f"{x:,}")
apt_rank['최고가_만원'] = apt_rank['최고가_만원'].apply(lambda x: f"{x:,}")
apt_rank.columns = ['시·군', '구', '법정동', '단지명', '거래건수', '평균 거래가(만원)', '최고 거래가(만원)']
apt_rank.index = range(1, len(apt_rank) + 1)

st.dataframe(apt_rank, use_container_width=True)
