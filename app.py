import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import html
import time
import plotly.graph_objects as go
from datetime import datetime
from dateutil.relativedelta import relativedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── 1. 페이지 설정 ──────────────────────────────────────
st.set_page_config(
    page_title="전국 아파트 실거래가 및 내집마련 대시보드",
    page_icon="🏠",
    layout="wide"
)

# ── 1-1. 디자인 시스템 (컬러 / 카드 / 타이포) ─────────────
# 팔레트: 시퀀셜=블루 단일 색상(#2a78d6), 강조=오렌지(#eb6834) — 고정 순서로만 사용.
# 참고: 호갱노노/아실류 부동산 정보 서비스의 "카드형 KPI + 랭킹 카드 + 인터랙티브 차트" 패턴을 참고해
# Streamlit 기본 위젯 위에 커스텀 CSS/HTML을 얹는 방식으로 구현.
CUSTOM_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

:root {
    --brand-primary: #2a78d6;
    --brand-primary-dark: #184f95;
    --brand-accent: #eb6834;
    --surface: #ffffff;
    --page-bg: #f5f7fa;
    --ink-primary: #0b0b0b;
    --ink-secondary: #52514e;
    --ink-muted: #898781;
    --border-hairline: rgba(11,11,11,0.08);
    --good: #0ca30c;
}

html, body, [class*="css"] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.stApp { background-color: var(--page-bg); }
.block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1240px; }

/* 상단 히어로 배너 */
.hero-banner {
    background: linear-gradient(135deg, #184f95 0%, #2a78d6 55%, #3987e5 100%);
    border-radius: 20px; padding: 28px 32px; margin-bottom: 22px; color: #ffffff;
    box-shadow: 0 12px 30px rgba(24,79,149,0.28);
}
.hero-banner h1 { margin: 0; font-size: 1.65rem; font-weight: 800; letter-spacing: -0.02em; }
.hero-banner p { margin: 8px 0 0; opacity: .88; font-size: .92rem; }

/* 필터 스텝 칩 */
.step-chip {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(42,120,214,0.10); color: var(--brand-primary-dark);
    font-weight: 700; font-size: .76rem; padding: 3px 10px; border-radius: 999px;
    margin-bottom: 6px;
}

/* KPI 카드 */
.kpi-card {
    background: var(--surface); border-radius: 16px; padding: 18px 20px;
    border: 1px solid var(--border-hairline);
    box-shadow: 0 1px 2px rgba(11,11,11,0.04), 0 8px 22px rgba(11,11,11,0.05);
    height: 100%;
}
.kpi-label {
    font-size: .8rem; color: var(--ink-secondary); font-weight: 700;
    display: flex; align-items: center; gap: 6px;
}
.kpi-value { font-size: 1.55rem; font-weight: 800; color: var(--ink-primary); margin-top: 8px; font-variant-numeric: tabular-nums; }
.kpi-value.accent { color: var(--brand-accent); }
.kpi-value.primary { color: var(--brand-primary-dark); }
.kpi-sub { font-size: .78rem; color: var(--good); margin-top: 5px; font-weight: 700; }
.kpi-sub.muted { color: var(--ink-muted); font-weight: 500; }

/* 섹션 타이틀 */
.section-title {
    display: flex; align-items: center; gap: 8px; font-size: 1.05rem; font-weight: 800;
    color: var(--ink-primary); margin: 6px 0 14px; padding-left: 10px;
    border-left: 4px solid var(--brand-primary);
}

/* 추천 단지 TOP3 하이라이트 카드 */
.rank-card {
    background: var(--surface); border-radius: 16px; padding: 18px;
    border: 1px solid var(--border-hairline);
    box-shadow: 0 8px 22px rgba(11,11,11,0.06);
    position: relative; height: 100%;
}
.rank-badge { position: absolute; top: -14px; left: 16px; font-size: 1.6rem; filter: drop-shadow(0 3px 4px rgba(0,0,0,0.15)); }
.rank-apt { font-weight: 800; font-size: 1.02rem; margin-top: 10px; color: var(--ink-primary); line-height: 1.3; }
.rank-loc { font-size: .78rem; color: var(--ink-muted); margin-top: 4px; }
.rank-price { font-size: 1.3rem; font-weight: 800; color: var(--brand-accent); margin-top: 12px; font-variant-numeric: tabular-nums; }
.rank-meta { font-size: .76rem; color: var(--ink-secondary); margin-top: 4px; }

/* 데이터프레임 카드화 */
div[data-testid="stDataFrame"] {
    border-radius: 14px; overflow: hidden; border: 1px solid var(--border-hairline);
    font-variant-numeric: tabular-nums;
}

/* 사이드바 */
section[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border-hairline); }
.budget-card {
    background: linear-gradient(135deg, #eef4fd 0%, #f8fbfe 100%);
    border-radius: 14px; padding: 14px 16px; border: 1px solid rgba(42,120,214,0.16);
    margin-top: 8px;
}
.budget-row { display: flex; justify-content: space-between; align-items: baseline; font-size: .82rem; padding: 5px 0; color: var(--ink-secondary); }
.budget-row b { color: var(--ink-primary); font-size: 1rem; font-variant-numeric: tabular-nums; }
.sidebar-note { font-size: .78rem; color: var(--ink-muted); line-height: 1.5; padding: 8px 2px; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def format_price(x: int) -> str:
    """만원 단위 정수를 'N억 N,NNN만' 형식 문자열로 변환."""
    x = int(x)
    return f"{x // 10000}억 {x % 10000:,}만" if x >= 10000 else f"{x:,}만"


# ── 2. 기본 설정 및 행정구역 매핑 ───────────────────────
DECODING_KEY = 'HFLjN2wHoX4g3U2XNaBnhqTWwhmqxMqr9B2TcPbOZV9dJn8xZlFtiiymS0QNo7vbQEnk744KO+byEhW7SOucBA=='
ENCODING_KEY = urllib.parse.quote(DECODING_KEY)
BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

REGION_STRUCTURE = {
    "경기도": {
        "성남시": {"분당구": "41135", "수정구": "41131", "중원구": "41133"},
        "수원시": {"영통구": "41117", "장안구": "41111", "권선구": "41113", "팔달구": "41115"},
        "용인시": {"수지구": "41465", "기흥구": "41463", "처인구": "41461"},
        # 2026-02-01부로 화성시가 만세구·효행구·병점구·동탄구 4개 일반구 체제로 개편되면서
        # 기존 화성시 통합 코드(41590)로는 실거래가 API가 더 이상 데이터를 반환하지 않음.
        # 신설된 구별 코드로 교체 (수원시/성남시 등과 동일한 다구 시 구조로 처리).
        "화성시": {
            "만세구": "41591",
            "효행구": "41593",
            "병점구": "41595",
            "동탄구": "41597"
        },
        "고양시": {"일산동구": "41285", "일산서구": "41287", "덕양구": "41281"},
        "안양시": {"동안구": "41173", "만안구": "41171"},
        "부천시": {"원미구": "41192", "소사구": "41194", "오정구": "41196"},
        "안산시": {"단원구": "41273", "상록구": "41271"},
        "평택시": {"평택시 전체": "41220"},
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

def fetch_single_month_task(lawd_cd: str, deal_ymd: str, sido: str, city: str, gu: str):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/xml'
    }
    task_records = []
    page = 1

    while True:
        params = {
            'serviceKey': DECODING_KEY,
            'LAWD_CD': lawd_cd,
            'DEAL_YMD': deal_ymd,
            'numOfRows': '200',
            'pageNo': str(page)
        }

        res = None
        for attempt in range(2):
            try:
                res = requests.get(BASE_URL, params=params, headers=headers, timeout=12)
                if res.status_code == 200 and '<item>' in res.text:
                    break
            except Exception:
                time.sleep(0.2)

        if res is None or res.status_code != 200 or '<item>' not in res.text:
            fallback_url = f"{BASE_URL}?serviceKey={ENCODING_KEY}&LAWD_CD={lawd_cd}&DEAL_YMD={deal_ymd}&numOfRows=200&pageNo={page}"
            try:
                res = requests.get(fallback_url, headers=headers, timeout=12)
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
            if not raw_dong:
                raw_dong = r.get('aptDong', '').strip() or '기타'
            else:
                parts = raw_dong.split()
                if len(parts) > 1 and parts[0].endswith(('읍', '면')):
                    raw_dong = parts[0]

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

        if len(items) < 200 or len(task_records) >= total:
            break
        page += 1

    return task_records

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

# ── 3. 사이드바 설정 및 예산 계산기 ────────────────────────
st.sidebar.markdown("### ⚙️ 대시보드 설정")

if st.sidebar.button("🔄 캐시 초기화 및 데이터 다시 불러오기", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

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
calc_enabled = st.sidebar.toggle("🪙 내 자본금 맞춤 계산기 활성화", value=True)

if calc_enabled:
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

    st.sidebar.markdown(f"""
    <div class="budget-card">
      <div class="budget-row"><span>💵 최대 매수 가능가</span><b>{format_price(max_affordable_price)}원</b></div>
      <div class="budget-row"><span>💳 필요 대출금액</span><b>{format_price(max_loan_amount)}원</b></div>
      <div class="budget-row"><span>🏦 월 예상 원리금</span><b>{monthly_payment // 10000:,}만원 / 월</b></div>
    </div>
    """, unsafe_allow_html=True)

    filter_by_budget = st.sidebar.checkbox("🎯 내 예산 이하 단지만 필터링", value=True)
else:
    my_capital = 0
    max_affordable_price = None
    max_loan_amount = 0
    monthly_payment = 0
    filter_by_budget = False
    st.sidebar.markdown(
        '<div class="sidebar-note">계산기를 켜면 보유 자본금 기준 최대 매수가·월 원리금을 계산하고, '
        '예산 이하 단지만 걸러서 볼 수 있어요.</div>',
        unsafe_allow_html=True
    )

# ── 4. 메인 UI 및 계층형 지역 필터 ────────────────────────
st.markdown("""
<div class="hero-banner">
  <h1>🏠 전국 아파트 실거래가 및 내집마련 대시보드</h1>
  <p>국토교통부 실거래가 오픈 API 실시간 연동 · 시/구 전체 통합 집계 및 맞춤 추천</p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown('<div class="step-chip">1️⃣ 시·도</div>', unsafe_allow_html=True)
    sido_list = list(REGION_STRUCTURE.keys())
    selected_sido = st.selectbox(
        "시·도", sido_list, index=sido_list.index("경기도") if "경기도" in sido_list else 0,
        label_visibility="collapsed"
    )

sido_data = REGION_STRUCTURE[selected_sido]
target_codes_to_fetch = []

if selected_sido == "경기도":
    with col2:
        st.markdown('<div class="step-chip">2️⃣ 시·군</div>', unsafe_allow_html=True)
        city_options = ["경기도 전체"] + list(sido_data.keys())
        default_city_idx = city_options.index("성남시") if "성남시" in city_options else 1
        selected_city = st.selectbox("시·군", city_options, index=default_city_idx, label_visibility="collapsed")

    if selected_city == "경기도 전체":
        with col3:
            st.markdown('<div class="step-chip">3️⃣ 구·권역</div>', unsafe_allow_html=True)
            selected_gu = st.selectbox("구·권역", ["경기도 전체"], label_visibility="collapsed")
        for c_name, gu_dict in sido_data.items():
            for g_name, code in gu_dict.items():
                target_codes_to_fetch.append((code, selected_sido, c_name, g_name))
    else:
        gu_dict = sido_data[selected_city]
        gu_keys = list(gu_dict.keys())

        if len(gu_keys) > 1:
            gu_options = [f"{selected_city} 전체"] + gu_keys
        else:
            gu_options = gu_keys

        with col3:
            st.markdown('<div class="step-chip">3️⃣ 구·권역</div>', unsafe_allow_html=True)
            selected_gu = st.selectbox("구·권역", gu_options, label_visibility="collapsed")

        if selected_gu == f"{selected_city} 전체":
            for g_name, code in gu_dict.items():
                target_codes_to_fetch.append((code, selected_sido, selected_city, g_name))
        else:
            code = gu_dict[selected_gu]
            target_codes_to_fetch.append((code, selected_sido, selected_city, selected_gu))
else:
    with col2:
        st.markdown('<div class="step-chip">2️⃣ 구·군</div>', unsafe_allow_html=True)
        gu_options = [f"{selected_sido} 전체"] + list(sido_data.keys())
        selected_gu_direct = st.selectbox("구·군", gu_options, label_visibility="collapsed")
    with col3:
        st.markdown('<div class="step-chip">3️⃣ 구·권역</div>', unsafe_allow_html=True)
        st.selectbox("구·권역", ["-"], disabled=True, label_visibility="collapsed")

    if selected_gu_direct == f"{selected_sido} 전체":
        for g_name, code in sido_data.items():
            target_codes_to_fetch.append((code, selected_sido, selected_sido, g_name))
    else:
        code = sido_data[selected_gu_direct]
        target_codes_to_fetch.append((code, selected_sido, selected_sido, selected_gu_direct))

scope_name = selected_city if selected_sido == "경기도" else selected_gu_direct

with st.spinner(f"'{selected_sido} {scope_name} ({selected_gu if selected_sido == '경기도' else ''})' 실거래 데이터를 조회 중입니다..."):
    df = fetch_target_records(tuple(target_codes_to_fetch), tuple(target_months))

if df.empty:
    st.cache_data.clear()
    st.warning("국토교통부 API 서버 응답이 지연되었습니다. 사이드바의 [🔄 캐시 초기화 및 데이터 다시 불러오기]를 눌러주세요.")
    st.stop()

with col4:
    st.markdown('<div class="step-chip">4️⃣ 읍·면·동</div>', unsafe_allow_html=True)
    dong_list = ['전체 보기'] + sorted(list(df['dong'].unique())) if not df.empty else ['전체 보기']
    selected_dong = st.selectbox("읍·면·동", dong_list, label_visibility="collapsed")

view_df = df if selected_dong == '전체 보기' else df[df['dong'] == selected_dong]

if filter_by_budget and max_affordable_price is not None:
    affordable_df = view_df[view_df['price'] <= max_affordable_price]
else:
    affordable_df = view_df

# ── 5. 요약 통계 및 시각화 ─────────────────────────────────
match_pct = (len(affordable_df) / len(view_df) * 100) if len(view_df) > 0 else 0

k1, k2, k3, k4 = st.columns(4)

if calc_enabled:
    with k1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">💵 최대 매수가</div>
            <div class="kpi-value accent">{format_price(max_affordable_price)}</div>
            <div class="kpi-sub muted">자본금 {my_capital:,}만 · LTV {ltv_rate}%</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">💳 필요 대출금</div>
            <div class="kpi-value">{format_price(max_loan_amount)}</div>
            <div class="kpi-sub muted">금리 {loan_interest:.1f}% · {loan_term_years}년 만기</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">🎯 매수 가능 거래</div>
            <div class="kpi-value">{len(affordable_df):,}건</div>
            <div class="kpi-sub">↑ 전체 {len(view_df):,}건 중 {match_pct:.1f}%</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">🏦 월 예상 원리금</div>
            <div class="kpi-value primary">{monthly_payment // 10000:,}만원</div>
            <div class="kpi-sub muted">원리금 균등분할 기준</div>
        </div>""", unsafe_allow_html=True)
else:
    avg_price = int(view_df['price'].mean()) if len(view_df) > 0 else 0
    max_price = int(view_df['price'].max()) if len(view_df) > 0 else 0
    apt_count = view_df['apt'].nunique() if len(view_df) > 0 else 0
    with k1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">📊 전체 거래건수</div>
            <div class="kpi-value">{len(view_df):,}건</div>
            <div class="kpi-sub muted">선택 지역·기간 기준</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">💰 평균 실거래가</div>
            <div class="kpi-value accent">{format_price(avg_price)}</div>
            <div class="kpi-sub muted">전체 거래 평균</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">🏆 최고 실거래가</div>
            <div class="kpi-value">{format_price(max_price)}</div>
            <div class="kpi-sub muted">최근 6개월~ 기준</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">🏘️ 거래 단지 수</div>
            <div class="kpi-value primary">{apt_count:,}개</div>
            <div class="kpi-sub muted">사이드바에서 계산기를 켜보세요</div>
        </div>""", unsafe_allow_html=True)

st.write("")

c1, c2 = st.columns([3, 2])

display_title = f"{selected_sido} {scope_name}"
if selected_sido == "경기도" and selected_gu != f"{selected_city} 전체":
    display_title = f"{selected_city} {selected_gu}"
if selected_dong != '전체 보기':
    display_title += f" {selected_dong}"

with c1:
    st.markdown(f'<div class="section-title">📈 {display_title} 월별 거래량 추이</div>', unsafe_allow_html=True)
    monthly_series = affordable_df['month'].value_counts().sort_index()
    fig = go.Figure(go.Bar(
        x=monthly_series.index,
        y=monthly_series.values,
        marker_color="#2a78d6",
        hovertemplate="%{x}<br><b>%{y}건</b><extra></extra>",
    ))
    fig.update_layout(
        plot_bgcolor="#fcfcfb",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        height=320,
        font=dict(family="Pretendard, sans-serif", color="#52514e", size=13),
        xaxis=dict(showgrid=False, linecolor="#c3c2b7"),
        yaxis=dict(gridcolor="#e1e0d9", zeroline=False),
        hoverlabel=dict(bgcolor="#184f95", font_color="#ffffff", font_family="Pretendard, sans-serif"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with c2:
    st.markdown(
        f'<div class="section-title">🥇 {selected_gu if selected_sido == "경기도" else scope_name} 동별 거래량 순위</div>',
        unsafe_allow_html=True
    )
    rank_df = affordable_df.groupby(['city', 'gu', 'dong']).size().reset_index(name='거래건수')
    rank_df = rank_df.sort_values(by='거래건수', ascending=False)
    rank_df.columns = ['시·군', '구', '동·읍·면명', '거래건수']
    rank_df.index = range(1, len(rank_df) + 1)
    max_count = int(rank_df['거래건수'].max()) if len(rank_df) > 0 else 1
    st.dataframe(
        rank_df,
        use_container_width=True,
        height=290,
        column_config={
            "거래건수": st.column_config.ProgressColumn(
                "거래건수", format="%d건", min_value=0, max_value=max_count
            )
        }
    )

st.write("")

if calc_enabled:
    st.markdown(
        f'<div class="section-title">🏆 내 예산({max_affordable_price // 10000}억 이하) 맞춤 실거래 추천 단지 TOP 15</div>',
        unsafe_allow_html=True
    )
else:
    st.markdown('<div class="section-title">🏆 실거래 인기 단지 TOP 15 (전체 거래 기준)</div>', unsafe_allow_html=True)

if affordable_df.empty:
    st.info("현재 설정된 예산으로 매수 가능한 실거래 아파트가 없습니다. 자본금이나 LTV 비율을 올려보세요.")
else:
    apt_rank = affordable_df.groupby(['city', 'gu', 'dong', 'apt']).agg(
        거래건수=('price', 'count'),
        평균실거래가=('price', 'mean'),
        최근최고가=('price', 'max'),
        전용면적_평균=('area', 'mean')
    ).reset_index()

    apt_rank = apt_rank.sort_values(by='거래건수', ascending=False).head(15).reset_index(drop=True)

    apt_rank['평균실거래가_fmt'] = apt_rank['평균실거래가'].astype(int).apply(format_price)
    apt_rank['최근최고가_fmt'] = apt_rank['최근최고가'].astype(int).apply(format_price)
    apt_rank['전용면적_평형'] = apt_rank['전용면적_평균'].apply(lambda x: f"{x:.1f}㎡ ({x/3.30578:.0f}평)")

    # 상위 3개 단지는 하이라이트 카드로
    medals = ['🥇', '🥈', '🥉']
    top3 = apt_rank.head(3)
    if len(top3) > 0:
        top_cols = st.columns(len(top3))
        for i, (_, row) in enumerate(top3.iterrows()):
            apt_name = html.escape(str(row['apt']))
            loc_txt = html.escape(f"{row['city']} {row['gu']} {row['dong']} · {row['전용면적_평형']}")
            with top_cols[i]:
                st.markdown(f"""<div class="rank-card">
                    <div class="rank-badge">{medals[i]}</div>
                    <div class="rank-apt">{apt_name}</div>
                    <div class="rank-loc">{loc_txt}</div>
                    <div class="rank-price">{row['평균실거래가_fmt']}원</div>
                    <div class="rank-meta">거래 {row['거래건수']}건 · 최고가 {row['최근최고가_fmt']}원</div>
                </div>""", unsafe_allow_html=True)
        st.write("")

    # 4위 이하는 표로
    rest = apt_rank.iloc[3:].copy()
    if not rest.empty:
        rest_display = rest[['city', 'gu', 'dong', 'apt', '전용면적_평형', '거래건수', '평균실거래가_fmt', '최근최고가_fmt']].copy()
        rest_display.columns = ['시·군', '구', '법정동(읍·면)', '단지명', '평균 면적', '거래건수', '평균 실거래가', '최근 최고가']
        rest_display.index = range(4, 4 + len(rest_display))
        max_txn = int(apt_rank['거래건수'].max())
        st.dataframe(
            rest_display,
            use_container_width=True,
            column_config={
                "거래건수": st.column_config.ProgressColumn(
                    "거래건수", format="%d건", min_value=0, max_value=max_txn
                )
            }
        )
