import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os

# 1. CẤU HÌNH GIAO DIỆN
st.set_page_config(page_title="Săn Sóng Siêu Cấp V18", layout="wide")

# 2. HÀM TÍNH TOÁN (Logic gộp từ sieu_loc_adx và loc_diem_mua)
def calculate_all(df, df_vni=None):
    # Dọn dẹp dữ liệu
    df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    df.columns = df.columns.str.capitalize()
    
    close = pd.Series(df['Close'].values.flatten(), index=df.index)
    high = pd.Series(df['High'].values.flatten(), index=df.index)
    low = pd.Series(df['Low'].values.flatten(), index=df.index)
    vol = pd.Series(df['Volume'].values.flatten(), index=df.index)

    # ADX Wilder
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    up = high.diff(); dw = low.shift(1) - low
    p_dm = np.where((up > dw) & (up > 0), up, 0)
    m_dm = np.where((dw > up) & (dw > 0), dw, 0)
    atr = tr.ewm(alpha=1/14, adjust=False).mean()
    p_di = 100 * (pd.Series(p_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr)
    m_di = 100 * (pd.Series(m_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr)
    dx = 100 * (abs(p_di - m_di) / (p_di + m_di).replace(0, np.nan))
    df['ADX'] = dx.ewm(alpha=1/14, adjust=False).mean()

    # RSI & RS (So với VN-Index)
    df['RSI'] = 100 - (100 / (1 + (close.diff().where(close.diff() > 0, 0).ewm(alpha=1/14).mean() / 
                                  (-close.diff().where(close.diff() < 0, 0)).ewm(alpha=1/14).mean())))
    if df_vni is not None:
        vni_close = pd.Series(df_vni['Close'].values.flatten(), index=df_vni.index)
        df['RS'] = (close / vni_close.reindex(df.index, method='ffill')) * 100

    # Quả Bom (Squeeze) & Điểm Mua
    df['SMA20'] = close.rolling(20).mean()
    df['BW'] = (close.rolling(20).std() * 4) / df['SMA20']
    df['BOMB'] = df['BW'] <= df['BW'].rolling(20).min()
    df['VOL_SMA'] = vol.rolling(10).mean()
    df['BUY'] = (vol > df['VOL_SMA'] * 1.3) & (close > df['Open'].values.flatten()) & (df['ADX'] > 20)
    
    return df

# 3. SIDEBAR - ĐIỀU KHIỂN
with st.sidebar:
    st.header("⚡ HỆ THỐNG V18")
    if st.button("🚀 CẬP NHẬT & TẢI DATA"):
        st.cache_data.clear()
        st.success("Đã tải lại dữ liệu phiên mới nhất!")
    
    btn_loc = st.button("🔍 SIÊU LỌC CỔ PHIẾU")
    ticker = st.text_input("📈 NHẬP MÃ SOI CHART:", value="DIG").upper()

# Tải VNI để tính RS
vni = yf.download("^VNINDEX", period="1y", progress=False)

# 4. XỬ LÝ LỌC CỔ (Logic từ download_hose + loc_diem_mua)
if btn_loc:
    st.subheader(" danh sách Cổ Phiếu Có Điểm Mua & Bom 💣")
    # Sử dụng danh sách từ file hose.csv của bạn hoặc list mẫu nếu chưa load được file
    mã_list = ['VGI', 'DIG', 'DXG', 'GEX', 'HPG', 'SSI', 'PDR', 'VNM', 'FPT', 'TCB']
    kq = []
    bar = st.progress(0)
    for i, m in enumerate(mã_list):
        d = yf.download(f"{m}.VN", period="60d", progress=False)
        if not d.empty:
            d = calculate_all(d, vni)
            l = d.iloc[-1]
            if l['BUY'] or l['BOMB']:
                kq.append({"Mã": m, "Giá": int(l['Close']), "ADX": round(l['ADX'],1), "Tín Hiệu": "MUA 🚀" if l['BUY'] else "BOM 💣"})
        bar.progress((i+1)/len(mã_list))
    st.table(pd.DataFrame(kq))

# 5. HIỂN THỊ CHART (Yêu cầu đầy đủ RSI, ADX, VOL, MUA, BOM, TARGET)
if ticker:
    df = yf.download(f"{ticker}.VN", period="1y", progress=False)
    if not df.empty:
        df = calculate_all(df, vni)
        l = df.iloc[-1]
        
        # Chỉ số Metric
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("GIÁ", f"{int(l['Close']):,}")
        c2.metric("ADX", f"{l['ADX']:.1f}")
        c3.metric("RSI", f"{l['RSI']:.1f}")
        c4.metric("RS", f"{l['RS']:.2f}")

        # Vẽ đồ thị
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.2, 0.3])
        
        # Tầng 1: Nến + Target + Buy/Bom
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'), row=1, col=1)
        
        # Target 1 (7%) & Stoploss (6%)
        t1, sl = float(l['Close']*1.07), float(l['Close']*0.94)
        fig.add_hline(y=t1, line_dash="dash", line_color="lime", annotation_text="Target 1", row=1, col=1)
        fig.add_hline(y=sl, line_dash="dash", line_color="red", annotation_text="Cắt lỗ", row=1, col=1)

        # Mua & Bom
        buy_df = df[df['BUY']]
        fig.add_trace(go.Scatter(x=buy_df.index, y=buy_df['Low']*0.98, mode='markers+text', text="MUA", marker=dict(symbol='triangle-up', size=15, color='lime')), row=1, col=1)
        bomb_df = df[df['BOMB']]
        fig.add_trace(go.Scatter(x=bomb_df.index, y=bomb_df['High']*1.02, mode='text', text="💣"), row=1, col=1)

        # Tầng 2: Volume
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Khối lượng', marker_color='gray'), row=2, col=1)

        # Tầng 3: ADX & RSI & RS
        fig.add_trace(go.Scatter(x=df.index, y=df['ADX'], line=dict(color='cyan'), name='ADX'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='orange'), name='RSI'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RS'], line=dict(color='magenta', dash='dot'), name='RS (Sức mạnh)'), row=3, col=1)
        
        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
