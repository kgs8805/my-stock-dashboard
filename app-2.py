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
import os

# --- 기본 페이지 설정 ---
st.set_page_config(
    page_title="내 주식 평생 관리 대시보드",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- KIS OpenAPI 인증 키 ---
APP_KEY = "PSSpT74p43VgT6Rn24Y4NlqAg8m8eF6vmBzD"
APP_SECRET = "ZiNUtohv5bzjidzP54uZ+GH3/jZ8U9+SU2SJr4g9uLLOocmdNFEGvjQ3iWqxLqTsdoZOUv3ZZx2Aj1fl9Oez54DapzbHh9+FAGn15rF6MV9R5iiYO8qnDxq4gjuRGGToaB3Ewqv46McrV9MLc10q2PonKNwOAyjsxbKUvtWIL5NMIlXcR3o="

@st.cache_data(ttl=24*3600)
def get_kis_token():
    url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    body = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    try:
        res = requests.post(url, headers={"content-type": "application/json"}, data=json.dumps(body))
        return res.json().get("access_token")
    except:
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
            if sign == '5': diff = -diff
            elif sign == '3': diff = 0
            ratio = float(nxt_info['fluctuationsRatio'])
            return {'price': price, 'diff': diff, 'ratio': ratio}
        return None
    except:
        return None

@st.cache_data(ttl=600)
def get_market_data():
    try:
        kospi = yf.Ticker("^KS11").history(period="1mo")
        kosdaq = yf.Ticker("^KQ11").history(period="1mo")
        return kospi, kosdaq
    except:
        return None, None

@st.cache_data(ttl=3600)
def get_news(query, num=3):
    try:
        search_query = f"{query} when:7d"
        encoded_query = urllib.parse.quote(search_query)
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

def draw_candlestick(hist_df):
    hist_df = hist_df.copy()
    hist_df['MA20'] = hist_df['Close'].rolling(window=20).mean()
    hist_df['MA60'] = hist_df['Close'].rolling(window=60).mean()
    recent_hist = hist_df.tail(20)
    recent_hist.index = recent_hist.index.strftime('%Y-%m-%d')
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=recent_hist.index,
                open=recent_hist['Open'],
                high=recent_hist['High'],
                low=recent_hist['Low'],
                close=recent_hist['Close'],
                increasing_line_color='#ef4444', decreasing_line_color='#3b82f6',
                name='캔들'))
    fig.add_trace(go.Scatter(x=recent_hist.index, y=recent_hist['MA20'], 
                             mode='lines', name='20일선', 
                             line=dict(color='#fbbf24', width=1.5)))
    fig.add_trace(go.Scatter(x=recent_hist.index, y=recent_hist['MA60'], 
                             mode='lines', name='60일선', 
                             line=dict(color='#c084fc', width=1.5)))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=150,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_rangeslider_visible=False,
        xaxis=dict(type='category', showgrid=False, showticklabels=True, tickmode='auto', nticks=5),
        yaxis=dict(showgrid=False, showticklabels=False)
    )
    return fig

# --- CSS 스타일 ---
st.markdown("""
<style>
    .market-box { background-color: #1e293b; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #334155; }
    .market-title { color: #94a3b8; font-size: 1rem; margin-bottom: 5px; }
    .market-val { font-size: 1.8rem; font-weight: bold; }
    .stock-card { background-color: #1e293b; padding: 20px; border-radius: 15px; margin-bottom: 20px; border-top: 4px solid #475569; }
    .pf-box { background: linear-gradient(135deg, #1e1b4b, #312e81); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
    .pf-box.total-box { background: linear-gradient(135deg, #064e3b, #0f766e); margin-top: 20px;}
    .pf-title { font-size: 1.1rem; color: #c4b5fd; margin-bottom: 15px; margin-top: 0; }
    .total-box .pf-title { color: #a7f3d0; }
    .pf-val { font-size: 2.2rem; font-weight: bold; margin-bottom: 10px; }
    .profit { color: #ff4d4d !important; text-shadow: 0px 0px 10px rgba(255, 77, 77, 0.4); font-weight: 800; }
    .loss { color: #3b82f6 !important; text-shadow: 0px 0px 10px rgba(59, 130, 246, 0.4); font-weight: 800; }
    .news-title { color: #fbbf24; font-weight: bold; margin-bottom: 5px;}
    .news-link { color: #94a3b8 !important; text-decoration: none; }
    .news-link:hover { color: #60a5fa !important; text-decoration: underline; }
</style>
""", unsafe_allow_html=True)

# --- 메인 로직 ---
st.title("💼 내 주식 포트폴리오 평생 관리 대시보드")
now_kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
st.info(f"🕒 **현재 분석 시각:** {now_kst.strftime('%Y년 %m월 %d일 %H:%M:%S')} (데이터 갱신 주기: 1분)")
st.caption("※ KIS OpenAPI 연동: HTS 완벽 동일 실시간 주가 / 시간외단일가(NXT) 지원")

# 포트폴리오 데이터 읽기
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
data_file = os.path.join(BASE_DIR, "my_portfolio_data.txt")

my_stocks = []
realized_profit = 0

if os.path.exists(data_file):
    with open(data_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if line.startswith('REALIZED_PROFIT='):
                try: realized_profit = float(line.split('=')[1].strip())
                except: pass
            else:
                parts = line.split(':')
                if len(parts) >= 4:
                    code = parts[1].strip()
                    yf_ticker = code if code.endswith(".KS") or code.endswith(".KQ") else code + ".KS"
                    my_stocks.append({
                        "name": parts[0].strip(),
                        "code": code,
                        "yf_ticker": yf_ticker,
                        "buy_price": float(parts[2].strip()),
                        "qty": int(parts[3].strip())
                    })

if not my_stocks:
    st.warning("`my_portfolio_data.txt` 파일에 보유 종목이 설정되지 않았습니다.")
    st.stop()

# 1. 시장 지수 요약
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
    
    q_last_date = kosdaq_data.index[-1].strftime('%Y-%m-%d')
    q_prev = float(kosdaq_data['Close'].iloc[-2]) if q_last_date == today_str else float(kosdaq_data['Close'].iloc[-1])
    q_curr = kis_q_curr if kis_q_curr is not None else float(kosdaq_data['Close'].iloc[-1])
    q_pct = ((q_curr - q_prev) / q_prev) * 100
    q_color = "profit" if q_pct > 0 else "loss"

    with col1:
        st.markdown(f"<div class='market-box'><div class='market-title'>KOSPI 종합</div><div class='market-val'><span class='{k_color}'>{k_curr:,.2f} ({k_pct:+.2f}%)</span></div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='market-box'><div class='market-title'>KOSDAQ 종합</div><div class='market-val'><span class='{q_color}'>{q_curr:,.2f} ({q_pct:+.2f}%)</span></div></div>", unsafe_allow_html=True)

st.markdown("---")

# 2. 개별 종목 분석 + 포트폴리오 집계
st.subheader("📋 내 포트폴리오 실시간 진단")

total_invest = 0
total_value = 0
stock_widgets = [] # 나중에 그릴 요소들

for s in my_stocks:
    search_ticker = s['yf_ticker']
    ticker = yf.Ticker(search_ticker)
    hist = ticker.history(period="6mo")
    
    if hist.empty and search_ticker.endswith('.KS'):
        search_ticker = search_ticker.replace('.KS', '.KQ')
        ticker = yf.Ticker(search_ticker)
        hist = ticker.history(period="6mo")
        
    if hist.empty:
        stock_widgets.append((s, None, None, None, None, None))
        continue
        
    today_str = now_kst.strftime('%Y-%m-%d')
    last_date_str = hist.index[-1].strftime('%Y-%m-%d')
    prev_price = float(hist['Close'].iloc[-2]) if (last_date_str == today_str and len(hist) > 1) else float(hist['Close'].iloc[-1])
    
    kis_price = get_kis_stock_price(search_ticker)
    current_price = kis_price if kis_price is not None else float(hist['Close'].iloc[-1])
    
    # 시간외/NXT 확인
    nxt_data = get_nxt_stock_price(search_ticker)
    active_price = current_price
    if nxt_data and nxt_data['price'] != current_price:
        active_price = nxt_data['price'] # 포트폴리오 가치 계산은 최신가(NXT) 반영
        # MTS앱에 표시되는 '평단가'에는 이미 매수 수수료가 녹아있는 경우가 대부분입니다.
    # 따라서 매수 원금은 순수하게 (평단가 * 수량)으로 잡습니다.
    invest_amount = s['buy_price'] * s['qty']
    
    # 팔 때 떼이는 세금+증권사수수료(약 0.195%)만 현재가치에서 빼줍니다.
    current_amount = (active_price * s['qty']) * (1 - 0.001161)
    
    total_invest += invest_amount
    total_value += current_amount
    
    stock_widgets.append((s, hist, prev_price, current_price, nxt_data, current_amount))

# 3. 총 계좌 요약 대시보드 (맨 위 배치)
unrealized_amt = total_value - total_invest
unrealized_pct = (unrealized_amt / total_invest * 100) if total_invest > 0 else 0
u_color = "profit" if unrealized_amt > 0 else "loss"
u_sign = "+" if unrealized_amt > 0 else ""

total_cumulative_amt = unrealized_amt + realized_profit
tc_color = "profit" if total_cumulative_amt > 0 else "loss"
tc_sign = "+" if total_cumulative_amt > 0 else ""

r_color = "profit" if realized_profit > 0 else "loss"
r_sign = "+" if realized_profit > 0 else ""

col1, col2 = st.columns(2)
with col1:
    st.markdown(f"""
    <div class="pf-box">
        <h2 class="pf-title">💼 현재 들고 있는 주식 (미실현 평가액)</h2>
        <div class="pf-val">{total_value:,.0f} 원</div>
        <div class="{u_color}" style="font-size:1.1rem; font-weight:bold;">현재 평가 수익: {u_sign}{unrealized_amt:,.0f}원 ({u_sign}{unrealized_pct:.2f}%)</div>
        <div style="margin-top: 10px; color: #94a3b8; font-size: 0.85rem;">투자 원금: {total_invest:,.0f}원</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="pf-box total-box">
        <h2 class="pf-title">🏆 내 주식농사 총 결산 (누적 손익)</h2>
        <div class="pf-val {tc_color}">{tc_sign}{total_cumulative_amt:,.0f} 원</div>
        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
            <div style="display:flex; justify-content:space-between; margin-bottom: 5px; font-size: 1.05rem;">
                <span style="color:#e2e8f0;">① 과거 팔아서 번 돈(실현손익):</span>
                <b class="{r_color}">{r_sign}{realized_profit:,.0f}원</b>
            </div>
            <div style="display:flex; justify-content:space-between; font-size: 1.05rem;">
                <span style="color:#e2e8f0;">② 지금 들고 있는 돈(평가손익):</span>
                <b class="{u_color}">{u_sign}{unrealized_amt:,.0f}원</b>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br><br>", unsafe_allow_html=True)

# 4. 개별 종목 카드 출력
for s, hist, prev_price, current_price, nxt_data, current_amount in stock_widgets:
    if hist is None:
        st.error(f"[{s['name']}] 데이터를 찾을 수 없습니다.")
        continue

    return_pct = ((current_price - prev_price) / prev_price) * 100
    color_class = "profit" if return_pct > 0 else "loss"
    sign = "+" if return_pct > 0 else ""
    
    my_return_pct = ((current_price - s['buy_price']) / s['buy_price']) * 100
    my_color = "profit" if my_return_pct > 0 else "loss"
    
    st.markdown(f'<div class="stock-card">', unsafe_allow_html=True)
    row_col1, row_col2 = st.columns([2, 1])
    
    with row_col1:
        st.markdown(f"### {s['name']} <span style='font-size: 1rem; color: #94a3b8;'>({s['code']})</span>", unsafe_allow_html=True)
        
        # NXT 표시 최우선 로직
        if nxt_data and nxt_data['price'] != current_price:
             nxt_price = nxt_data['price']
             nxt_ratio = nxt_data['ratio']
             nxt_color = "profit" if nxt_ratio > 0 else "loss"
             nxt_sign = "+" if nxt_ratio > 0 else ""
             st.markdown(f"<div style='margin-bottom: -15px;'><span style='background-color: #3b82f6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; font-weight: bold;'>시간외/NXT</span></div>", unsafe_allow_html=True)
             st.markdown(f"## <span class='{nxt_color}'>{nxt_price:,.0f}원 ({nxt_sign}{nxt_ratio:.2f}%)</span>", unsafe_allow_html=True)
             st.markdown(f"<div style='color: #94a3b8; margin-bottom: 15px;'>오늘(정규) <span class='{color_class}'>{current_price:,.0f}원 ({sign}{return_pct:.2f}%)</span></div>", unsafe_allow_html=True)
             
             # 세금/수수료 반영 수익률
             my_return_amt = current_amount - invest_amount
             my_return_pct = (my_return_amt / invest_amount) * 100
             my_color = "profit" if my_return_pct > 0 else "loss"
             
        else:
             st.markdown(f"## <span class='{color_class}'>{current_price:,.0f}원 ({sign}{return_pct:.2f}%)</span>", unsafe_allow_html=True)
             st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
             
        # 내 포지션 정보 블록 (세금/수수료 반영분)
        my_return_amt = current_amount - invest_amount
        my_return_pct = (my_return_amt / invest_amount) * 100
        my_color = "profit" if my_return_pct > 0 else "loss"
        
        st.markdown(f"""
        <div style='background-color: #0f172a; border: 1px solid #334155; padding: 15px; border-radius: 8px; margin-bottom:15px;'>
            <div style='display:flex; justify-content:space-between; margin-bottom: 5px; font-size:1.1rem;'>
                <span style='color:#e2e8f0'>추정 정산금액: <b>{current_amount:,.0f}원</b></span>
                <span class="{my_color}" style='font-size:1.2rem; font-weight:bold;'>({my_return_pct:+.2f}%) {my_return_amt:+,.0f}원</span>
            </div>
            <div style='color:#94a3b8; font-size:0.95rem;'>내 평단가: {s['buy_price']:,.0f}원 | 투자수량: {s['qty']}주 (투자원금+수수료: {invest_amount:,.0f}원)</div>
            <div style='color:#64748b; font-size:0.75rem; margin-top:3px;'>※ 제비용(매매수수료 0.015%, 증권거래세 0.18%) 차감 후 순수익 및 정산금 추정치입니다.</div>
        </div>
        """, unsafe_allow_html=True)
             
        st.plotly_chart(draw_candlestick(hist), width='stretch', config={'displayModeBar': False})
        
    with row_col2:
        st.markdown('<div class="news-title">📰 최근 관련 뉴스</div>', unsafe_allow_html=True)
        news_items = get_news(f"{s['name']} 실적 OR 주가", 4)
        if news_items:
            for title, link in news_items:
                st.markdown(f"- <a class='news-link' href='{link}' target='_blank'>{title}</a>", unsafe_allow_html=True)
        else:
            st.markdown("<span style='color: #94a3b8;'>최근 관련 뉴스가 없습니다.</span>", unsafe_allow_html=True)
            
    st.markdown('</div>', unsafe_allow_html=True)