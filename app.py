import streamlit as st
import yfinance as yf
import pandas as pd
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import datetime
import plotly.graph_objects as go
import requests
import json

# --- 기본 페이지 설정 ---
st.set_page_config(
    page_title="주식 진단 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
# --- KIS OpenAPI 인증 키 (보안 적용) ---
try:
    # Streamlit Cloud의 Secrets(비밀 금고)에 저장된 값을 우선적으로 가져옵니다.
    APP_KEY = st.secrets["KIS_APP_KEY"]
    APP_SECRET = st.secrets["KIS_APP_SECRET"]
except FileNotFoundError:
    # 주의: 깃허브가 'Public(공개)' 상태라면, 해커가 이 키를 훔쳐 쓸 수 있으므로 매우 위험합니다!!
    # 가급적 빨리 이 아래 두 줄을 지우고 st.secrets만 쓰도록 하시는 것이 좋습니다.
    APP_KEY = "PSSpT74p43VgT6Rn24Y4NlqAg8m8eF6vmBzD"
    APP_SECRET = "ZiNUtohv5bzjidzP54uZ+GH3/jZ8U9+SU2SJr4g9uLLOocmdNFEGvjQ3iWqxLqTsdoZOUv3ZZx2Aj1fl9Oez54DapzbHh9+FAGn15rF6MV9R5iiYO8qnDxq4gjuRGGToaB3Ewqv46McrV9MLc10q2PonKNwOAyjsxbKUvtWIL5NMIlXcR3o="
def get_kis_token():
    url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    body = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    try:
        res = requests.post(url, headers={"content-type": "application/json"}, data=json.dumps(body))
        return res.json().get("access_token")
    except:
        return None

# --- CSS 스타일 적용 ---
st.markdown("""
<style>
    .market-box {
        background-color: #1e293b;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #334155;
    }
    .market-title {
        color: #94a3b8;
        font-size: 1rem;
        margin-bottom: 5px;
    }
    .market-val {
        font-size: 1.8rem;
        font-weight: bold;
    }
    .stock-card {
        background-color: #1e293b;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 20px;
        border-top: 4px solid #475569;
    }
    .profit { color: #ff4d4d !important; text-shadow: 0px 0px 10px rgba(255, 77, 77, 0.4); font-weight: 800; } /* 상승 빨강 */
    .loss { color: #3b82f6 !important; text-shadow: 0px 0px 10px rgba(59, 130, 246, 0.4); font-weight: 800; }   /* 하락 파랑 */
    .news-title { color: #fbbf24; font-weight: bold; margin-bottom: 5px;}
    .news-link { color: #94a3b8 !important; text-decoration: none; }
    .news-link:hover { color: #60a5fa !important; text-decoration: underline; }
</style>
""", unsafe_allow_html=True)


# --- 헬퍼 함수 ---


@st.cache_data(ttl=3600)  # 1시간 캐싱 (서버 부하 방지 및 속도 향상)
def get_news(query, num=3):
    try:
        # 뉴스 검색어에 시간 제한(최근 7일) 추가 чтобы 최신 뉴스만 가져오게 함
        search_query = f"{query} when:7d"
        encoded_query = urllib.parse.quote(search_query)
        # 검색결과를 날짜순(최신순)으로 정렬하려면 RSS URL 파라미터를 변경 (하지만 구글뉴스 RSS는 자동 관련도이므로 when 필터가 가장 확실함)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        items = root.findall('.//item')[:num]
        
        news_list = []
        for item in items:
            title = item.find('title').text
            if " - " in title: title = title.rsplit(" - ", 1)[0]
            link = item.find('link').text
            news_list.append((title, link))
        return news_list
    except:
        return []

@st.cache_data(ttl=600)
def run_backtest(ticker_symbol):
    try:
        # 백테스트를 위해 좀 더 긴 기간(5년) 데이터 로드
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period="5y")
        if df.empty: return None

        # 1. 이동평균선 계산
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()

        # 2. 투자 시그널 생성 (20일선이 60일선 위에 있으면 매수 상태(1), 아니면 현금(0))
        df['Signal'] = 0
        df.loc[df['MA20'] > df['MA60'], 'Signal'] = 1
        
        # 다음 날 수익률을 시그널에 곱함 (오늘 종가에 확인하고 내일 시가에 매매한다고 가정하는 단순 모델)
        df['Daily_Return'] = df['Close'].pct_change()
        df['Strategy_Return'] = df['Signal'].shift(1) * df['Daily_Return']

        # 3. 누적 수익률 계산
        df['Buy_Hold_Cumulative'] = (1 + df['Daily_Return']).cumprod() - 1
        df['Strategy_Cumulative'] = (1 + df['Strategy_Return']).cumprod() - 1

        # 결과 추출
        total_buy_hold_rtn = df['Buy_Hold_Cumulative'].iloc[-1] * 100
        total_strategy_rtn = df['Strategy_Cumulative'].iloc[-1] * 100
        
        # 승률 계산 (시그널이 유지되는 구간별로 수익이 났는지 체크)
        trades = []
        in_trade = False
        entry_price = 0
        for i in range(1, len(df)):
            if df['Signal'].iloc[i] == 1 and df['Signal'].iloc[i-1] == 0:
                in_trade = True
                entry_price = df['Close'].iloc[i]
            elif df['Signal'].iloc[i] == 0 and df['Signal'].iloc[i-1] == 1 and in_trade:
                in_trade = False
                exit_price = df['Close'].iloc[i]
                trades.append((exit_price - entry_price) / entry_price)
                
        win_rate = 0
        if trades:
            wins = sum(1 for t in trades if t > 0)
            win_rate = (wins / len(trades)) * 100

        # 백테스트 차트 그리기
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df['Buy_Hold_Cumulative']*100, mode='lines', name='그냥 존버 시', line=dict(color='#94a3b8', width=2)))
        fig.add_trace(go.Scatter(x=df.index, y=df['Strategy_Cumulative']*100, mode='lines', name='골든크로스 전략 시', line=dict(color='#fbbf24', width=3)))
        
        fig.update_layout(
            title="최근 5년 백테스트 누적 수익률 비교",
            xaxis_title="날짜",
            yaxis_title="누적 수익률 (%)",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            hovermode="x unified",
            height=300,
            margin=dict(l=0, r=0, t=40, b=0)
        )
        
        return {
            'buy_hold_rtn': total_buy_hold_rtn,
            'strategy_rtn': total_strategy_rtn,
            'win_rate': win_rate,
            'trade_count': len(trades),
            'fig': fig
        }
    except Exception as e:
        return None

@st.cache_data(ttl=60)
def get_kis_market_data():
    token = get_kis_token()
    if not token: return None, None
    url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "content-type": "application/json; charset=utf-8", "authorization": f"Bearer {token}",
        "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHPUP02100000"
    }
    try:
        res_k = requests.get(url, headers=headers, params={"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": "0001"})
        k_curr = float(res_k.json()['output']['stck_prpr'])
        res_q = requests.get(url, headers=headers, params={"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": "1001"})
        q_curr = float(res_q.json()['output']['stck_prpr'])
        return k_curr, q_curr
    except:
        return None, None

@st.cache_data(ttl=60)
def get_kis_stock_price(ticker_symbol):
    token = get_kis_token()
    if not token: return None
    code = ticker_symbol.split('.')[0]
    url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "content-type": "application/json; charset=utf-8", "authorization": f"Bearer {token}",
        "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHKST01010100"
    }
    try:
        res = requests.get(url, headers=headers, params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code})
        out = res.json()['output']
        return float(out['stck_prpr'])
    except:
        return None

@st.cache_data(ttl=60)
def get_nxt_stock_price(ticker_symbol):
    try:
        code = ticker_symbol.split('.')[0]
        url = f'https://polling.finance.naver.com/api/realtime/domestic/stock/{code}'
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        info = res.json()['datas'][0]
        nxt_info = info.get('overMarketPriceInfo')
        if nxt_info and nxt_info.get('overPrice'):
            price = float(nxt_info['overPrice'].replace(',', ''))
            diff = float(nxt_info['compareToPreviousClosePrice'].replace(',', ''))
            sign = nxt_info['compareToPreviousPrice']['code']
            if sign == '5': diff = -diff # 하락
            elif sign == '3': diff = 0   # 보합
            ratio = float(nxt_info['fluctuationsRatio'])
            return {'price': price, 'diff': diff, 'ratio': ratio}
        return None
    except:
        return None

@st.cache_data(ttl=600) # 10분마다 시장 데이터 갱신
def get_market_data():
    try:
        kospi = yf.Ticker("^KS11").history(period="1mo")
        kosdaq = yf.Ticker("^KQ11").history(period="1mo")
        return kospi, kosdaq
    except:
        return None, None

@st.cache_data(ttl=600)
def get_stock_data(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="6mo")
        
        # 한국 코스피(.KS)로 시도 후 없으면 코스닥(.KQ)으로 재시도
        if hist.empty and ticker_symbol.endswith('.KS'):
             fallback_ticker = ticker_symbol.replace('.KS', '.KQ')
             ticker = yf.Ticker(fallback_ticker)
             hist = ticker.history(period="6mo")
             return hist, fallback_ticker
        
        return hist, ticker_symbol
    except:
        return None, ticker_symbol

def draw_candlestick(hist_df):
    # 이동평균선 계산 (전체 데이터 기준)
    hist_df = hist_df.copy()
    hist_df['MA20'] = hist_df['Close'].rolling(window=20).mean()
    hist_df['MA60'] = hist_df['Close'].rolling(window=60).mean()
    
    recent_hist = hist_df.tail(20) # 최근 20일 캔들
    # 날짜를 문자열로 변환하여 주말/휴일에 빈 공간이 생기지 않도록 함 (Category 타입으로 인식시킴)
    recent_hist.index = recent_hist.index.strftime('%Y-%m-%d')
    
    fig = go.Figure()
    
    # 캔들 차트 추가
    fig.add_trace(go.Candlestick(x=recent_hist.index,
                open=recent_hist['Open'],
                high=recent_hist['High'],
                low=recent_hist['Low'],
                close=recent_hist['Close'],
                increasing_line_color='#ef4444', decreasing_line_color='#3b82f6',
                name='캔들'))
                
    # 20일 이동평균선 추가
    fig.add_trace(go.Scatter(x=recent_hist.index, y=recent_hist['MA20'], 
                             mode='lines', name='20일선', 
                             line=dict(color='#fbbf24', width=1.5)))
                             
    # 60일 이동평균선 추가
    fig.add_trace(go.Scatter(x=recent_hist.index, y=recent_hist['MA60'], 
                             mode='lines', name='60일선', 
                             line=dict(color='#c084fc', width=1.5)))

    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=150,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_rangeslider_visible=False,
        xaxis=dict(
            type='category', # Category 타입으로 지정하여 균일한 간격 유지
            showgrid=False, 
            showticklabels=True,
            tickmode='auto',
            nticks=5 # 라벨이 너무 겹치지 않게 개수 조절
        ),
        yaxis=dict(showgrid=False, showticklabels=False)
    )
    return fig


# --- 메인 앱 UI ---
st.title("📊 초보자 주식 집중 분석 대시보드")
st.markdown("매일 장 마감 후 시장 요약과 내 관심 종목을 한눈에 살펴보세요.")

# 현재 시간 표시 (한국 시간 기준)
now_kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
st.info(f"🕒 **현재 분석 시각:** {now_kst.strftime('%Y년 %m월 %d일 %H:%M:%S')} (데이터 갱신 주기: 1분)")
st.caption("※ 참고: KIS OpenAPI를 연동하여 HTS(한국투자증권)와 완전히 동일한 100% 실시간 주가를 제공합니다. 시간외단일가(NXT 등)가 존재할 경우 함께 표시됩니다.")

# 1. 사이드바 (사용자 입력)
with st.sidebar:
    st.header("🔍 분석할 종목 입력")
    st.markdown("관심 있는 종목 코드를 쉼표(,)로 구분하여 입력하세요.")
    
    # URL 파라미터에서 종목 코드 읽어오기 (없으면 기본값 사용)
    default_tickers = st.query_params.get("stocks", "005930, 035420")
    
    tickers_input = st.text_input("종목 코드 (예: 005930, 035420)", default_tickers)
    
    # 입력된 종목을 URL 파라미터에 실시간으로 반영하여 즐겨찾기(북마크) 지원
    if tickers_input:
        st.query_params["stocks"] = tickers_input
        
    st.markdown("---")
    st.markdown("💡 **Tip:** 이 주소를 즐겨찾기 해두시면 매번 앱 설치 없이 모바일에서도 실시간 조회가 가능합니다.")

# 2. 시장 주요 지수 (KOSPI / KOSDAQ)
st.subheader("📈 현재 시장 상황 (코스피 / 코스닥)")
kospi_data, kosdaq_data = get_market_data()
kis_k_curr, kis_q_curr = get_kis_market_data()

col1, col2 = st.columns(2)

if kospi_data is not None and not kospi_data.empty:
    today_str = now_kst.strftime('%Y-%m-%d')
    k_last_date = kospi_data.index[-1].strftime('%Y-%m-%d')
    k_prev = float(kospi_data['Close'].iloc[-2]) if k_last_date == today_str else float(kospi_data['Close'].iloc[-1])
    k_curr = kis_k_curr if kis_k_curr is not None else float(kospi_data['Close'].iloc[-1])
    
    k_pct = ((k_curr - k_prev) / k_prev) * 100
    k_color = "profit" if k_pct > 0 else "loss"
    k_sign = "+" if k_pct > 0 else ""
    
    q_last_date = kosdaq_data.index[-1].strftime('%Y-%m-%d')
    q_prev = float(kosdaq_data['Close'].iloc[-2]) if q_last_date == today_str else float(kosdaq_data['Close'].iloc[-1])
    q_curr = kis_q_curr if kis_q_curr is not None else float(kosdaq_data['Close'].iloc[-1])
    
    q_pct = ((q_curr - q_prev) / q_prev) * 100
    q_color = "profit" if q_pct > 0 else "loss"
    q_sign = "+" if q_pct > 0 else ""

    with col1:
        st.markdown(f"""
        <div class="market-box">
            <div class="market-title">KOSPI 종합</div>
            <div class="market-val"><span class="{k_color}">{k_curr:,.2f} ({k_sign}{k_pct:.2f}%)</span></div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
         st.markdown(f"""
        <div class="market-box">
            <div class="market-title">KOSDAQ 종합</div>
            <div class="market-val"><span class="{q_color}">{q_curr:,.2f} ({q_sign}{q_pct:.2f}%)</span></div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.warning("시장 데이터를 불러오고 있습니다...")


st.markdown("---")
st.subheader("📋 관심 종목 실시간 진단")

# 3. 개별 종목 분석 루프
if tickers_input:
    # 쉼표로 분리 후 공백 제거
    ticker_list = [t.strip() for t in tickers_input.split(',')]
    
    for req_code in ticker_list:
        if not req_code: continue
        
        # .KS 나 .KQ 가 없으면 기본적으로 .KS 붙여서 검색
        search_ticker = req_code
        if not search_ticker.endswith(".KS") and not search_ticker.endswith(".KQ"):
            search_ticker += ".KS"
            
        hist, final_ticker = get_stock_data(search_ticker)
        
        if hist is None or hist.empty:
            st.error(f"[{req_code}] 종목 데이터를 찾을 수 없습니다.")
            continue
            
        ticker_info = yf.Ticker(final_ticker)
        
        # 종목명 가져오기 (종목 정보에서 못 가져오면 코드로 대체)
        try:
            info = ticker_info.info
            stock_name = info.get('shortName', req_code)
        except:
            stock_name = req_code
            
        # 가격 및 등락 파악 (한국투자증권 API 정규장 가격)
        today_str = now_kst.strftime('%Y-%m-%d')
        last_date_str = hist.index[-1].strftime('%Y-%m-%d')
        prev_price = float(hist['Close'].iloc[-2]) if (last_date_str == today_str and len(hist) > 1) else float(hist['Close'].iloc[-1])
        
        kis_price = get_kis_stock_price(search_ticker)
        current_price = kis_price if kis_price is not None else float(hist['Close'].iloc[-1])
        
        return_pct = ((current_price - prev_price) / prev_price) * 100
        return_amt = current_price - prev_price
        
        color_class = "profit" if return_pct > 0 else "loss"
        sign = "+" if return_pct > 0 else ""
        
        # 시간외단일가(NXT) 정보 파악
        nxt_data = get_nxt_stock_price(search_ticker)
        
        # 간단 기술적 진단 (이평선 기준)
        try:
            ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            ma60 = hist['Close'].rolling(window=60).mean().iloc[-1]
            
            # MA 분석 로직
            if pd.isna(ma60): # 60일선 데이터가 부족한 경우 20일선만 분석
                if current_price >= ma20:
                    trend_msg = "단기 강세 (20일선 위) 상장된 지 얼마 안 된 종목이거나 데이터가 부족합니다."
                else:
                    trend_msg = "단기 약세 (20일선 무너짐) 데이터가 충분치 않습니다."
            else:
                if current_price >= ma20 and ma20 >= ma60:
                    trend_msg = "🟢 **완벽한 정배열 상승추세!** (현재가 > 20일선 > 60일선)<br>단기/중기 모두 매수세가 강해 긍정적입니다. 계속 오르는 배에 올라탈 만합니다 🚀"
                elif current_price < ma20 and current_price >= ma60:
                    trend_msg = "🟡 **단기 조정 중** (60일선 지지 테스트)<br>최근 살짝 떨어졌지만(20일선 하회), 아직 중장기 추세(60일선)는 살아있습니다. 여기서 버텨주면 좋은 매수 찬스입니다 ⚖️"
                elif current_price >= ma20 and current_price < ma60:
                    trend_msg = "🟠 **단기 반등 시도** (60일선 저항 테스트)<br>오랜 하락 끝에 고개를 들고 있습니다(20일선 돌파). 하지만 위에 있는 60일선(중장기 매물대)을 뚫을 수 있을지가 관건입니다 🧗"
                else:
                    trend_msg = "🔴 **완전한 역배열 하락추세** (현재가 < 20일선 < 60일선)<br>파는 사람이 너무 많습니다. 바닥이 확인될 때까지 신규 매수는 신중히 관망하는 것이 좋습니다 ⚠️"
        except:
             trend_msg = "단기 관망 보수적 접근 필요 ⚠️ (데이터 집계 지연)"

        # 화면 분할 (1.카드 정보, 2.뉴스)
        st.markdown(f'<div class="stock-card">', unsafe_allow_html=True)
        row1_col1, row1_col2 = st.columns([2, 1])
        
        with row1_col1:
            st.markdown(f"### {stock_name} <span style='font-size: 1rem; color: #94a3b8;'>({req_code})</span>", unsafe_allow_html=True)
            
            # NXT(시간외단일가)가 존재할 경우 표시 권역 교체 (NXT 최우선 노출)
            if nxt_data and nxt_data['price'] != current_price:
                 nxt_price = nxt_data['price']
                 nxt_diff = nxt_data['diff']
                 nxt_ratio = nxt_data['ratio']
                 nxt_color = "profit" if nxt_ratio > 0 else "loss"
                 nxt_sign = "+" if nxt_ratio > 0 else ""
                 
                 # 1. 메인 (큰 시세) 자리에 시간외/NXT 가격 꽂기
                 st.markdown(f"<div style='margin-bottom: -15px;'><span style='background-color: #3b82f6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; font-weight: bold;'>시간외/NXT</span></div>", unsafe_allow_html=True)
                 st.markdown(f"## <span class='{nxt_color}'>{nxt_price:,.0f}원 ({nxt_sign}{nxt_ratio:.2f}%)</span>", unsafe_allow_html=True)
                 
                 # 2. 서브 (작은 시세) 자리에 원래 정규장(KRX) 종가 꽂기
                 st.markdown(f"<div style='color: #94a3b8; margin-bottom: 15px;'>오늘(정규) <span class='{color_class}'>{current_price:,.0f}원 ({sign}{return_pct:.2f}%)</span></div>", unsafe_allow_html=True)
            else:
                 # 시간외 가격이 변동이 없거나 장중일 경우 원래대로 표기
                 st.markdown(f"## <span class='{color_class}'>{current_price:,.0f}원 ({sign}{return_pct:.2f}%)</span>", unsafe_allow_html=True)
                 
            st.markdown(f"<div style='background-color: #1e293b; border: 1px solid #475569; padding: 15px; border-radius: 8px; color: #f8fafc; font-size: 1rem; line-height: 1.5; display:inline-block; border-left: 5px solid #3b82f6; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);'><div style='color:#60a5fa; font-size: 1.1rem; font-weight:900; margin-bottom:8px;'>🤖 AI 이평선 진단</div>{trend_msg}</div>", unsafe_allow_html=True)
            st.plotly_chart(draw_candlestick(hist), width='stretch', config={'displayModeBar': False})
            
        with row1_col2:
            st.markdown('<div class="news-title">📰 최근 관련 뉴스</div>', unsafe_allow_html=True)
            news_items = get_news(f"{stock_name} 주가 OR 실적 OR 전망", 4)
            if news_items:
                for title, link in news_items:
                    st.markdown(f"- <a class='news-link' href='{link}' target='_blank'>{title}</a>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='color: #94a3b8;'>최근 관련 뉴스가 없습니다.</span>", unsafe_allow_html=True)
                
        # --- 백테스트 결과 노출 영역 ---
        st.markdown("---")
        with st.expander(f"⚙️ [{stock_name}] 5년 백테스트 시뮬레이션 돌려보기 (20일선 vs 60일선 교차 전략)", expanded=False):
            st.markdown("""
            **이동평균선 교차 전략이란?**
            * 초보자도 쉽게 따라하는 가장 고전적인 기법입니다.
            * **매수:** 최근 20일간의 주가 흐름(단기)이 60일간의 흐름(장기)을 뚫고 **상승**할 때.
            * **매도:** 반대로 20일선이 60일선을 뚫고 **하락**할 때 즉시 팔고 현금화.
            """)
            
            with st.spinner("AI가 지난 5년(약 1,200일) 치 데이터를 불러와 가상 매매를 시뮬레이션 중입니다..."):
                bt_result = run_backtest(final_ticker)
                
            if bt_result:
                b_rtn = bt_result['buy_hold_rtn']
                s_rtn = bt_result['strategy_rtn']
                w_rate = bt_result['win_rate']
                trades = bt_result['trade_count']
                
                b_color = "profit" if b_rtn > 0 else "loss"
                s_color = "profit" if s_rtn > 0 else "loss"
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("전략 사용 시 총수익률", f"{s_rtn:.1f}%")
                col2.metric("그냥 존버 시 총수익률", f"{b_rtn:.1f}%")
                col3.metric("승률 (이익/손절 빈도)", f"{w_rate:.1f}%")
                col4.metric("5년간 총 매매 횟수", f"{trades}회")
                
                # 결과 해석 한줄평
                if s_rtn > b_rtn:
                    st.success("🎉 이 종목은 그냥 가만히 들고 있는 것보다 **타이밍(골든크로스)을 맞춰서 사고파는 편이 훨씬 돈을 많이 벌었습니다!**")
                else:
                    st.warning("⚠️ 이 종목은 잦은 매매로 수수료만 날렸습니다. **이런 우직한 종목은 차트 보지 말고 그냥 장기투자하는 게 답이네요!**")

                st.plotly_chart(bt_result['fig'], width='stretch', config={'displayModeBar': False})
            else:
                st.error("데이터 부족으로 백테스트를 진행할 수 없습니다. 상장된 지 5년 미만이거나 거래 정지 종목일 수 있습니다.")
                
        st.markdown('</div>', unsafe_allow_html=True)

else:
    st.info("왼쪽 사이드바에 종목 코드를 입력해주세요.")
