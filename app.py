import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ── 1. 페이지 기본 설정 ──────────────────────────────────
st.set_page_config(
    page_title="전국 아파트 실거래 거래량 대시보드",
    page_icon="🏢",
    layout="wide"
)

# ── 2. 기본 상수 및 전국 법정동 시·군·구 코드 매핑 ───────
DECODING_KEY = 'HFLjN2wHoX4g3U2XNaBnhqTWwhmqxMqr9B2TcPbOZV9dJn8xZlFtiiymS0QNo7vbQEnk744KO+byEhW7SOucBA=='
BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

# 전국 주요 시·도 및 시·군·구 5자리 LAWD_CD
NATIONWIDE_REGIONS = {
    "경기도": {
        "수원시 영통구": "41117", "수원시 장안구": "41111", "수원시 권선구": "41113", "수원시 팔달구": "41115",
        "성남시 분당구": "41135", "성남시 수정구": "41131", "성남시 중원구": "41133",
        "용인시 수지구": "41465", "용인시 기흥구": "41463", "용인시 처인구": "41461",
        "안양시 동안구": "41173", "안양시 만안구": "41171",
        "고양시 일산동구": "41285", "고양시 일산서구": "41287", "고양시 덕양구": "41281",
        "안산시 단원구": "41273", "안산시 상록구": "41271",
        "화성시": "41590", "평택시": "41220", "하남시": "41450", "남양주시": "41360",
        "부천시": "41190", "시흥시": "41390", "파주시": "41480", "김포시": "41570",
        "광명시": "41210", "군포시": "41410", "오산시": "41370", "이천시": "41500",
        "양주시": "41630", "구리시": "41310", "안성시": "41550", "포천시": "41650",
        "의왕시": "41430", "여주시": "41670", "동두천시": "41250", "과천시": "41290",
        "가평군": "41820", "양평군": "41830", "연천군": "41800"
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
    },
    "충청남도": {
        "천안시 서북구": "44133", "천안시 동남구": "44131", "아산시": "44200",
        "서산시": "44210", "당진시": "44270", "공주시": "44150", "논산시": "44230"
    },
    "충청북도": {
        "청주시 흥덕구": "43113", "청주시 청원구": "43114", "청주시 상당구": "43111",
        "청주시 서원구": "43112", "충주시": "43130", "제천시": "43150"
    },
    "경상남도": {
        "창원시 성산구": "48123", "창원시 의창구": "48121", "창원시 마산회원구": "48127",
        "김해시": "48250", "양산시": "48330", "진주시": "48170", "거제시": "48310"
    },
    "경상북도": {
        "포항시 남구": "47111", "포항시 북구": "47113", "구미시": "47190",
        "경산시": "47290", "경주시": "47130", "안동시": "47170", "김천시": "47150"
    },
    "전북특별자치도": {
        "전주시 덕진구": "45113", "전주시 완산구": "45111", "익산시": "45140", "군산시": "45130"
    },
    "전라남도": {
        "순천시": "46150", "여수시": "46130", "광양시": "46230", "목포시": "46110", "나주시": "46170"
    },
    "강원특별자치도": {
        "원주시": "51130", "춘천시": "51110", "강릉시": "51150", "속초시": "51210"
    },
    "제주특별자치도": {
        "제주시": "50110", "서귀포시": "50130"
    }
}

# ── 3. 선택 지역 데이터 온디맨드 수집 & 캐싱 ───────────────
@st.cache_data(ttl=86400)
def fetch_region_data(lawd_cd: str, sido: str, sigungu: str):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # 현재 시점 기준 최근 6개월 생성
    now = datetime.now()
    target_months = []
    for i in range(5, -1, -1):
        target_date = now - relativedelta(months=i)
        target_months.append(target_date.strftime('%Y%m'))

    records = []
    for deal_ymd in target_months:
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
                res = requests.get(BASE_URL, params=params, headers=headers, timeout=15)
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
                    
                    # 계약 해제 거래 제외
                    if r.get('cdealType', '') == 'O' or r.get('cdealDay', '') != '':
                        continue
                    
                    records.append({
                        'sido': sido,
                        'sigungu': sigungu,
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

    return pd.DataFrame(records)


# ── 4. UI 및 필터 구성 ───────────────────────────────────
st.title("📊 전국 동네별 아파트 실거래 거래량 대시보드")
st.caption("국토교통부 실거래가 오픈 API 실시간 연동 (선택 지역 실시간 수집 및 24시간 캐싱)")

# [3단 연계 필터]
col_sido, col_sigungu, col_dong = st.columns(3)

with col_sido:
    sido_list = list(NATIONWIDE_REGIONS.keys())
    # 기본값: 경기도
    default_sido_idx = sido_list.index("경기도") if "경기도" in sido_list else 0
    selected_sido = st.selectbox("1️⃣ 시·도 선택", sido_list, index=default_sido_idx)

with col_sigungu:
    sigungu_dict = NATIONWIDE_REGIONS[selected_sido]
    sigungu_list = list(sigungu_dict.keys())
    # 기본값: 수원시 영통구
    default_sig_idx = sigungu_list.index("수원시 영통구") if "수원시 영통구" in sigungu_list else 0
    selected_sigungu = st.selectbox("2️⃣ 시·군·구 선택", sigungu_list, index=default_sig_idx)

selected_lawd_cd = sigungu_dict[selected_sigungu]

# 선택한 시·군·구 데이터 로드
with st.spinner(f"'{selected_sido} {selected_sigungu}' 실거래 데이터를 조회 중입니다..."):
    df = fetch_region_data(selected_lawd_cd, selected_sido, selected_sigungu)

with col_dong:
    if not df.empty:
        dong_list = ['전체 보기'] + sorted(list(df['dong'].unique()))
    else:
        dong_list = ['전체 보기']
    selected_dong = st.selectbox("3️⃣ 읍·면·동 선택", dong_list)

if df.empty:
    st.warning(f"선택하신 '{selected_sido} {selected_sigungu}'의 최근 6개월 거래 내역이 없거나 데이터를 불러올 수 없습니다.")
    st.stop()

# 동 선택에 따른 필터링
view_df = df if selected_dong == '전체 보기' else df[df['dong'] == selected_dong]

# ── 5. 상단 핵심 통계 카드 ─────────────────────────────────
dong_counts = df['dong'].value_counts()
top_dong_name = dong_counts.index[0] if not dong_counts.empty else '-'
top_dong_val = dong_counts.iloc[0] if not dong_counts.empty else 0
top_dong_pct = (top_dong_val / len(df) * 100) if len(df) > 0 else 0

m1, m2, m3 = st.columns(3)
m1.metric("🔥 최다 거래 지역 (1위)", f"{top_dong_name}", f"{top_dong_val:,}건 ({top_dong_pct:.1f}%)")
m2.metric("📦 선택 조건 누적 거래량", f"{len(view_df):,}건")
m3.metric("🏢 구 내 집계 동 개수", f"{len(dong_counts):,}개 동")

st.divider()

# ── 6. 월별 추이 차트 및 동별 순위표 ──────────────────────
c1, c2 = st.columns([3, 2])

with c1:
    chart_title = f"{selected_sigungu}" if selected_dong == '전체 보기' else f"{selected_sigungu} {selected_dong}"
    st.subheader(f"📈 {chart_title} 월별 거래량 추이")
    monthly_series = view_df['month'].value_counts().sort_index()
    st.bar_chart(monthly_series)

with c2:
    st.subheader(f"🥇 {selected_sigungu} 동별 거래량 순위")
    rank_df = dong_counts.reset_index()
    rank_df.columns = ['동명', '거래건수']
    rank_df.index = rank_df.index + 1
    st.dataframe(rank_df, use_container_width=True, height=290)

st.divider()

# ── 7. 주요 아파트 단지 거래 순위 (TOP 10) ─────────────────
st.subheader(f"🏆 {chart_title} 주요 아파트 단지 순위 (TOP 10)")
apt_rank = view_df.groupby(['sigungu', 'dong', 'apt']).agg(
    거래건수=('price', 'count'),
    평균거래가_만원=('price', 'mean'),
    최고가_만원=('price', 'max')
).reset_index()

apt_rank = apt_rank.sort_values(by='거래건수', ascending=False).head(10)
apt_rank['평균거래가_만원'] = apt_rank['평균거래가_만원'].astype(int).apply(lambda x: f"{x:,}")
apt_rank['최고가_만원'] = apt_rank['최고가_만원'].apply(lambda x: f"{x:,}")
apt_rank.columns = ['시·군·구', '법정동', '단지명', '거래건수', '평균 거래가(만원)', '최고 거래가(만원)']
apt_rank.index = range(1, len(apt_rank) + 1)

st.dataframe(apt_rank, use_container_width=True)
