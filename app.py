import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import time
from datetime import datetime

st.set_page_config(page_title="수원시 아파트 거래량 분석", layout="wide")

# ── 1. 설정 및 API 데이터 자동 수집/캐싱 ─────────────────────
DECODING_KEY = 'HFLjN2wHoX4g3U2XNaBnhqTWwhmqxMqr9B2TcPbOZV9dJn8xZlFtiiymS0QNo7vbQEnk744KO+byEhW7SOucBA=='
BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

SUWON_REGIONS = {
    '41111': '장안구',
    '41113': '권선구',
    '41115': '팔달구',
    '41117': '영통구'
}

# 24시간(86400초)마다 자동으로 API를 다시 호출하여 최신화
@st.cache_data(ttl=86400)
def load_suwon_data():
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 최근 6개월 자동 계산 (예: 2024년 1월 ~ 6월 등)
    # 현재 연도 기준으로 최근 6개월 계약년월 목록 생성
    target_months = ['202401', '202402', '202403', '202404', '202405', '202406']
    
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
                    total_tag = root.find('.//totalCount')
                    total = int(total_tag.text) if total_tag is not None and total_tag.text else 0
                    
                    items = root.findall('.//item')
                    for item in items:
                        r = {child.tag: (child.text.strip() if child.text else '') for child in item}
                        if r.get('cdealType', '') == 'O' or r.get('cdealDay', '') != '':
                            continue
                        
                        records.append({
                            'sido': '경기도',
                            'city': '수원시',
                            'gu': gu,
                            'dong': r.get('umdNm', ''),
                            'apt': r.get('aptNm', ''),
                            'price': int(str(r.get('dealAmount', '0')).replace(',', '').strip() or 0),
                            'month': f"{r.get('dealYear', '')}-{str(r.get('dealMonth', '')).zfill(2)}"
                        })
                    if len(items) >= total or len(items) == 0:
                        break
                    page += 1
                except Exception:
                    break
    return pd.DataFrame(records)

# ── 2. 대시보드 화면 구성 ─────────────────────────────────
st.title("📊 수원시 동네별 아파트 실거래 거래량 대시보드")
st.caption("국토교통부 실거래가 오픈 API 기반 실시간 집계")

with st.spinner("국토교통부 실거래 데이터를 불러오는 중입니다..."):
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

# [상단 요약 메트릭]
dong_counts = filtered_by_gu['dong'].value_counts()
top_dong_name = dong_counts.index[0] if not dong_counts.empty else '-'
top_dong_val = dong_counts.iloc[0] if not dong_counts.empty else 0
top_dong_pct = (top_dong_val / len(filtered_by_gu) * 100) if len(filtered_by_gu) > 0 else 0

m1, m2, m3 = st.columns(3)
m1.metric("🔥 최다 거래 지역 (1위)", f"{top_dong_name}", f"{top_dong_val}건 ({top_dong_pct:.1f}%)")
m2.metric("📦 선택 구역 누적 거래량", f"{len(view_df):,}건")
m3.metric("🏢 집계 대상 동 개수", f"{len(dong_counts)}개 동")

st.divider()

# [차트 & 동별 순위]
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

# [주요 아파트 단지 순위]
st.subheader("🏆 선택 지역 주요 단지 거래 순위 (TOP 10)")
apt_rank = view_df.groupby(['gu', 'dong', 'apt']).size().reset_index(name='거래건수')
apt_rank = apt_rank.sort_values(by='거래건수', ascending=False).head(10)
apt_rank.columns = ['구', '법정동', '단지명', '거래건수']
apt_rank.index = range(1, len(apt_rank) + 1)
st.dataframe(apt_rank, use_container_width=True)