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

# ── 2. 기본 상수 및 계층형 전국 지역 코드 매핑 ──────────
DECODING_KEY = 'HFLjN2wHoX4g3U2XNaBnhqTWwhmqxMqr9B2TcPbOZV9dJn8xZlFtiiymS0QNo7vbQEnk744KO+byEhW7SOucBA=='
BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

NATIONWIDE_REGIONS = {
    "경기도": {
        "수원시": {"영통구": "41117", "장안구": "41111", "권선구": "41113", "팔달구": "41115"},
        "성남시": {"분당구": "41135", "수정구": "41131", "중원구": "41133"},
        "용인시": {"수지구": "41465", "기흥구": "41463", "처인구": "41461"},
        "고양시": {"일산동구": "41285", "일산서구": "41287", "덕양구": "41281"},
        "안양시": {"동안구": "41173", "만안구": "41171"},
        "안산시": {"단원구": "41273", "상록구": "41271"},
        "부천시": {"원미구": "41192", "소사구": "41194", "오정구": "41196"},
        "화성시": {"전체 (구 없음)": "41590"},
        "평택시": {"전체 (구 없음)": "41220"},
        "남양주시": {"전체 (구 없음)": "41360"},
        "하남시": {"전체 (구 없음)": "41450"},
        "시흥시": {"전체 (구 없음)": "41390"},
        "파주시": {"전체 (구 없음)": "41480"},
        "김포시": {"전체 (구 없음)": "41570"},
        "광명시": {"전체 (구 없음)": "41210"},
        "군포시": {"전체 (구 없음)": "41410"},
        "오산시": {"전체 (구 없음)": "41370"},
        "이천시": {"전체 (구 없음)": "41500"},
        "구리시": {"전체 (구 없음)": "41310"},
        "안성시": {"전체 (구 없음)": "41550"},
        "의왕시": {"전체 (구 없음)": "41430"},
        "양주시": {"전체 (구 없음)": "41630"},
        "포천시": {"전체 (구 없음)": "41650"},
        "여주시": {"전체 (구 없음)": "41670"},
        "동두천시": {"전체 (구 없음)": "41250"},
        "과천시": {"전체 (구 없음)": "41290"},
        "가평군": {"전체 (구 없음)": "41820"},
        "양평군": {"전체 (구 없음)": "41830"},
        "연천군": {"전체 (구 없음)": "41800"}
    },
    "서울특별시": {
        "서울특별시": {
            "강남구": "11680", "서초구": "11650", "송파구": "11710", "강동구": "11740",
            "마포구": "11440", "용산구": "11170", "성동구": "11200", "광진구": "11215",
            "영등포구": "11560", "양천구": "11470", "동작구": "11590", "관악구": "11620",
            "강서구": "11500", "구로구": "11530", "금천구": "11545", "서대문구": "11410",
            "동대문구": "11230", "성북구": "11290", "노원구": "11350", "도봉구": "11320",
            "강북구": "11305", "중랑구": "11260", "은평구": "11380", "종로구": "11110", "중구": "11140"
        }
    },
    "인천광역시": {
        "인천광역시": {
            "연수구": "28185", "남동구": "28200", "서구": "28260", "부평구": "28237",
            "미추홀구": "28177", "계양구": "28245", "중구": "28110", "동구": "28140", "강화군": "28710"
        }
    },
    "부산광역시": {
        "부산광역시": {
            "해운대구": "26350", "수영구": "26500", "남구": "26290", "동래구": "26260",
            "부산진구": "26230", "연제구": "26470", "금정구": "26410", "북구": "26320",
            "사하구": "26380", "강서구": "26440", "사상구": "26530", "기장군": "26710"
        }
    },
    "대구광역시": {
        "대구광역시": {
            "수성구": "27260", "달서구": "27290", "중구": "27110", "동구": "27140",
            "서구": "27170", "남구": "27200", "북구": "27230", "달성군": "27710"
        }
    },
    "대전광역시": {
        "대전광역시": {
            "유성구": "30200", "서구": "30170", "중구": "30140", "동구": "30110", "대덕구": "30230"
        }
    },
    "광주광역시": {
        "광주광역시": {
            "광산구": "29200", "서구": "29140", "남구": "29150", "북구": "29170", "동구": "29110"
        }
    },
    "울산광역시": {
        "울산광역시": {
            "남구": "31140", "중구": "31110", "북구": "31200", "동구": "31170", "울주군": "31710"
        }
    },
    "세종특별자치시": {
        "세종특별자치시": {"세종시": "36110"}
    },
    "충청남도": {
        "천안시": {"서북구": "44133", "동남구": "44131"},
        "아산시": {"전체 (구 없음)": "44200"},
        "서산시": {"전체 (구 없음)": "44210"},
        "당진시": {"전체 (구 없음)": "44270"}
    },
    "충청북도": {
        "청주시": {"흥덕구": "43113", "청원구": "43114", "상당구": "43111", "서원구": "43112"},
        "충주시": {"전체 (구 없음)": "43130"}
    },
    "경상남도": {
        "창원시": {"성산구": "48123", "의창구": "48121", "마산회원구": "48127", "마산합포구": "48125", "진해구": "48129"},
        "김해시": {"전체 (구 없음)": "48250"},
        "양산시": {"전체 (구 없음)": "48330"},
        "진주시": {"전체 (구 없음)": "48170"}
    },
    "경상북도": {
        "포항시": {"남구": "47111", "북구": "47113"},
        "구미시": {"전체 (구 없음)": "47190"},
        "경산시": {"전체 (구 없음)": "47290"},
        "경주시": {"전체 (구 없음)": "47130"}
    },
    "전북특별자치도": {
        "전주시": {"덕진구": "45113", "완산구": "45111"},
        "익산시": {"전체 (구 없음)": "45140"},
        "군산시": {"전체 (구 없음)": "45130"}
    },
    "전라남도": {
        "순천시": {"전체 (구 없음)": "46150"},
        "여수시": {"전체 (구 없음)": "46130"},
        "광양시": {"전체 (구 없음)": "46230"},
        "목포시": {"전체 (구 없음)": "46110"}
    },
    "강원특별자치도": {
        "원주시": {"전체 (구 없음)": "51130"},
        "춘천시": {"전체 (구 없음)": "51110"},
        "강릉시": {"전체 (구 없음)": "51150"}
    },
    "제주특별자치도": {
        "제주시": {"전체 (구 없음)": "50110"},
        "서귀포시": {"전체 (구 없음)": "50130"}
    }
}

# ── 3. 단일 월/구 고속 수집 단위 함수 ─────────────────────
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


# ── 4. 멀티스레딩 병렬 수집 & 캐싱 (속도 극대화) ───────────
@st.cache_data(ttl=86400)
def fetch_parallel_region_data(sido: str, city: str, gu_target_dict: dict):
    now = datetime.now()
    target_months = [(now - relativedelta(months=i)).strftime('%Y%m') for i in range(5, -1, -1)]

    # 모든 구 × 모든 월 조합의 작업 큐 생성
    tasks = []
    for g_name, code in gu_target_dict.items():
        for deal_ymd in target_months:
            tasks.append((code, deal_ymd, sido, city, g_name))

    all_records = []
    # 최대 12개 스레드로 동시 요청 전송
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(fetch_single_month_task, *task) for task in tasks]
        for future in as_completed(futures):
            try:
                res = future.result()
                if res:
                    all_records.extend(res)
            except Exception:
                pass

    return pd.DataFrame(all_records)


# ── 5. UI 및 4단계 필터 구성 ──────────────────────────────
st.title("📊 전국 동네별 아파트 실거래 거래량 대시보드")
st.caption("국토교통부 실거래가 오픈 API 연동 (멀티스레딩 고속 병렬 수집 & 24시간 캐싱)")

col_sido, col_city, col_gu, col_dong = st.columns(4)

with col_sido:
    sido_list = list(NATIONWIDE_REGIONS.keys())
    default_sido_idx = sido_list.index("경기도") if "경기도" in sido_list else 0
    selected_sido = st.selectbox("1️⃣ 시·도", sido_list, index=default_sido_idx)

with col_city:
    city_dict = NATIONWIDE_REGIONS[selected_sido]
    city_list = list(city_dict.keys())
    default_city_idx = city_list.index("수원시") if "수원시" in city_list else 0
    selected_city = st.selectbox("2️⃣ 시·군", city_list, index=default_city_idx)

gu_dict = city_dict[selected_city]
gu_keys = list(gu_dict.keys())

with col_gu:
    if len(gu_keys) > 1:
        gu_options = [f"{selected_city} 전체"] + gu_keys
    else:
        gu_options = gu_keys
    selected_gu = st.selectbox("3️⃣ 구", gu_options)

# 병렬 수집 대상 딕셔너리 결정
if selected_gu == f"{selected_city} 전체":
    target_gu_dict = gu_dict
else:
    target_gu_dict = {selected_gu: gu_dict[selected_gu]}

with st.spinner(f"'{selected_sido} {selected_city} ({selected_gu})' 실거래 데이터를 고속 수집 중입니다..."):
    df = fetch_parallel_region_data(selected_sido, selected_city, target_gu_dict)

with col_dong:
    if not df.empty:
        dong_list = ['전체 보기'] + sorted(list(df['dong'].unique()))
    else:
        dong_list = ['전체 보기']
    selected_dong = st.selectbox("4️⃣ 읍·면·동", dong_list)

if df.empty:
    st.warning(f"선택하신 지역의 최근 6개월 거래 내역이 없거나 데이터를 불러올 수 없습니다.")
    st.stop()

view_df = df if selected_dong == '전체 보기' else df[df['dong'] == selected_dong]

# ── 6. 상단 요약 통계 카드 ─────────────────────────────────
if selected_gu == f"{selected_city} 전체":
    dong_counts = df.groupby(['gu', 'dong']).size().sort_values(ascending=False)
    top_label = f"{dong_counts.index[0][1]} ({dong_counts.index[0][0]})" if not dong_counts.empty else '-'
    top_val = dong_counts.iloc[0] if not dong_counts.empty else 0
    total_dong_count = len(dong_counts)
else:
    dong_counts = df['dong'].value_counts()
    top_label = f"{dong_counts.index[0]}" if not dong_counts.empty else '-'
    top_val = dong_counts.iloc[0] if not dong_counts.empty else 0
    total_dong_count = len(dong_counts)

top_pct = (top_val / len(df) * 100) if len(df) > 0 else 0

m1, m2, m3 = st.columns(3)
m1.metric("🔥 최다 거래 지역 (1위)", f"{top_label}", f"{top_val:,}건 ({top_pct:.1f}%)")
m2.metric("📦 선택 조건 누적 거래량", f"{len(view_df):,}건")
m3.metric("🏢 구역 내 집계 동 개수", f"{total_dong_count:,}개 동")

st.divider()

# ── 7. 월별 거래량 추이 차트 및 동별 순위표 ──────────────
c1, c2 = st.columns([3, 2])

if selected_gu == f"{selected_city} 전체":
    scope_title = f"{selected_city} 전체"
elif selected_gu == "전체 (구 없음)":
    scope_title = f"{selected_city}"
else:
    scope_title = f"{selected_city} {selected_gu}"

if selected_dong != '전체 보기':
    scope_title += f" {selected_dong}"

with c1:
    st.subheader(f"📈 {scope_title} 월별 거래량 추이")
    monthly_series = view_df['month'].value_counts().sort_index()
    st.bar_chart(monthly_series)

with c2:
    st.subheader(f"🥇 동별 거래량 순위")
    if selected_gu == f"{selected_city} 전체":
        rank_df = dong_counts.reset_index()
        rank_df.columns = ['구', '동명', '거래건수']
    else:
        rank_df = dong_counts.reset_index()
        rank_df.columns = ['동명', '거래건수']
    rank_df.index = range(1, len(rank_df) + 1)
    st.dataframe(rank_df, use_container_width=True, height=290)

st.divider()

# ── 8. 주요 아파트 단지 순위 (TOP 10) ─────────────────
st.subheader(f"🏆 {scope_title} 주요 아파트 단지 순위 (TOP 10)")
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
