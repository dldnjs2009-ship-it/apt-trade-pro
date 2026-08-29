import streamlit as st
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import xml.etree.ElementTree as ET
import urllib.parse
import html
import time
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# 한국 표준시(KST, UTC+9) 타임존 정의
KST = timezone(timedelta(hours=9))

# ── 1. 페이지 설정 ──────────────────────────────────────
st.set_page_config(
    page_title="전국 아파트 실거래가 및 내집마련 대시보드",
    page_icon="🏠",
    layout="wide"
)

# ── 1-1. 디자인 시스템 (PC / 모바일 반응형 CSS Grid) ─────────
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
    --danger: #e53e3e;
    --warning: #dd6b20;
    --rise: #e53e3e;
    --fall: #2a78d6;
    --gap-purple: #7048e8;
}

html, body, [class*="css"] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.stApp { background-color: var(--page-bg); }
.block-container { padding-top: 1.2rem; padding-bottom: 2.5rem; max-width: 1240px; }

/* 상단 히어로 배너 */
.hero-banner {
    background: linear-gradient(135deg, #184f95 0%, #2a78d6 55%, #3987e5 100%);
    border-radius: 16px; padding: 20px 24px; margin-bottom: 14px; color: #ffffff;
    box-shadow: 0 8px 20px rgba(24,79,149,0.20);
}
.hero-banner h1 { margin: 0; font-size: 1.45rem; font-weight: 800; letter-spacing: -0.02em; }
.hero-banner p { margin: 5px 0 0; opacity: .88; font-size: .85rem; }

/* 필터 스텝 칩 */
.step-chip {
    display: inline-flex; align-items: center; gap: 4px;
    background: rgba(42,120,214,0.10); color: var(--brand-primary-dark);
    font-weight: 700; font-size: .75rem; padding: 2px 8px; border-radius: 999px;
    margin-bottom: 3px;
}

/* KPI 카드 그리드 */
.kpi-grid-container {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin: 10px 0 16px;
}
.kpi-card {
    background: var(--surface); border-radius: 14px; padding: 14px 16px;
    border: 1px solid var(--border-hairline);
    box-shadow: 0 1px 2px rgba(11,11,11,0.03), 0 6px 18px rgba(11,11,11,0.04);
    height: 100%; box-sizing: border-box;
}
.kpi-label {
    font-size: .78rem; color: var(--ink-secondary); font-weight: 700;
    display: flex; align-items: center; gap: 5px;
}
.kpi-value { font-size: 1.4rem; font-weight: 800; color: var(--ink-primary); margin-top: 6px; font-variant-numeric: tabular-nums; }
.kpi-value.accent { color: var(--brand-accent); }
.kpi-value.primary { color: var(--brand-primary-dark); }
.kpi-sub { 
    font-size: .74rem; 
    color: var(--good); 
    margin-top: 4px; 
    font-weight: 700; 
    white-space: nowrap; 
    overflow: hidden; 
    text-overflow: ellipsis; 
}
.kpi-sub.muted { color: var(--ink-muted); font-weight: 500; }

/* 섹션 타이틀 */
.section-title {
    display: flex; align-items: center; gap: 8px; font-size: 1.02rem; font-weight: 800;
    color: var(--ink-primary); margin: 6px 0 12px; padding-left: 10px;
    border-left: 4px solid var(--brand-primary);
}

/* 추천 단지 TOP3 하이라이트 카드 */
.rank-card {
    background: var(--surface); border-radius: 14px; padding: 16px;
    border: 1px solid var(--border-hairline);
    box-shadow: 0 6px 18px rgba(11,11,11,0.05);
    position: relative; height: 100%;
    display: flex; flex-direction: column; justify-content: space-between;
}
.rank-badge { position: absolute; top: -12px; left: 14px; font-size: 1.5rem; filter: drop-shadow(0 2px 3px rgba(0,0,0,0.12)); }
.rank-apt { font-weight: 800; font-size: 1.02rem; margin-top: 8px; color: var(--ink-primary); line-height: 1.3; }
.rank-loc { font-size: .76rem; color: var(--ink-muted); margin-top: 4px; }
.rank-price { font-size: 1.38rem; font-weight: 800; color: var(--brand-accent); margin-top: 10px; font-variant-numeric: tabular-nums; }
.rank-meta { font-size: .76rem; color: var(--ink-secondary); margin-top: 5px; }

.rank-gap-box {
    background: #f8f6ff; border-radius: 8px; padding: 6px 10px; margin-top: 8px;
    border: 1px solid rgba(112, 72, 232, 0.18);
    font-size: .77rem; color: var(--gap-purple); font-weight: 700;
}

/* 6개월 시세 변동률 배지 */
.badge-rate {
    display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: .72rem; font-weight: 800; margin-top: 6px;
}
.badge-rate.surge { background: rgba(229, 62, 62, 0.14); color: var(--rise); border: 1px solid rgba(229, 62, 62, 0.25); }
.badge-rate.rise { background: rgba(235, 104, 52, 0.12); color: var(--brand-accent); }
.badge-rate.flat { background: rgba(137, 135, 129, 0.12); color: var(--ink-secondary); }
.badge-rate.fall { background: rgba(42, 120, 214, 0.12); color: var(--fall); }
.badge-rate.drop { background: rgba(24, 79, 149, 0.15); color: var(--brand-primary-dark); font-weight: 900; }

/* 데이터프레임 스타일 */
div[data-testid="stDataFrame"] {
    border-radius: 12px; overflow: hidden; border: 1px solid var(--border-hairline);
    font-variant-numeric: tabular-nums;
}

/* 사이드바 예산 상세 */
section[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border-hairline); }
.budget-card {
    background: linear-gradient(135deg, #eef4fd 0%, #f8fbfe 100%);
    border-radius: 12px; padding: 12px 14px; border: 1px solid rgba(42,120,214,0.16);
    margin-top: 6px;
}
.budget-row { display: flex; justify-content: space-between; align-items: baseline; font-size: .79rem; padding: 3px 0; color: var(--ink-secondary); }
.budget-row b { color: var(--ink-primary); font-size: .92rem; font-variant-numeric: tabular-nums; }
.budget-divider { border-top: 1px dashed rgba(42,120,214,0.22); margin: 6px 0; }
.sidebar-note { font-size: .75rem; color: var(--ink-muted); line-height: 1.4; padding: 6px 2px; }

/* 📱 모바일 반응형 압축 */
@media (max-width: 768px) {
    .block-container {
        padding-top: 0.8rem !important;
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        padding-bottom: 2rem !important;
    }
    .hero-banner {
        padding: 14px 16px !important;
        border-radius: 12px !important;
        margin-bottom: 10px !important;
    }
    .hero-banner h1 { font-size: 1.15rem !important; }
    .hero-banner p { font-size: 0.76rem !important; margin-top: 3px !important; }

    div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        gap: 6px !important;
    }
    div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div[data-testid="column"] {
        width: calc(50% - 3px) !important;
        min-width: calc(50% - 3px) !important;
        max-width: calc(50% - 3px) !important;
        flex: 1 1 calc(50% - 3px) !important;
        margin-bottom: 2px !important;
    }
    div[data-testid="stSelectbox"] {
        margin-bottom: -10px !important;
    }

    .kpi-grid-container {
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 6px !important;
        margin: 8px 0 12px !important;
    }
    .kpi-card { padding: 10px 12px !important; border-radius: 10px !important; }
    .kpi-label { font-size: 0.72rem !important; }
    .kpi-value { font-size: 1.15rem !important; margin-top: 3px !important; }
    .kpi-sub { font-size: 0.68rem !important; margin-top: 2px !important; }
    .step-chip { font-size: 0.68rem !important; padding: 1px 6px !important; margin-bottom: 1px !important; }

    .rank-card { padding: 12px 14px !important; margin-top: 10px !important; }
    .rank-badge { font-size: 1.3rem !important; top: -10px !important; }
    .rank-apt { font-size: 0.95rem !important; }
    .rank-price { font-size: 1.2rem !important; margin-top: 6px !important; }
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ── 1-2. 보조 연산 및 부대비용/면적 환산 함수 ──────────────────
def format_price(x: int) -> str:
    """만원 단위 정수를 'N억 N,NNN만' 형식 문자열로 변환."""
    if pd.isna(x) or x is None or int(x) <= 0:
        return "-"
    x = int(x)
    return f"{x // 10000}억 {x % 10000:,}만" if x >= 10000 else f"{x:,}만"


def get_pyeong_group_key(m2: float) -> tuple:
    """전용면적(㎡)을 분양/공급 체감 평형 그룹으로 분류."""
    supply_p = int(round((m2 / 3.30578) / 0.745))
    label = f"{m2:.1f}㎡ ({supply_p}평형)"
    return supply_p, label


def calculate_acquisition_costs(price: int) -> dict:
    """만원 단위 매매가 기준 취득세, 중개보수, 법무/기타비용 정밀 산출"""
    if price <= 60000:
        tax_rate = 0.011
    elif price <= 90000:
        tax_rate = (((price * (2 / 30000)) - 3) / 100) * 1.1
    else:
        tax_rate = 0.033

    acquisition_tax = int(price * tax_rate)

    if price < 20000:
        broker_rate = 0.005
    elif price < 90000:
        broker_rate = 0.004
    elif price < 120000:
        broker_rate = 0.005
    elif price < 150000:
        broker_rate = 0.006
    else:
        broker_rate = 0.007

    broker_fee = int(price * broker_rate)
    etc_fee = int(price * 0.004)

    total_costs = acquisition_tax + broker_fee + etc_fee
    return {
        "취득세": acquisition_tax,
        "중개보수": broker_fee,
        "기타비용": etc_fee,
        "총부대비용": total_costs
    }


def calculate_dsr_max_loan(annual_income: int, loan_interest: float, term_years: int) -> int:
    """연소득 기준 DSR 40% 최대 대출 가능 원금 역산 (만원 단위)"""
    if annual_income <= 0:
        return 0
    max_annual_payment = annual_income * 0.40
    max_monthly_payment = (max_annual_payment * 10000) / 12
    monthly_rate = (loan_interest / 100) / 12
    total_months = term_years * 12

    max_loan = (max_monthly_payment * (((1 + monthly_rate) ** total_months) - 1)) / (
        monthly_rate * ((1 + monthly_rate) ** total_months)
    )
    return int(max_loan // 10000)


def get_trend_badge(trend_rate: float) -> str:
    """6개월 전 대비 시세 변동률(모멘텀) 상태 배지 생성"""
    if trend_rate >= 5.0:
        return f'<span class="badge-rate surge">🔥 급상승 (+{trend_rate:.1f}%)</span>'
    elif trend_rate >= 1.0:
        return f'<span class="badge-rate rise">📈 상승 (+{trend_rate:.1f}%)</span>'
    elif trend_rate > -1.0:
        return f'<span class="badge-rate flat">➖ 보합 ({trend_rate:+.1f}%)</span>'
    elif trend_rate > -5.0:
        return f'<span class="badge-rate fall">📉 조정 ({trend_rate:.1f}%)</span>'
    else:
        return f'<span class="badge-rate drop">🧊 급락 ({trend_rate:.1f}%)</span>'


def remove_bulk_acquisitions(df: pd.DataFrame, threshold: int = 10) -> pd.DataFrame:
    """동일 단지/월/면적/가격 10건 이상 통매입/임대 이상치 필터링"""
    if df.empty:
        return df
    duplicate_counts = df.groupby(['apt', 'month', 'area', 'price'])['price'].transform('count')
    cleaned_df = df[duplicate_counts < threshold].copy()
    return cleaned_df


# ── 2. 기본 설정, 세션 풀 및 방문자 집계 ──────────────────
DECODING_KEY = 'HFLjN2wHoX4g3U2XNaBnhqTWwhmqxMqr9B2TcPbOZV9dJn8xZlFtiiymS0QNo7vbQEnk744KO+byEhW7SOucBA=='
ENCODING_KEY = urllib.parse.quote(DECODING_KEY)

TRADE_BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
RENT_API_URLS = [
    "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
    "https://apis.data.go.kr/1613000/RTMSDataSvcAptRentDev/getRTMSDataSvcAptRentDev"
]

@st.cache_resource
def get_visitor_storage():
    return {
        "daily": {},
        "total": 0,
        "logs": []
    }

visitor_storage = get_visitor_storage()
now_kst = datetime.now(KST)
today_key = now_kst.strftime("%Y-%m-%d")

if "session_visited" not in st.session_state:
    st.session_state["session_visited"] = True
    visitor_storage["total"] += 1
    visitor_storage["daily"][today_key] = visitor_storage["daily"].get(today_key, 0) + 1
    visitor_storage["logs"].append({
        "time": now_kst.strftime("%H:%M:%S"),
        "date": today_key
    })

@st.cache_resource
def get_http_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(pool_connections=25, pool_maxsize=25, max_retries=retries)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/xml'
    })
    return session

HTTP_SESSION = get_http_session()

REGION_STRUCTURE = {
    "경기도": {
        "성남시": {"분당구": "41135", "수정구": "41131", "중원구": "41133"},
        "수원시": {"영통구": "41117", "장안구": "41111", "권선구": "41113", "팔달구": "41115"},
        "용인시": {"수지구": "41465", "기흥구": "41463", "처인구": "41461"},
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

# ── 3. 단일 월 매매 및 전세 수집 태스크 ───────────────────────
def fetch_trade_task(lawd_cd: str, deal_ymd: str, sido: str, city: str, gu: str):
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
        try:
            res = HTTP_SESSION.get(TRADE_BASE_URL, params=params, timeout=12)
        except Exception:
            pass

        if res is None or res.status_code != 200 or '<item>' not in res.text:
            fallback_url = f"{TRADE_BASE_URL}?serviceKey={ENCODING_KEY}&LAWD_CD={lawd_cd}&DEAL_YMD={deal_ymd}&numOfRows=1000&pageNo={page}"
            try:
                res = HTTP_SESSION.get(fallback_url, timeout=12)
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

            raw_dong = r.get('umdNm', '').strip() or r.get('aptDong', '').strip() or '기타'
            floor_str = str(r.get('floor', '0')).strip()
            try:
                floor_val = int(floor_str)
            except ValueError:
                floor_val = 0

            deal_type = r.get('dealingGbn', '').strip() or r.get('reqGbn', '').strip() or '중개거래'
            deal_year = r.get('dealYear', '')
            deal_month = str(r.get('dealMonth', '')).zfill(2)
            deal_day = str(r.get('dealDay', '1')).zfill(2)

            task_records.append({
                'sido': sido,
                'city': city,
                'gu': gu,
                'dong': raw_dong,
                'apt': r.get('aptNm', '').strip(),
                'area': float(r.get('excluUseAr', 0) or 0),
                'floor': floor_val,
                'deal_type': deal_type,
                'price': int(str(r.get('dealAmount', '0')).replace(',', '').strip() or 0),
                'month': f"{deal_year}-{deal_month}",
                'deal_date': f"{deal_year}-{deal_month}-{deal_day}"
            })

        if len(items) < 1000 or len(task_records) >= total:
            break
        page += 1

    return task_records


def fetch_rent_task(lawd_cd: str, deal_ymd: str, sido: str, city: str, gu: str):
    task_records = []
    page = 1

    while True:
        res = None
        for url in RENT_API_URLS:
            params = {
                'serviceKey': DECODING_KEY,
                'LAWD_CD': lawd_cd,
                'DEAL_YMD': deal_ymd,
                'numOfRows': '1000',
                'pageNo': str(page)
            }
            try:
                r = HTTP_SESSION.get(url, params=params, timeout=12)
                if r.status_code == 200 and '<item>' in r.text:
                    res = r
                    break
                fallback_url = f"{url}?serviceKey={ENCODING_KEY}&LAWD_CD={lawd_cd}&DEAL_YMD={deal_ymd}&numOfRows=1000&pageNo={page}"
                r_fb = HTTP_SESSION.get(fallback_url, timeout=12)
                if r_fb.status_code == 200 and '<item>' in r_fb.text:
                    res = r_fb
                    break
            except Exception:
                continue

        if res is None or res.status_code != 200:
            break

        try:
            root = ET.fromstring(res.content)
        except Exception:
            break

        items = root.findall('.//item')
        if not items:
            break

        for item in items:
            r = {child.tag: (child.text.strip() if child.text else '') for child in item}
            monthly_rent = str(r.get('monthlyRent', '0')).replace(',', '').strip()
            # 순수 전세만 수집
            if monthly_rent == '0':
                raw_dong = r.get('umdNm', '').strip() or r.get('aptDong', '').strip() or '기타'
                floor_str = str(r.get('floor', '0')).strip()
                try:
                    floor_val = int(floor_str)
                except ValueError:
                    floor_val = 0

                deposit = int(str(r.get('deposit', '0')).replace(',', '').strip() or 0)
                deal_year = r.get('dealYear', '')
                deal_month = str(r.get('dealMonth', '')).zfill(2)

                task_records.append({
                    'sido': sido,
                    'city': city,
                    'gu': gu,
                    'dong': raw_dong,
                    'apt': r.get('aptNm', '').strip(),
                    'area': float(r.get('excluUseAr', 0) or 0),
                    'floor': floor_val,
                    'deposit': deposit,
                    'month': f"{deal_year}-{deal_month}"
                })

        if len(items) < 1000:
            break
        page += 1

    return task_records

# ── 4. 병렬 분산 수집 & 캐싱 ──────────────────────────────
@st.cache_data(ttl=86400)
def fetch_all_target_records(target_list_tuples, target_months_tuple):
    trade_tasks = []
    rent_tasks = []
    seen_calls = set()

    for code, sido, city, gu in target_list_tuples:
        for deal_ymd in target_months_tuple:
            call_key = (code, deal_ymd)
            if call_key not in seen_calls:
                seen_calls.add(call_key)
                trade_tasks.append((code, deal_ymd, sido, city, gu))
                rent_tasks.append((code, deal_ymd, sido, city, gu))

    all_trade_records = []
    all_rent_records = []

    with ThreadPoolExecutor(max_workers=16) as executor:
        trade_futures = [executor.submit(fetch_trade_task, *task) for task in trade_tasks]
        rent_futures = [executor.submit(fetch_rent_task, *task) for task in rent_tasks]

        for future in as_completed(trade_futures):
            try:
                res = future.result()
                if res:
                    all_trade_records.extend(res)
            except Exception:
                pass

        for future in as_completed(rent_futures):
            try:
                res = future.result()
                if res:
                    all_rent_records.extend(res)
            except Exception:
                pass

    return pd.DataFrame(all_trade_records), pd.DataFrame(all_rent_records)

# ── 5. 사이드바 설정 ─────────────────────────────────────
st.sidebar.markdown("### ⚙️ 대시보드 설정")

with st.sidebar.expander("🔒 관리자 모드 (방문자 확인)", expanded=False):
    admin_password = st.text_input("비밀번호 입력", type="password", key="admin_auth_pwd")
    ADMIN_SECRET_KEY = "7576"

    if admin_password == ADMIN_SECRET_KEY:
        st.success("인증 완료")
        today_visitors = visitor_storage["daily"].get(today_key, 0)
        total_visitors = visitor_storage["total"]

        adm_col1, adm_col2 = st.columns(2)
        adm_col1.metric("오늘 방문자", f"{today_visitors:,}명")
        adm_col2.metric("누적 방문자", f"{total_visitors:,}명")

        if visitor_storage["logs"]:
            today_logs = [log for log in visitor_storage["logs"] if log["date"] == today_key]
            st.caption(f"최근 접속 기록(한국 시간): {today_logs[-1]['time'] if today_logs else '-'}")
    elif admin_password:
        st.error("비밀번호가 일치하지 않습니다.")

st.sidebar.markdown("---")

if st.sidebar.button("🔄 캐시 초기화 및 데이터 다시 불러오기", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# [1] 조회 기간 선택
period_option = st.sidebar.selectbox(
    "📅 조회 기간 선택",
    ["최근 6개월 (실시간)", "최근 12개월 (1년)", "2024년 전체"],
    index=0
)

if period_option == "최근 6개월 (실시간)":
    target_months = [(now_kst - relativedelta(months=i)).strftime('%Y%m') for i in range(5, -1, -1)]
elif period_option == "최근 12개월 (1년)":
    target_months = [(now_kst - relativedelta(months=i)).strftime('%Y%m') for i in range(11, -1, -1)]
else:
    target_months = [f"2024{m:02d}" for m in range(1, 13)]

# [2] 이상치 정제 옵션
filter_bulk_option = st.sidebar.checkbox(
    "🚫 통매입/임대 대량 일괄거래 제외",
    value=True,
    help="동일 단지·월·면적·가격으로 10건 이상 동시 등록된 공공 매입임대/통매매 이상치를 제거합니다."
)

st.sidebar.markdown("---")

# [3] 공급/분양평형 기준 면적 필터
st.sidebar.markdown("### 📐 분양/공급평형 필터")
area_unit = st.sidebar.radio("면적 단위", ["공급평형", "전용면적(㎡)"], index=0, horizontal=True)

quick_pyeong_options = ["~10평형대", "20평형대 (전용 59타입 등)", "30평형대 (전용 84타입 등)", "40평형대 (대형)", "50평형대 이상"]

selected_quick_pyeong = st.sidebar.multiselect(
    "⚡ 평형대 빠른 선택 (다중 선택 가능)",
    quick_pyeong_options,
    default=[],
    help="체감 공급평형(24평형, 34평형 등) 기준으로 필터링합니다."
)

PYEONG_BAND_MAP = {
    "~10평형대": (0.0, 19.99),
    "20평형대 (전용 59타입 등)": (20.0, 29.99),
    "30평형대 (전용 84타입 등)": (30.0, 39.99),
    "40평형대 (대형)": (40.0, 49.99),
    "50평형대 이상": (50.0, 999.0)
}

if area_unit == "공급평형":
    slider_pyeong_range = st.sidebar.slider(
        "공급평형 범위 미세 조정",
        min_value=0,
        max_value=80,
        value=(0, 80),
        step=1,
        format="%d평형"
    )
    slider_min_p, slider_max_p = slider_pyeong_range
else:
    slider_m2_range = st.sidebar.slider(
        "전용면적 범위 미세 조정 (㎡)",
        min_value=0,
        max_value=250,
        value=(0, 250),
        step=5,
        format="%d㎡"
    )
    slider_min_m2, slider_max_m2 = slider_m2_range

st.sidebar.markdown("---")

# [4] 정밀 자본금 & DSR 계산기
calc_enabled = st.sidebar.toggle("🪙 정밀 자본금 & DSR 계산기 활성화", value=False)

if calc_enabled:
    my_capital = st.sidebar.number_input(
        "내 보유 순수 자본금 (만원)",
        min_value=1000,
        max_value=500000,
        value=30000,
        step=1000,
        help="부동산 매수에 투입 가능한 순수 자기자본입니다."
    )

    use_dsr = st.sidebar.checkbox("📊 DSR 40% 한도 역산 적용", value=True)
    if use_dsr:
        annual_income = st.sidebar.number_input(
            "본인/부부합산 연소득 (만원)",
            min_value=1000,
            max_value=30000,
            value=7000,
            step=500,
            help="DSR 40% 기준 연간 원리금 상환 한도를 계산합니다."
        )
    else:
        annual_income = 0

    ltv_rate = st.sidebar.slider("희망 대출 비율 (LTV %)", min_value=0, max_value=80, value=70, step=5)
    loan_interest = st.sidebar.slider("대출 예상 금리 (%)", min_value=2.0, max_value=8.0, value=4.0, step=0.1)
    loan_term_years = st.sidebar.selectbox("대출 만기 (년)", [10, 20, 30, 40], index=2)

    if use_dsr and annual_income > 0:
        dsr_max_loan = calculate_dsr_max_loan(annual_income, loan_interest, loan_term_years)
    else:
        dsr_max_loan = 9999999

    temp_price = int(my_capital / (1 - (ltv_rate / 100) + 0.035)) if ltv_rate < 100 else my_capital * 2
    for _ in range(3):
        costs = calculate_acquisition_costs(temp_price)
        avail_capital = my_capital - costs['총부대비용']
        if ltv_rate < 100:
            ltv_price = int(avail_capital / (1 - (ltv_rate / 100)))
        else:
            ltv_price = avail_capital * 2
        temp_price = max(1000, ltv_price)

    ltv_loan = temp_price - (my_capital - calculate_acquisition_costs(temp_price)['총부대비용'])
    actual_loan_amount = min(ltv_loan, dsr_max_loan)
    actual_loan_amount = max(0, actual_loan_amount)

    final_costs = calculate_acquisition_costs(temp_price)
    max_affordable_price = (my_capital - final_costs['총부대비용']) + actual_loan_amount

    if actual_loan_amount > 0:
        monthly_rate = (loan_interest / 100) / 12
        total_months = loan_term_years * 12
        monthly_payment = int(
            (actual_loan_amount * 10000 * monthly_rate * ((1 + monthly_rate) ** total_months))
            / (((1 + monthly_rate) ** total_months) - 1)
        )
    else:
        monthly_payment = 0

    st.sidebar.markdown(f"""
    <div class="budget-card">
      <div class="budget-row"><span>💵 최대 매수 가능가</span><b>{format_price(max_affordable_price)}원</b></div>
      <div class="budget-row"><span>💳 필요 대출금액</span><b>{format_price(actual_loan_amount)}원</b></div>
      <div class="budget-row"><span>🏦 월 예상 원리금</span><b>{monthly_payment // 10000:,}만원 / 월</b></div>
      <div class="budget-divider"></div>
      <div class="budget-row"><span>💸 예상 부대비용 합계</span><b>{format_price(final_costs['총부대비용'])}원</b></div>
      <div class="budget-row" style="font-size:0.72rem; color:var(--ink-muted);">
        <span>└ 취득세 {final_costs['취득세']:,}만 · 복비 {final_costs['중개보수']:,}만</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    filter_by_budget = st.sidebar.checkbox("🎯 내 예산 이하 단지만 필터링", value=True)
else:
    my_capital = 0
    max_affordable_price = None
    actual_loan_amount = 0
    monthly_payment = 0
    final_costs = {"총부대비용": 0}
    filter_by_budget = False
    st.sidebar.markdown(
        '<div class="sidebar-note">계산기를 켜면 보유 자본금 기준 최대 매수가·월 원리금과 취득세·복비를 정밀 계산합니다.</div>',
        unsafe_allow_html=True
    )

# ── 6. 메인 UI 및 계층형 지역 필터 ────────────────────────
st.markdown("""
<div class="hero-banner">
  <h1>🏠 전국 아파트 실거래가 및 내집마련 대시보드</h1>
  <p>국토교통부 매매·전세 실거래가 오픈 API 실시간 연동 · 전세가율 및 실투자 갭 분석</p>
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
        default_city_idx = city_options.index("수원시") if "수원시" in city_options else 1
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

with st.spinner(f"'{selected_sido} {scope_name} ({selected_gu if selected_sido == '경기도' else ''})' 매매 및 전세 실거래 데이터를 조회 중입니다..."):
    raw_df, raw_rent_df = fetch_all_target_records(tuple(target_codes_to_fetch), tuple(target_months))

if raw_df.empty:
    st.cache_data.clear()
    st.warning("국토교통부 API 서버 응답이 지연되었습니다. 사이드바의 [🔄 캐시 초기화 및 데이터 다시 불러오기]를 눌러주세요.")
    st.stop()

# ── [데이터 정제: 1. 통매입 제외 -> 2. 평형 산출] ─────────────
df = raw_df.copy()
rent_df = raw_rent_df.copy()

if filter_bulk_option:
    df = remove_bulk_acquisitions(df, threshold=10)

# 매매 데이터 평형 산출
pyeong_info = df['area'].apply(get_pyeong_group_key)
df['supply_pyeong'] = [p[0] for p in pyeong_info]
df['pyeong_label'] = [p[1] for p in pyeong_info]

# 전세 데이터 평형 산출
if not rent_df.empty:
    rent_pyeong_info = rent_df['area'].apply(get_pyeong_group_key)
    rent_df['supply_pyeong'] = [p[0] for p in rent_pyeong_info]

# 면적 필터 적용
if selected_quick_pyeong and len(selected_quick_pyeong) < len(quick_pyeong_options):
    condition_list = []
    for band in selected_quick_pyeong:
        p_min, p_max = PYEONG_BAND_MAP[band]
        condition_list.append((df['supply_pyeong'] >= p_min) & (df['supply_pyeong'] <= p_max))

    if condition_list:
        combined_cond = condition_list[0]
        for cond in condition_list[1:]:
            combined_cond = combined_cond | cond
        df = df[combined_cond].copy()

if area_unit == "공급평형":
    if slider_min_p > 0 or slider_max_p < 80:
        max_p_limit = slider_max_p if slider_max_p < 80 else 999.0
        df = df[(df['supply_pyeong'] >= slider_min_p) & (df['supply_pyeong'] <= max_p_limit)].copy()
else:
    if slider_min_m2 > 0 or slider_max_m2 < 250:
        max_m2_limit = slider_max_m2 if slider_max_m2 < 250 else 9999.0
        df = df[(df['area'] >= slider_min_m2) & (df['area'] <= max_m2_limit)].copy()

with col4:
    st.markdown('<div class="step-chip">4️⃣ 읍·면·동</div>', unsafe_allow_html=True)
    dong_list = ['전체 보기'] + sorted(list(df['dong'].unique())) if not df.empty else ['전체 보기']
    selected_dong = st.selectbox("읍·면·동", dong_list, label_visibility="collapsed")

view_df = df if selected_dong == '전체 보기' else df[df['dong'] == selected_dong]
view_rent_df = rent_df if (selected_dong == '전체 보기' or rent_df.empty) else rent_df[rent_df['dong'] == selected_dong]

if filter_by_budget and max_affordable_price is not None:
    affordable_df = view_df[view_df['price'] <= max_affordable_price]
    dong_rank_source = df[df['price'] <= max_affordable_price]
else:
    affordable_df = view_df
    dong_rank_source = df

# ── 7. 요약 통계 KPI 카드 ─────────────────────────────────
match_pct = (len(affordable_df) / len(view_df) * 100) if len(view_df) > 0 else 0

clean_price_deals = view_df[(view_df['floor'] > 3) & (view_df['deal_type'] != '직거래')]
if clean_price_deals.empty:
    clean_price_deals = view_df

avg_clean_price = int(clean_price_deals['price'].mean()) if len(clean_price_deals) > 0 else 0
apt_count = view_df['apt'].nunique() if len(view_df) > 0 else 0

if len(view_df) > 0:
    max_idx = view_df['price'].idxmax()
    max_row = view_df.loc[max_idx]
    max_price = int(max_row['price'])
    max_apt_desc = f"{max_row['apt']} ({max_row['dong']} · {int(max_row['supply_pyeong'])}평형)"
else:
    max_price = 0
    max_apt_desc = "조회 기간 내 최고가"

if calc_enabled:
    kpi_html = f"""
    <div class="kpi-grid-container">
        <div class="kpi-card">
            <div class="kpi-label">💵 최대 매수가</div>
            <div class="kpi-value accent">{format_price(max_affordable_price)}</div>
            <div class="kpi-sub muted">부대비용 {final_costs['총부대비용']:,}만 차감 반영</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">💳 필요 대출금</div>
            <div class="kpi-value">{format_price(actual_loan_amount)}</div>
            <div class="kpi-sub muted">LTV {ltv_rate}% · DSR 40% 한도 적용</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">🎯 매수 가능 거래</div>
            <div class="kpi-value">{len(affordable_df):,}건</div>
            <div class="kpi-sub">전체 {len(view_df):,}건 중 {match_pct:.1f}%</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">🏦 월 예상 원리금</div>
            <div class="kpi-value primary">{monthly_payment // 10000:,}만원</div>
            <div class="kpi-sub muted">금리 {loan_interest:.1f}% · {loan_term_years}년 만기</div>
        </div>
    </div>
    """
else:
    kpi_html = f"""
    <div class="kpi-grid-container">
        <div class="kpi-card">
            <div class="kpi-label">📊 전체 거래건수</div>
            <div class="kpi-value">{len(view_df):,}건</div>
            <div class="kpi-sub muted">해당 기간 전체 실거래 100%</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">💰 평균 실거래가</div>
            <div class="kpi-value accent">{format_price(avg_clean_price)}</div>
            <div class="kpi-sub muted">로열층 중개거래 기준</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">🏆 최고 실거래가</div>
            <div class="kpi-value">{format_price(max_price)}</div>
            <div class="kpi-sub muted" title="{html.escape(max_apt_desc)}">{html.escape(max_apt_desc)}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">🏘️ 거래 단지 수</div>
            <div class="kpi-value primary">{apt_count:,}개</div>
            <div class="kpi-sub muted">사이드바 계산기 지원</div>
        </div>
    </div>
    """

st.markdown(kpi_html, unsafe_allow_html=True)

# ── 8. 차트 및 동별 순위표 (차트 40% : 순위표 60%) ─────────────
c1, c2 = st.columns([2, 3])

display_title = f"{selected_sido} {scope_name}"
if selected_sido == "경기도" and selected_gu != f"{selected_city} 전체":
    display_title = f"{selected_city} {selected_gu}"
if selected_dong != '전체 보기':
    display_title += f" {selected_dong}"

with c1:
    st.markdown(f'<div class="section-title">📈 월별 거래량 추이</div>', unsafe_allow_html=True)
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
        margin=dict(l=6, r=6, t=10, b=10),
        height=290,
        font=dict(family="Pretendard, sans-serif", color="#52514e", size=11),
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
    rank_df = dong_rank_source.groupby(['city', 'gu', 'dong']).size().reset_index(name='거래건수')
    rank_df = rank_df.sort_values(by='거래건수', ascending=False)
    rank_df.columns = ['시·군', '구', '동·읍·면명', '거래건수']
    rank_df.index = range(1, len(rank_df) + 1)
    max_count = int(rank_df['거래건수'].max()) if len(rank_df) > 0 else 1
    st.dataframe(
        rank_df,
        use_container_width=True,
        height=270,
        column_config={
            "거래건수": st.column_config.ProgressColumn(
                "거래건수", format="%d건", min_value=0, max_value=max_count
            )
        }
    )

st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

# ── 9. 추천 단지 TOP 15 (전세가율 & 실투자 갭 통합 집계) ────────
if calc_enabled:
    st.markdown(
        f'<div class="section-title">🏆 내 예산({max_affordable_price // 10000}억 이하) 맞춤 실거래 추천 단지 TOP 15</div>',
        unsafe_allow_html=True
    )
else:
    st.markdown(f'<div class="section-title">🏆 {display_title} 실거래 인기 단지 TOP 15</div>', unsafe_allow_html=True)

if affordable_df.empty:
    st.info("현재 설정된 조건(면적/예산 필터)으로 매수 가능한 실거래 아파트가 없습니다.")
else:
    all_period_months = sorted(list(affordable_df['month'].unique()))
    early_fixed_months = all_period_months[:2] if len(all_period_months) >= 2 else all_period_months
    late_fixed_months = all_period_months[-2:] if len(all_period_months) >= 2 else all_period_months
    half_split_idx = max(1, len(all_period_months) // 2)
    first_half_months = all_period_months[:half_split_idx]

    # 전세 데이터 사전 집계 (단지+평형별 최근 전세가)
    rent_dict = {}
    if not view_rent_df.empty:
        # 저층 전세 제외 (시세 정밀화)
        clean_rent_df = view_rent_df[view_rent_df['floor'] > 3]
        if clean_rent_df.empty:
            clean_rent_df = view_rent_df

        for (c, g, d, a, p), r_group in clean_rent_df.groupby(['city', 'gu', 'dong', 'apt', 'supply_pyeong']):
            # 최근 전세 거래 우선
            r_recent = r_group[r_group['month'].isin(late_fixed_months)]
            if not r_recent.empty:
                r_price = r_recent['deposit'].mean()
            else:
                r_latest_month = r_group['month'].max()
                r_price = r_group[r_group['month'] == r_latest_month]['deposit'].mean()
            rent_dict[(c, g, d, a, p)] = int(r_price)

    def aggregate_apt_metrics(group):
        total_count = len(group)
        max_price_val = group['price'].max()
        mean_area = group['area'].mean()
        
        # 1. 매매 가격 정제 (저층·직거래 제외)
        clean_group = group[(group['floor'] > 3) & (group['deal_type'] != '직거래')]
        if clean_group.empty:
            clean_group = group

        # 2. 최근 실거래가 산출
        recent_deals = clean_group[clean_group['month'].isin(late_fixed_months)]
        if not recent_deals.empty:
            recent_mean = recent_deals['price'].mean()
        else:
            latest_month_of_apt = clean_group['month'].max()
            recent_mean = clean_group[clean_group['month'] == latest_month_of_apt]['price'].mean()

        # 3. 5~6개월 전 초기 기준 시세 산출
        base_deals = clean_group[clean_group['month'].isin(early_fixed_months)]
        if not base_deals.empty:
            base_mean = base_deals['price'].mean()
        else:
            first_half_deals = clean_group[clean_group['month'].isin(first_half_months)]
            if not first_half_deals.empty:
                base_mean = first_half_deals['price'].mean()
            else:
                earliest_month_of_apt = clean_group['month'].min()
                base_mean = clean_group[clean_group['month'] == earliest_month_of_apt]['price'].mean()

        # 4. 6개월 전 대비 시세 변동률(모멘텀)
        if base_mean > 0:
            trend_rate = ((recent_mean - base_mean) / base_mean) * 100
        else:
            trend_rate = 0.0

        # 5. 전세가 및 갭 매칭
        c_val = group['city'].iloc[0]
        g_val = group['gu'].iloc[0]
        d_val = group['dong'].iloc[0]
        a_val = group['apt'].iloc[0]
        p_val = group['supply_pyeong'].iloc[0]

        rent_val = rent_dict.get((c_val, g_val, d_val, a_val, p_val), None)
        if rent_val and rent_val > 0:
            jeonse_rate = (rent_val / recent_mean) * 100
            gap_price = recent_mean - rent_val
        else:
            jeonse_rate = None
            gap_price = None

        return pd.Series({
            '거래건수': total_count,
            '최근실거래가': recent_mean,
            '초기기준시세': base_mean,
            '변동률': trend_rate,
            '조회기간최고가': max_price_val,
            '최근전세가': rent_val,
            '전세가율': jeonse_rate,
            '실투자갭': gap_price,
            '전용면적_평균': mean_area
        })

    apt_rank = affordable_df.groupby(['city', 'gu', 'dong', 'apt', 'supply_pyeong']).apply(
        aggregate_apt_metrics
    ).reset_index()

    apt_rank['상태배지'] = apt_rank['변동률'].apply(get_trend_badge)

    apt_rank = apt_rank.sort_values(by='거래건수', ascending=False).head(15).reset_index(drop=True)

    apt_rank['최근실거래가_fmt'] = apt_rank['최근실거래가'].astype(int).apply(format_price)
    apt_rank['조회기간최고가_fmt'] = apt_rank['조회기간최고가'].astype(int).apply(format_price)
    apt_rank['최근전세가_fmt'] = apt_rank['최근전세가'].apply(lambda x: format_price(x) if pd.notna(x) else "-")
    apt_rank['실투자갭_fmt'] = apt_rank['실투자갭'].apply(lambda x: format_price(x) if pd.notna(x) else "-")
    apt_rank['전세가율_fmt'] = apt_rank['전세가율'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "-")
    apt_rank['전용면적_평형'] = apt_rank['전용면적_평균'].apply(
        lambda x: f"{x:.1f}㎡ ({int(round((x/3.30578)/0.745))}평형)"
    )

    medals = ['🥇', '🥈', '🥉']
    top3 = apt_rank.head(3)
    if len(top3) > 0:
        top_cols = st.columns(len(top3))
        for i, (_, row) in enumerate(top3.iterrows()):
            apt_name = html.escape(str(row['apt']))
            loc_txt = html.escape(f"{row['city']} {row['gu']} {row['dong']} · {row['전용면적_평형']}")
            trend_badge_html = row['상태배지']
            
            # 전세 및 갭 텍스트 생성
            if row['전세가율_fmt'] != "-":
                gap_html = f"""
                <div class="rank-gap-box">
                    전세 {row['최근전세가_fmt']} (전세가율 {row['전세가율_fmt']} · 갭 {row['실투자갭_fmt']})
                </div>
                """
            else:
                gap_html = """<div class="rank-gap-box" style="color:var(--ink-muted); border-color:var(--border-hairline);">최근 전세 거래 없음</div>"""

            with top_cols[i]:
                st.markdown(f"""<div class="rank-card">
                    <div>
                        <div class="rank-badge">{medals[i]}</div>
                        <div class="rank-apt">{apt_name}</div>
                        <div class="rank-loc">{loc_txt}</div>
                        <div>{trend_badge_html}</div>
                        <div class="rank-price">{row['최근실거래가_fmt']}원</div>
                        <div class="rank-meta">총 {int(row['거래건수'])}건 거래 · 최고가 {row['조회기간최고가_fmt']}원</div>
                    </div>
                    {gap_html}
                </div>""", unsafe_allow_html=True)
        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)

    # 4위 이하 단지 표
    rest = apt_rank.iloc[3:].copy()
    if not rest.empty:
        def format_trend_text(val):
            if val >= 5.0:
                return f"🔥 급상승 (+{val:.1f}%)"
            elif val >= 1.0:
                return f"📈 상승 (+{val:.1f}%)"
            elif val > -1.0:
                return f"➖ 보합 ({val:+.1f}%)"
            elif val > -5.0:
                return f"📉 조정 ({val:.1f}%)"
            else:
                return f"🧊 급락 ({val:.1f}%)"

        rest['6개월시세변동'] = rest['변동률'].apply(format_trend_text)
        rest['거래건수'] = rest['거래건수'].astype(int)

        rest_display = rest[[
            'city', 'gu', 'dong', 'apt', '전용면적_평형', '거래건수', 
            '최근실거래가_fmt', '최근전세가_fmt', '전세가율_fmt', '실투자갭_fmt', '6개월시세변동'
        ]].copy()
        rest_display.columns = [
            '시·군', '구', '법정동', '단지명', '면적(공급평형)', '거래건수', 
            '최근 매매가', '최근 전세가', '전세가율', '실투자 갭', '6개월 변동'
        ]
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
