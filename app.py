import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import base64
import requests

# --- CẤU HÌNH ---
GITHUB_TOKEN = "YOUR_GITHUB_TOKEN"  # Thay token của bạn vào đây
REPO_NAME = "san-song" # Tên repository của bạn
GITHUB_USER = "TEN_CUA_BAN" # Tên user GitHub của bạn

st.set_page_config(page_title="Hệ Thống Săn Sóng V21", layout="wide")

# --- HÀM TÍNH TOÁN FULL CHỈ BÁO ---
def tinh_toan_chuyen_sau(df, df_vni=None):
    if df is None or len(df) < 20: return None
    df.columns = df.columns.str.lower()
    
    close = df['close']; high = df['high']; low = df['low']
    open_p = df['open']; vol = df['volume']

    # 1. ADX WILDER CHUẨN (ĐƯỜNG MÀU CYAN)
    period = 14
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    up = high.diff(); dw = low.shift(1) - low
    p_dm = np.where((up > dw) & (up > 0), up, 0)
    m_dm = np.where((dw > up) & (dw > 0), dw, 0)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    p_di = 100 * (pd.Series(p_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr)
    m_di = 100 * (pd.Series(m_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr)
    dx = 100 * (abs(p_di - m_di) / (p_di + m_di).replace(0, np.nan))
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()

    # 2. RSI & RS (SỬ DỤNG VNINDEX.CSV ĐỂ SO SÁNH)
    df['rsi'] = 100 - (100 / (1 + (close.diff().where(close.diff() > 0, 0).ewm(alpha=1/14).mean() / 
                                  (-close.diff().where(close.diff() < 0, 0)).ewm(alpha=1/14).mean())))
    
    df['rs_score'] = 0.0
    if df_vni is not None and len(df_vni) >= 5:
        vni_c = df_vni['close'] if 'close' in df_vni.columns else df_vni['Close']
        vni_change = (vni_c.iloc[-1] / vni_c.iloc[-5] - 1) * 100
        stock_change = (close.iloc[-1] / close.iloc[-5] - 1) * 100
        df['rs_score'] = round(stock_change - vni_change, 2)

    # 3. QUẢ BOM & ĐIỂM MUA
    df['sma20'] = close.rolling(20).mean()
    df['bw'] = (close.rolling(20).std() * 4) / df['sma20']
    df['bomb'] = df['bw'] <= df['bw'].rolling(20).min()
    df['vol_sma10'] = vol.rolling(10).mean()
    df['is_buy'] = (vol > df['vol_sma10'] * 1.3) & (close > open_p) & (df['adx'] > 20)
    
    return df

# --- HÀM UPDATE GHI ĐÈ FILE LÊN GITHUB ---
def update_github_file(file_path, df):
    csv_content = df.to_csv(index=False)
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{file_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    
    # Lấy SHA của file cũ để ghi đè
    res = requests.get(url, headers=headers)
    sha = res.json().get('sha') if res.status_code == 200 else None
    
    payload = {
        "message": f"Update {file_path} via Streamlit",
        "content": base64.b64encode(csv_content.encode()).decode(),
        "sha": sha
    }
    r = requests.put(url, headers=headers, json=payload)
    return r.status_code in [200, 201]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚡ HỆ THỐNG V21")
    if st.button("🔄 UPDATE HOSE & VNI"):
        with st.spinner("Đang tải data & ghi đè GitHub..."):
            # 1. Update VNINDEX
            vni_new = yf.download("^VNINDEX", period="1y", progress=False)
            vni_new.reset_index(inplace=True)
            # 2. Update HOSE (Ví dụ 10 mã tiêu biểu, bạn có thể load list từ file)
            list_mã = ['SSI','DIG','VGI','HPG','GEX','VND','TCB','MBB','SHB','VHM']
            df_hose_new = yf.download([m + ".VN" for m in list_mã], period="1y", group_by='ticker')
            
            # (Logic dọn dẹp và lưu file ở đây...)
            s1 = update_github_file("VNINDEX.csv", vni_new)
            st.success("Đã ghi đè VNINDEX.csv!") if s1 else st.error("Lỗi update VNI")

    btn_sieu_sao = st.button("🌟 SIÊU SAO THEO DÕI")
    ticker_input = st.text_input("📈 SOI CHI TIẾT MÃ:", value="DIG").upper().strip()

# --- ĐỌC DỮ LIỆU ---
try:
    vni_data = pd.read_csv("VNINDEX.csv")
    hose_data = pd.read_csv("hose.csv")
except:
    st.warning("Vui lòng nhấn Update hoặc kiểm tra file CSV trên GitHub.")

# --- HIỂN THỊ SIÊU SAO ---
if btn_sieu_sao:
    st.subheader("🔥 Tín Hiệu Dòng Tiền & RS")
    # Logic tính toán bảng Siêu Sao tương tự bản trước...
    # (Sử dụng hàm tinh_toan_chuyen_sau để lấy ADX, RS, Điểm Mua)

# --- HIỂN THỊ ĐỒ THỊ FULL CHỈ BÁO ---
if ticker_input:
    df_mã = hose_data[hose_data['symbol'] == ticker_input].copy()
    if not df_mã.empty:
        df_mã = tinh_toan_chuyen_sau(df_mã, vni_data)
        l = df_mã.iloc[-1]
        
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.2, 0.3])
        
        # Tầng 1: Giá + Buy + Bom
        fig.add_trace(go.Candlestick(x=df_mã['date'], open=df_mã['open'], high=df_mã['high'], low=df_mã['low'], close=df_mã['close'], name='Giá'), row=1, col=1)
        
        # Tầng 2: Volume
        fig.add_trace(go.Bar(x=df_mã['date'], y=df_mã['volume'], name='Volume'), row=2, col=1)
        
        # Tầng 3: ADX (ĐÃ CẬP NHẬT) & RSI & RS
        fig.add_trace(go.Scatter(x=df_mã['date'], y=df_mã['adx'], line=dict(color='cyan', width=2), name='ADX'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_mã['date'], y=df_mã['rsi'], line=dict(color='orange'), name='RSI'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_mã['date'], y=df_mã['rs_score'], line=dict(color='magenta', dash='dot'), name='Sức mạnh RS'), row=3, col=1)
        
        fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
