import streamlit as st
import yfinance as yf
import pandas as pd
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import datetime
import plotly.graph_objects as go

# --- 기본 페이지 설정 ---
st.set_page_config(
    page_title="주식 진단 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    .profit { color: #ef4444; } /* 상승 빨강 */
    .loss { color: #3b82f6; }   /* 하락 파랑 */
    .news-title { color: #fbbf24; font-weight: bold; margin-bottom: 5px;}
    .news-link { color: #94a3b8 !important; text-decoration: none; }
    .news-link:hover { color: #60a5fa !important; text-decoration: underline; }
</style>
""", unsafe_allow_html=True)


# --- 헬퍼 함수 ---
@st.cache_data(ttl=3600)  # 1시간 캐싱 (서버 부하 방지 및 속도 향상)
def get_news(query, num=3):
    try:
        encoded_query = urllib.parse.quote(query)
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
    recent_hist = hist_df.tail(20) # 최근 20일 캔들
    fig = go.Figure(data=[go.Candlestick(x=recent_hist.index,
                open=recent_hist['Open'],
                high=recent_hist['High'],
                low=recent_hist['Low'],
                close=recent_hist['Close'],
                increasing_line_color='#ef4444', decreasing_line_color='#3b82f6')])
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=150,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_rangeslider_visible=False,
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False, showticklabels=False)
    )
    return fig


# --- 메인 앱 UI ---
st.title("📊 초보자 주식 집중 분석 대시보드")
st.markdown("매일 장 마감 후 시장 요약과 내 관심 종목을 한눈에 살펴보세요.")

# 1. 사이드바 (사용자 입력)
with st.sidebar:
    st.header("🔍 분석할 종목 입력")
    st.markdown("관심 있는 종목 코드를 쉼표(,)로 구분하여 입력하세요.")
    tickers_input = st.text_input("종목 코드 (예: 005930, 035420)", "005930, 035420")
    
    st.markdown("---")
    st.markdown("💡 **Tip:** 이 주소를 즐겨찾기 해두시면 매번 앱 설치 없이 모바일에서도 실시간 조회가 가능합니다.")

# 2. 시장 주요 지수 (KOSPI / KOSDAQ)
st.subheader("📈 현재 시장 상황 (코스피 / 코스닥)")
kospi_data, kosdaq_data = get_market_data()

col1, col2 = st.columns(2)

if kospi_data is not None and not kospi_data.empty:
    k_curr = float(kospi_data['Close'].iloc[-1])
    k_prev = float(kospi_data['Close'].iloc[-2])
    k_pct = ((k_curr - k_prev) / k_prev) * 100
    k_color = "profit" if k_pct > 0 else "loss"
    k_sign = "+" if k_pct > 0 else ""
    
    q_curr = float(kosdaq_data['Close'].iloc[-1])
    q_prev = float(kosdaq_data['Close'].iloc[-2])
    q_pct = ((q_curr - q_prev) / q_prev) * 100
    q_color = "profit" if q_pct > 0 else "loss"
    q_sign = "+" if q_pct > 0 else ""

    with col1:
        st.markdown(f"""
        <div class="market-box">
            <div class="market-title">KOSPI 종합</div>
            <div class="market-val <span class="{k_color}">{k_curr:,.2f} ({k_sign}{k_pct:.2f}%)</span></div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
         st.markdown(f"""
        <div class="market-box">
            <div class="market-title">KOSDAQ 종합</div>
            <div class="market-val <span class="{q_color}">{q_curr:,.2f} ({q_sign}{q_pct:.2f}%)</span></div>
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
            
        # 가격 및 등락 파악
        current_price = float(hist['Close'].iloc[-1])
        prev_price = float(hist['Close'].iloc[-2])
        return_pct = ((current_price - prev_price) / prev_price) * 100
        return_amt = current_price - prev_price
        
        color_class = "profit" if return_pct > 0 else "loss"
        sign = "+" if return_pct > 0 else ""
        
        # 간단 기술적 진단 (단기 이평선 기준)
        ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
        if current_price >= ma20:
            trend_msg = "생명선(20일선) 돌파! 추세 양호 🚀"
        else:
            trend_msg = "20일선 밑으로 무너짐. 단기 관망 보수적 접근 필요 ⚠️"

        # 화면 분할 (1.카드 정보, 2.뉴스)
        st.markdown(f'<div class="stock-card">', unsafe_allow_html=True)
        row1_col1, row1_col2 = st.columns([2, 1])
        
        with row1_col1:
            st.markdown(f"### {stock_name} <span style='font-size: 1rem; color: #94a3b8;'>({req_code})</span>", unsafe_allow_html=True)
            st.markdown(f"## <span class='{color_class}'>{current_price:,.0f}원 ({sign}{return_pct:.2f}%)</span>", unsafe_allow_html=True)
            st.markdown(f"<div style='background: rgba(0,0,0,0.2); padding: 10px; border-radius: 8px; color: #cbd5e1; font-size: 0.95rem; display:inline-block;'><b>🤖 AI 단기 진단:</b> {trend_msg}</div>", unsafe_allow_html=True)
            
            # 미니 차트 삽입
            st.plotly_chart(draw_candlestick(hist), use_container_width=True, config={'displayModeBar': False})
            
        with row1_col2:
            st.markdown('<div class="news-title">📰 최근 관련 뉴스</div>', unsafe_allow_html=True)
            news_items = get_news(f"{stock_name} 주가 OR 실적 OR 전망", 4)
            if news_items:
                for title, link in news_items:
                    st.markdown(f"- <a class='news-link' href='{link}' target='_blank'>{title}</a>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='color: #94a3b8;'>최근 관련 뉴스가 없습니다.</span>", unsafe_allow_html=True)
                
        st.markdown('</div>', unsafe_allow_html=True)

else:
    st.info("왼쪽 사이드바에 종목 코드를 입력해주세요.")
