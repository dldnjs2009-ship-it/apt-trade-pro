import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ── 1. 페이지 기본 설정 ──────────────────────────────────
st.set_page_config(
    page_title="수원시 아파트 실거래 거래량 대시보드",
    page_icon="📊",
    layout="wide"
)

# ── 2. 기본 상수 및 설정 ──────────────────────────────────
DECODING_KEY = 'HFLjN2wHoX4g3U2XNaBnhqTWwhmqxMqr9B2TcPbOZV9dJn8xZlFtiiymS0QNo7vbQEnk744KO+byEhW7SOucBA=='
BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

SUWON_REGIONS = {
    '41111': '장안구',
    '41113': '권선구',
    '41115': '팔달구',
    '41117': '영통구'
}

# ── 3. 데이터 자동 수집 및 캐싱 (24시간 주기 갱신) ─────────
@st.cache_data(ttl=86400)
def load_suwon_data():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # 현재 날짜 기준 최근 6개월 YYYYMM 목록 동적 생성
    now = datetime.now()
    target_months = []
    for i in range(5, -1, -1):
        target_date = now - relativedelta(months=i)
        target_months.append(target_date.strftime('%Y%m'))
    
    records = []
    for lawd_cd, gu in SUWON_REGIONS.items():
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
                    
                    # 응답 검증
                    result_code = root.find('.//resultCode')
                    if result_code is not None and result_code.text not in ['00', '000']:
                        break

                    total_tag = root.find('.//totalCount')
                    total = int(total_tag.text) if total_tag is not None and total_tag.text else 0
                    
                    items = root.findall('.//item')
                    for item in items:
                        r = {child.tag: (child.text.strip() if child.text else '') for child in item}
                        
                        # 취소/해제 거래 제외
                        if r.get('cdealType', '') == 'O' or r.get('cdealDay', '') != '':
                            continue
                        
                        records.append({
                            'sido': '경기도',
                            'city': '수원시',
                            'gu': gu,
                            'dong': r.get('umdNm', ''),
                            'apt': r.get('aptNm', ''),
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

# ── 4. 대시보드 UI 및 통계 렌더링 ──────────────────────────
st.title("📊 수원시 동네별 아파트 실거래 거래량 대시보드")
st.caption("국토교통부 실거래가 오픈 API 실시간 연동 (매일 자동 갱신)")

with st.spinner("국토교통부 최신 실거래 데이터를 불러오는 중입니다..."):
    df = load_suwon_data()

if df.empty:
    st.error("데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")
    st.stop()

# [필터 영역]
col_f1, col_f2 = st.columns(2)
with col_f1:
    gu_list = ['수원시 전체'] + sorted(list(df['gu'].unique()))
    selected_gu = st.selectbox("구 선택", gu_list)

filtered_by_gu = df if selected_gu == '수원시 전체' else df[df['gu'] == selected_gu]

with col_f2:
    dong_list = ['전체 보기'] + sorted(list(filtered_by_gu['dong'].unique()))
    selected_dong = st.selectbox("동 선택", dong_list)

view_df = filtered_by_gu if selected_dong == '전체 보기' else filtered_by_gu[filtered_by_gu['dong'] == selected_dong]

# [상단 핵심 요약 메트릭 카드]
dong_counts = filtered_by_gu['dong'].value_counts()
top_dong_name = dong_counts.index[0] if not dong_counts.empty else '-'
top_dong_val = dong_counts.iloc[0] if not dong_counts.empty else 0
top_dong_pct = (top_dong_val / len(filtered_by_gu) * 100) if len(filtered_by_gu) > 0 else 0

m1, m2, m3 = st.columns(3)
m1.metric("🔥 선택 구역 최다 거래 지역 (1위)", f"{top_dong_name}", f"{top_dong_val:,}건 ({top_dong_pct:.1f}%)")
m2.metric("📦 선택 조건 누적 거래량", f"{len(view_df):,}건")
m3.metric("🏢 집계 대상 동 개수", f"{len(dong_counts):,}개 동")

st.divider()

# [차트 & 동별 순위표 (2단 그리드)]
c1, c2 = st.columns([3, 2])

with c1:
    title_target = (selected_gu if selected_dong == '전체 보기' else f"{selected_gu} {selected_dong}")
    st.subheader(f"📈 {title_target} 월별 거래량 추이")
    monthly_series = view_df['month'].value_counts().sort_index()
    st.bar_chart(monthly_series)

with c2:
    st.subheader("🥇 동별 거래량 순위")
    rank_df = dong_counts.reset_index()
    rank_df.columns = ['동명', '거래건수']
    rank_df.index = rank_df.index + 1
    st.dataframe(rank_df, use_container_width=True, height=290)

st.divider()

# [주요 아파트 단지 순위 (TOP 10)]
st.subheader("🏆 선택 지역 주요 단지 거래 순위 (TOP 10)")
apt_rank = view_df.groupby(['gu', 'dong', 'apt']).size().reset_index(name='거래건수')
apt_rank = apt_rank.sort_values(by='거래건수', ascending=False).head(10)
apt_rank.columns = ['구', '법정동', '단지명', '거래건수']
apt_rank.index = range(1, len(apt_rank) + 1)
st.dataframe(apt_rank, use_container_width=True)
