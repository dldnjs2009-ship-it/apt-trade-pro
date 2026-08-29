import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── 1. 페이지 기본 설정 ──────────────────────────────────
st.set_page_config(
    page_title="전국 아파트 실거래가 및 내집마련 대시보드",
    page_icon="🏠",
    layout="wide"
)

# ── 2. 기본 상수 및 행정구역 매핑 ───────────────────────
DECODING_KEY = 'HFLjN2wHoX4g3U2XNaBnhqTWwhmqxMqr9B2TcPbOZV9dJn8xZlFtiiymS0QNo7vbQEnk744KO+byEhW7SOucBA=='
ENCODING_KEY = urllib.parse.quote(DECODING_KEY)
BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

# 동탄구(동탄 1·2신도시) 소속 법정동 전수 목록
DONGTAN_DONGS = [
    '반송동', '석우동', '능동', '청계동', '영천동',
    '오산동', '신동', '목동', '산척동', '장지동',
    '송동', '중동', '방교동', '금곡동'
]

REGION_STRUCTURE = {
    "경기도": {
        "화성시": {
            "화성시 전체": "41590",
            "동탄구 (동탄 1·2신도시)": "41590",
            "비동탄권 (봉담·향남·남양 등)": "41590"
        },
        "수원시": {"영통구": "41117", "장안구": "41111", "권선구": "41113", "팔달구": "41115"},
        "성남시": {"분당구": "41135", "수정구": "41131", "중원구": "41133"},
        "용인시": {"수지구": "41465", "기흥구": "41463", "처인구": "41461"},
        "고양시": {"일산동구": "41285", "일산서구": "41287", "덕양구": "41281"},
        "평택시": {"평택시 전체": "41220"},
        "안양시": {"동안구": "41173", "만안구": "41171"},
        "안산시": {"단원구": "41273", "상록구": "41271"},
        "부천시": {"원미구": "41192", "소사구": "41194", "오정구": "41196"},
        "남양주시": {"남양주시 전체": "41360"},
        "하남시": {"하남시 전체": "41450"},
        "시흥시": {"시흥시 전체": "41390"},
        "파주시": {"파주시 전체": "41480"},
        "김포시": {"김포시 전체": "41570"},
        "광명시": {"광명시 전체": "41210"},
        "군포시": {"군포시 전체": "41410"},
        "오산시": {"오산시 전체": "41370"},
        "이천시": {"이천시 전체": "41500"},
        "구리시": {"구리시 전체": "41310"},
        "안성시": {"안성시 전체": "41550"},
        "의왕시": {"의왕시 전체": "41430"},
        "과천시": {"과천시 전체": "41290"},
        "양주시": {"양주시 전체": "41630"},
        "포천시": {"포천시 전체": "41650"},
        "여주시": {"여주시 전체": "41670"},
        "동두천시": {"동두천시 전체": "41250"},
        "가평군": {"가평군 전체": "41820"},
        "양평군": {"양평군 전체": "41830"},
        "연천군": {"연천군 전체": "41800"}
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

# ── 3. 단일 월 고속 API 수집 태스크 (2중 폴백 및 재시도) ────
def fetch_single_month_task(lawd_cd: str, deal_ymd: str, sido: str, city: str, gu: str):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/xml'
    }
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
        
        res = None
        # 1차: params 방식 호출
        try:
            res = requests.get(BASE_URL, params=params, headers=headers, timeout=20)
        except Exception:
            pass
            
        # 2차: URL 직접 결합 방식(Encoding 키) 폴백
        if res is None or res.status_code != 200 or '<item>' not in res.text:
            fallback_url = f"{BASE_URL}?serviceKey={ENCODING_KEY}&LAWD_CD={lawd_cd}&DEAL_YMD={deal_ymd}&numOfRows=1000&pageNo={page}"
            try:
                res = requests.get(fallback_url, headers=headers, timeout=20)
            except Exception:
                break

        if res is None or res.status_code != 200:
            break
            
        try:
            root = ET.fromstring(res.content)
        except Exception:
            break
            
        result_code = root.find('.//resultCode')
        if result_code is not None and result_code.text not in ['00', '000']:
            break

        total_tag = root.find('.//totalCount')
        total = int(total_tag.text) if total_tag is not None and total_tag.text else 0
        
        items = root.findall('.//item')
        if not items:
            break
            
        for item in items:
            r = {child.tag: (child.text.strip() if child.text else '') for child in item}
            if r.get('cdealType', '') == 'O' or r.get('cdealDay', '') != '':
                continue
            
            raw_dong = r.get('umdNm', '').strip()
            # 읍·면 지역(예: "봉담읍 동화리")인 경우 읍·면 또는 동 단위 분리
            if not raw_dong:
                raw_dong = r.get('aptDong', '').strip() or '기타'
            else:
                # "봉담읍 와우리" 형태에서 읍·면 단위로 통일하거나 세부동 유지
                parts = raw_dong.split()
                if len(parts) > 1 and parts[0].endswith(('읍', '면')):
                    raw_dong = parts[0]  # 봉담읍, 향남읍 등으로 그룹화
                
            task_records.append({
                'sido': sido,
                'city': city,
                'gu': gu,
                'dong': raw_dong,
                'apt': r.get('aptNm', '').strip(),
                'area': float(r.get('excluUseAr', 0) or 0),
                'price': int(str(r.get('dealAmount', '0')).replace(',', '').strip() or 0),
                'month': f"{r.get('dealYear', '')}-{str(r.get('dealMonth', '')).zfill(2)}"
            })
        
        if len(items) >= total or len(task_records) >= total:
            break
        page += 1

    return task_records


# 데이터가 있을 때만 캐시를 유지하는 함수
@st.cache_data(ttl=86400)
def fetch_target_records(target_list_tuples, target_months_tuple):
    tasks = []
    seen_calls = set()
    for code, sido, city, gu in target_list_tuples:
        for deal_ymd in target_months_tuple:
            call_key = (code, deal_ymd)
            if call_key not in seen_calls:
                seen_calls.add(call_key)
                tasks.append((code, deal_ymd, sido, city, gu))

    all_records = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(fetch_single_month_task, *task) for task in tasks]
        for future in as_completed(futures):
            try:
                res = future.result()
                if res:
                    all_records.extend(res)
            except Exception:
                pass

    return pd.DataFrame(all_records)


# ── 4. 사이드바 설정 및 예산 계산기 ────────────────────────
st.sidebar.header("⚙️ 데이터 및 예산 설정")

# [1] 캐시 강제 초기화 버튼 (데이터 안 뜰 때 즉시 해결)
if st.sidebar.button("🔄 캐시 초기화 및 데이터 다시 불러오기"):
    st.cache_data.clear()
    st.rerun()

# [2] 조회 기간 선택
period_option = st.sidebar.selectbox(
    "📅 조회 기간 선택",
    ["최근 6개월 (실시간)", "최근 12개월 (1년)", "2024년 전체"],
    index=0
)

now = datetime.now()
if period_option == "최근 6개월 (실시간)":
    target_months = [(now - relativedelta(months=i)).strftime('%Y%m') for i in range(5, -1, -1)]
elif period_option == "최근 12개월 (1년)":
    target_months = [(now - relativedelta(months=i)).strftime('%Y%m') for i in range(11, -1, -1)]
else:
    target_months = [f"2024{m:02d}" for m in range(1, 13)]

st.sidebar.markdown("---")
st.sidebar.subheader("💰 내 자본금 맞춤 계산기")

my_capital = st.sidebar.number_input(
    "내 보유 현금/자본금 (만원)",
    min_value=1000,
    max_value=500000,
    value=30000,
    step=1000,
    help="부동산 매수에 투입 가능한 순수 자기자본입니다."
)

ltv_rate = st.sidebar.slider("희망 대출 비율 (LTV %)", min_value=0, max_value=80, value=70, step=5)
loan_interest = st.sidebar.slider("대출 예상 금리 (%)", min_value=2.0, max_value=8.0, value=4.0, step=0.1)
loan_term_years = st.sidebar.selectbox("대출 만기 (년)", [10, 20, 30, 40], index=2)

effective_capital = my_capital * 0.97

if ltv_rate < 100:
    max_affordable_price = int(effective_capital / (1 - (ltv_rate / 100)))
else:
    max_affordable_price = int(effective_capital * 2)

max_loan_amount = max_affordable_price - my_capital
if max_loan_amount > 0:
    monthly_rate = (loan_interest / 100) / 12
    total_months = loan_term_years * 12
    monthly_payment = int(
        (max_loan_amount * 10000 * monthly_rate * ((1 + monthly_rate) ** total_months))
        / (((1 + monthly_rate) ** total_months) - 1)
    )
else:
    monthly_payment = 0

st.sidebar.markdown("---")
st.sidebar.subheader("📋 내 예산 분석 결과")
st.sidebar.write(f"• **최대 매수 가능가:** **{max_affordable_price // 10000}억 {(max_affordable_price % 10000):,}만원**")
st.sidebar.write(f"• **필요 대출금액:** {max_loan_amount // 10000}억 {(max_loan_amount % 10000):,}만원")
st.sidebar.write(f"• **월 예상 원리금:** **{monthly_payment // 10000:,}만원** / 월")

filter_by_budget = st.sidebar.checkbox("🎯 내 예산 이하 단지만 필터링", value=True)


# ── 5. 메인 UI 및 계층형 지역 필터 ────────────────────────
st.title("📊 전국 아파트 실거래가 및 내집마련 대시보드")
st.caption("국토교통부 실거래가 오픈 API 실시간 연동 (화성시 동탄구 분리 및 내집마련 추천)")

col1, col2, col3, col4 = st.columns(4)

with col1:
    sido_list = list(REGION_STRUCTURE.keys())
    selected_sido = st.selectbox("1️⃣ 시·도", sido_list, index=sido_list.index("경기도") if "경기도" in sido_list else 0)

sido_data = REGION_STRUCTURE[selected_sido]
target_codes_to_fetch = []

if selected_sido == "경기도":
    with col2:
        city_options = ["경기도 전체"] + list(sido_data.keys())
        default_city_idx = city_options.index("화성시") if "화성시" in city_options else 1
        selected_city = st.selectbox("2️⃣ 시·군", city_options, index=default_city_idx)

    if selected_city == "경기도 전체":
        with col3:
            selected_gu = st.selectbox("3️⃣ 구·권역", ["전체"])
        for c_name, gu_dict in sido_data.items():
            for g_name, code in gu_dict.items():
                target_codes_to_fetch.append((code, selected_sido, c_name, g_name))
    else:
        gu_dict = sido_data[selected_city]
        gu_keys = list(gu_dict.keys())
        with col3:
            gu_options = gu_keys
            selected_gu = st.selectbox("3️⃣ 구·권역", gu_options)

        if selected_gu == f"{selected_city} 전체":
            for g_name, code in gu_dict.items():
                target_codes_to_fetch.append((code, selected_sido, selected_city, g_name))
        else:
            code = gu_dict[selected_gu]
            target_codes_to_fetch.append((code, selected_sido, selected_city, selected_gu))
else:
    with col2:
        gu_options = [f"{selected_sido} 전체"] + list(sido_data.keys())
        selected_gu_direct = st.selectbox("2️⃣ 구·군", gu_options)
    with col3:
        st.selectbox("3️⃣ 구·권역", ["-"], disabled=True)

    if selected_gu_direct == f"{selected_sido} 전체":
        for g_name, code in sido_data.items():
            target_codes_to_fetch.append((code, selected_sido, selected_sido, g_name))
    else:
        code = sido_data[selected_gu_direct]
        target_codes_to_fetch.append((code, selected_sido, selected_sido, selected_gu_direct))

scope_name = selected_city if selected_sido == "경기도" else selected_gu_direct

with st.spinner(f"'{selected_sido} {scope_name}' 실거래 데이터를 국토부 API에서 수집 중입니다..."):
    df = fetch_target_records(tuple(target_codes_to_fetch), tuple(target_months))

# 만약 빈 데이터가 조회된 경우 캐시 강제 무효화
if df.empty:
    st.cache_data.clear()
    st.warning("국토교통부 API 서버 응답이 지연되어 데이터를 불러오지 못했습니다. 사이드바의 [🔄 캐시 초기화 및 다시 불러오기] 버튼을 눌러주세요.")
    st.stop()

# ── [동탄구 / 비동탄권 가상 분리 필터링] ──
if selected_city == "화성시":
    if selected_gu == "동탄구 (동탄 1·2신도시)":
        df = df[df['dong'].isin(DONGTAN_DONGS)].copy()
    elif selected_gu == "비동탄권 (봉담·향남·남양 등)":
        df = df[~df['dong'].isin(DONGTAN_DONGS)].copy()

with col4:
    dong_list = ['전체 보기'] + sorted(list(df['dong'].unique())) if not df.empty else ['전체 보기']
    selected_dong = st.selectbox("4️⃣ 읍·면·동", dong_list)

view_df = df if selected_dong == '전체 보기' else df[df['dong'] == selected_dong]

if filter_by_budget:
    affordable_df = view_df[view_df['price'] <= max_affordable_price]
else:
    affordable_df = view_df

# ── 6. 상단 요약 통계 메트릭 ──────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("💵 내 자본금 기준 최대 매수가", f"{max_affordable_price // 10000}억 {max_affordable_price % 10000:,}만원")
m2.metric("💳 필요 대출금 (LTV 적용)", f"{max_loan_amount // 10000}억 {max_loan_amount % 10000:,}만원")
match_pct = (len(affordable_df) / len(view_df) * 100) if len(view_df) > 0 else 0
m3.metric("🎯 매수 가능한 거래 건수", f"{len(affordable_df):,}건", f"전체 {len(view_df):,}건 중 {match_pct:.1f}%")
m4.metric("🏦 월 예상 원리금 상환액", f"{monthly_payment // 10000:,}만원")

st.divider()

# ── 7. 매수 가능 단지 순위 및 월별 거래량 ────────────────
c1, c2 = st.columns([3, 2])

display_title = f"{selected_sido} {scope_name}"
if selected_sido == "경기도" and selected_gu != f"{selected_city} 전체":
    display_title = f"{selected_city} {selected_gu}"
if selected_dong != '전체 보기':
    display_title += f" {selected_dong}"

with c1:
    st.subheader(f"📈 {display_title} 월별 거래량 추이")
    monthly_series = affordable_df['month'].value_counts().sort_index()
    st.bar_chart(monthly_series)

with c2:
    st.subheader(f"🥇 {selected_gu if selected_sido == '경기도' else scope_name} 동별 거래량 순위")
    rank_df = affordable_df.groupby(['city', 'dong']).size().reset_index(name='거래건수')
    rank_df = rank_df.sort_values(by='거래건수', ascending=False)
    rank_df.columns = ['시·군', '법정동(읍·면)', '거래건수']
    rank_df.index = range(1, len(rank_df) + 1)
    st.dataframe(rank_df, use_container_width=True, height=290)

st.divider()

# ── 8. 내 예산 맞춤 추천 단지 TOP 15 ──────────────────────
st.subheader(f"🏆 내 예산({max_affordable_price // 10000}억 이하) 맞춤 실거래 추천 단지 TOP 15")

if affordable_df.empty:
    st.info("현재 설정된 예산으로 매수 가능한 실거래 아파트가 없습니다. 자본금이나 LTV 비율을 올려보세요.")
else:
    apt_rank = affordable_df.groupby(['city', 'dong', 'apt']).agg(
        거래건수=('price', 'count'),
        평균실거래가=('price', 'mean'),
        최근최고가=('price', 'max'),
        전용면적_평균=('area', 'mean')
    ).reset_index()

    apt_rank = apt_rank.sort_values(by='거래건수', ascending=False).head(15)
    
    apt_rank['평균실거래가'] = apt_rank['평균실거래가'].astype(int).apply(lambda x: f"{x // 10000}억 {x % 10000:,}만" if x >= 10000 else f"{x:,}만")
    apt_rank['최근최고가'] = apt_rank['최근최고가'].astype(int).apply(lambda x: f"{x // 10000}억 {x % 10000:,}만" if x >= 10000 else f"{x:,}만")
    apt_rank['전용면적_평형'] = apt_rank['전용면적_평균'].apply(lambda x: f"{x:.1f}㎡ ({x/3.30578:.0f}평)")
    
    display_table = apt_rank[['city', 'dong', 'apt', '전용면적_평형', '거래건수', '평균실거래가', '최근최고가']]
    display_table.columns = ['시·군', '법정동(읍·면)', '단지명', '평균 면적', '거래건수', '평균 실거래가', '최근 최고가']
    display_table.index = range(1, len(display_table) + 1)

    st.dataframe(display_table, use_container_width=True)
