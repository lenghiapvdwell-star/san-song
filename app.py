import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Hệ Thống Săn Sóng V19", layout="wide")

# --- HÀM TÍNH TOÁN KỸ THUẬT SIÊU CẤP ---
def calculate_all(df, df_vni=None):
    df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    df.columns = df.columns.str.capitalize()
    
    close = pd.Series(df['Close'].values.flatten(), index=df.index)
    high = pd.Series(df['High'].values.flatten(), index=df.index)
    low = pd.Series(df['Low'].values.flatten(), index=df.index)
    vol = pd.Series(df['Volume'].values.flatten(), index=df.index)

    # 1. ADX Wilder
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    up = high.diff(); dw = low.shift(1) - low
    p_dm = np.where((up > dw) & (up > 0), up, 0)
    m_dm = np.where((dw > up) & (dw > 0), dw, 0)
    atr = tr.ewm(alpha=1/14, adjust=False).mean()
    p_di = 100 * (pd.Series(p_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr)
    m_di = 100 * (pd.Series(m_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr)
    dx = 100 * (abs(p_di - m_di) / (p_di + m_di).replace(0, np.nan))
    df['ADX'] = dx.ewm(alpha=1/14, adjust=False).mean()

    # 2. RSI & RS (Sửa lỗi nan: Tính RS so với nến cách đây 5 phiên)
    df['RSI'] = 100 - (100 / (1 + (close.diff().where(close.diff() > 0, 0).ewm(alpha=1/14).mean() / 
                                  (-close.diff().where(close.diff() < 0, 0)).ewm(alpha=1/14).mean())))
    
    if df_vni is not None:
        vni_close = pd.Series(df_vni['Close'].values.flatten(), index=df_vni.index)
        vni_change = (vni_close.iloc[-1] / vni_close.iloc[-5] - 1) * 100
        stock_change = (close / close.shift(5) - 1) * 100
        df['RS'] = stock_change - vni_change # RS điểm số
    
    # 3. Quả Bom (Squeeze) & Điểm Mua
    df['SMA20'] = close.rolling(20).mean()
    df['BW'] = (close.rolling(20).std() * 4) / df['SMA20']
    df['BOMB'] = df['BW'] <= df['BW'].rolling(20).min()
    df['VOL_SMA'] = vol.rolling(10).mean()
    df['BUY'] = (vol > df['VOL_SMA'] * 1.3) & (close > df['Open'].values.flatten()) & (df['ADX'] > 20)
    
    return df

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚡ ĐIỀU KHIỂN V19")
    if st.button("🚀 CẬP NHẬT DỮ LIỆU MỚI"):
        st.cache_data.clear()
        st.success("Đã làm mới dữ liệu!")
    
    btn_sieu_sao = st.button("🌟 SIÊU SAO THEO DÕI")
    btn_loc = st.button("🔍 LỌC ĐIỂM MUA & BOM")
    ticker_input = st.text_input("📈 SOI CHI TIẾT MÃ:", value="DIG").upper()

# Lấy dữ liệu VNINDEX trực tuyến (Fix lỗi RS nan)
vni = yf.download("^VNINDEX", period="1y", progress=False)

# --- CHỨC NĂNG 1: SIÊU SAO THEO DÕI (TỪ FILE sieu_sao_theo_doi.py) ---
if btn_sieu_sao:
    st.subheader("🔥 Bảng Theo Dõi Siêu Sao Real-time")
    watch_list = ['SSI', 'VND', 'DIG', 'SHB', 'HPG', 'VPB', 'GEX', 'MBB', 'VHM', 'VIC', 'VGI']
    kq_sao = []
    
    vni_c = vni['Close'].values.flatten()
    vni_change = (vni_c[-1] / vni_c[-5] - 1) * 100
    
    with st.spinner("Đang check tín hiệu dòng tiền..."):
        for t in watch_list:
            d = yf.download(f"{t}.VN", period="20d", progress=False)
            if not d.empty:
                d = calculate_all(d, vni)
                l = d.iloc[-1]
                # Logic xác nhận nổ từ code của bạn
                trigger_p = d['High'].iloc[-2:].max()
                rs_score = round(l['RS'], 2)
                
                if l['Close'] >= trigger_p and rs_score > 0:
                    advice = ">>> MUA <<<"
                    status = "XÁC NHẬN NỔ 🔥"
                elif l['Close'] >= trigger_p and rs_score <= 0:
                    advice = "BẪY BULLTRAP ⚠️"
                    status = "HỒI ẢO"
                else:
                    advice = "Theo dõi"
                    status = "Đang rũ"
                
                kq_sao.append({
                    "Mã": t, "Giá Live": int(l['Close']), "Điểm RS": rs_score,
                    "Tín Hiệu": status, "Lời Khuyên": advice,
                    "Target": int(l['Close']*1.15), "Stoploss": int(l['Close']*0.93)
                })
        st.table(pd.DataFrame(kq_sao))
        st.caption("💡 CẢNH BÁO: Chỉ vào lệnh khi tín hiệu là '>>> MUA <<<' và RS dương.")

# --- CHỨC NĂNG 2: LỌC ĐIỂM MUA & BOM ---
if btn_loc:
    st.subheader("🔍 Kết Quả Lọc Điểm Mua & Quả Bom")
    # Tự động lấy list từ file hose.csv nếu có
    try:
        mã_list = pd.read_csv("hose.csv")['symbol'].tolist()[:100]
    except:
        mã_list = ['VGI', 'DIG', 'DXG', 'GEX', 'HPG', 'SSI', 'PDR', 'VNM']
        
    kq_loc = []
    bar = st.progress(0)
    for i, m in enumerate(mã_list):
        d = yf.download(f"{m}.VN", period="60d", progress=False)
        if not d.empty:
            d = calculate_all(d, vni)
            l = d.iloc[-1]
            if l['BUY'] or l['BOMB']:
                kq_loc.append({
                    "Mã": m, "Giá": int(l['Close']), "ADX": round(l['ADX'],1), 
                    "RSI": round(l['RSI'],1), "Trạng Thái": "MUA 🚀" if l['BUY'] else "BOM 💣"
                })
        bar.progress((i+1)/len(mã_list))
    st.dataframe(pd.DataFrame(kq_loc), use_container_width=True)

# --- CHỨC NĂNG 3: SOI CHI TIẾT CHART ---
if ticker_input:
    df = yf.download(f"{ticker_input}.VN", period="1y", progress=False)
    if not df.empty:
        df = calculate_all(df, vni)
        l = df.iloc[-1]
        
        # Vẽ biểu đồ 3 tầng
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.2, 0.3])
        
        # Tầng 1: Nến + Target + Buy/Bom
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'), row=1, col=1)
        
        t1, sl = float(l['Close']*1.07), float(l['Close']*0.94)
        fig.add_hline(y=t1, line_dash="dash", line_color="lime", annotation_text="Target 1 (7%)", row=1, col=1)
        fig.add_hline(y=sl, line_dash="dash", line_color="red", annotation_text="Stoploss", row=1, col=1)

        buy_df = df[df['BUY']]
        fig.add_trace(go.Scatter(x=buy_df.index, y=buy_df['Low']*0.98, mode='markers+text', text="MUA", marker=dict(symbol='triangle-up', size=15, color='lime')), row=1, col=1)
        bomb_df = df[df['BOMB']]
        fig.add_trace(go.Scatter(x=bomb_df.index, y=bomb_df['High']*1.02, mode='text', text="💣"), row=1, col=1)

        # Tầng 2: Volume
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Khối lượng', marker_color='gray'), row=2, col=1)

        # Tầng 3: ADX & RSI & RS
        fig.add_trace(go.Scatter(x=df.index, y=df['ADX'], line=dict(color='cyan'), name='ADX'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='orange'), name='RSI'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RS'], line=dict(color='magenta', dash='dot'), name='Điểm RS'), row=3, col=1)
        
        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
