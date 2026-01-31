import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Hệ Thống Săn Sóng V17.2", layout="wide")

# --- HÀM TÍNH TOÁN KỸ THUẬT SIÊU CẤP ---
def tinh_toan_chuyen_sau(df, df_vni=None):
    # Ép kiểu dữ liệu để tránh lỗi "nan"
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = pd.to_numeric(df[col].to_numpy().flatten(), errors='coerce')
    
    close = df['Close']
    high = df['High']
    low = df['Low']
    
    # 1. Tính ADX Wilder chuẩn
    period = 14
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    up_move = high.diff(1)
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr)
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan))
    df['ADX'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # 2. Tính RSI & RS (Sức mạnh tương quan)
    df['RSI'] = 100 - (100 / (1 + (close.diff().where(close.diff() > 0, 0).ewm(alpha=1/14).mean() / 
                                  (-close.diff().where(close.diff() < 0, 0)).ewm(alpha=1/14).mean())))
    
    if df_vni is not None:
        # RS = (Giá CP / Giá VNI) * 100
        df['RS'] = (df['Close'] / df_vni['Close'].reindex(df.index, method='ffill')) * 100
    
    # 3. Quả Bom (Volatility Squeeze) & Điểm Mua
    df['SMA20'] = close.rolling(20).mean()
    df['BB_W'] = (close.rolling(20).std() * 4) / df['SMA20']
    df['BOMB'] = df['BB_W'] <= df['BB_W'].rolling(20).min()
    df['VOL_SMA10'] = df['Volume'].rolling(10).mean()
    df['IS_BUY'] = (df['Volume'] > df['VOL_SMA10'] * 1.3) & (close > df['Open']) & (df['ADX'] > 20)
    
    return df

# --- GIAO DIỆN APP ---
st.title("🛡️ TRẠM PHÂN TÍCH SIÊU CẤP V17.2")

with st.sidebar:
    st.header("⚡ BẢNG ĐIỀU KHIỂN")
    if st.button("🔄 Cập nhật Data (Download_hose)"):
        st.toast("Đang đồng bộ dữ liệu mới nhất từ Yahoo Finance...")
        # Logic này tự động chạy khi yf.download được gọi với mã mới
    
    btn_scan_hose = st.button("🔍 Quét Siêu Sao (ADX > 20)")
    btn_scan_buy = st.button("🎯 Tìm Điểm Mua & Quả Bom")

# Tải dữ liệu VNINDEX để tính RS
vni_data = yf.download("^VNINDEX", period="1y", progress=False)

# --- PHẦN SOI CHI TIẾT CHART ---
ticker = st.text_input("🔍 NHẬP MÃ CỔ PHIẾU:", value="DIG").upper().strip()

if ticker:
    df = yf.download(f"{ticker}.VN", period="1y", progress=False)
    if not df.empty:
        df = tinh_toan_chuyen_sau(df, vni_data)
        last = df.iloc[-1]
        
        # Chỉ số sức khỏe
        t1, sl = float(last['Close'] * 1.07), float(last['Close'] * 0.94)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Giá", f"{int(last['Close']):,}")
        c2.metric("ADX (Sóng)", f"{last['ADX']:.1f}")
        c3.metric("RSI", f"{last['RSI']:.1f}")
        c4.metric("RS (Sức mạnh)", f"{last['RS']:.2f}")

        # Đồ thị 3 tầng chuẩn
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                           row_heights=[0.5, 0.2, 0.3],
                           subplot_titles=("GIÁ - ĐIỂM MUA - QUẢ BOM 💣", "VOLUME", "CHỈ BÁO ADX - RSI - RS"))

        # Tầng 1: Candle + MUA + BOM
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'), row=1, col=1)
        
        # Điểm MUA (Tam giác xanh)
        buys = df[df['IS_BUY']]
        fig.add_trace(go.Scatter(x=buys.index, y=buys['Low']*0.98, mode='markers+text', text="MUA", marker=dict(symbol='triangle-up', size=12, color='lime'), name='MUA'), row=1, col=1)
        
        # Quả BOM (Icon 💣)
        bombs = df[df['BOMB']]
        fig.add_trace(go.Scatter(x=bombs.index, y=bombs['High']*1.02, mode='text', text="💣", textfont=dict(size=18), name='BOM'), row=1, col=1)

        # Target 1 & Stoploss
        fig.add_hline(y=t1, line=dict(color="lime", dash="dash"), annotation_text=f"T1: {int(t1):,}", row=1, col=1)
        fig.add_hline(y=sl, line=dict(color="red", dash="dash"), annotation_text=f"SL: {int(sl):,}", row=1, col=1)

        # Tầng 2: Volume
        v_colors = ['red' if c < o else 'green' for c, o in zip(df['Close'], df['Open'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors, name='Vol'), row=2, col=1)

        # Tầng 3: Chỉ báo
        fig.add_trace(go.Scatter(x=df.index, y=df['ADX'], line=dict(color='cyan', width=2), name='ADX'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='orange', width=2), name='RSI'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RS'], line=dict(color='magenta', width=1, dash='dot'), name='RS (vs VNI)'), row=3, col=1)
        fig.add_hline(y=23, line_dash="dash", line_color="white", row=3, col=1)

        fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Báo cáo sức khỏe CP
        suc_khoe = "KHỎE 💪" if last['RS'] > df['RS'].tail(10).mean() and last['ADX'] > 23 else "YẾU ⚠️"
        st.info(f"🚩 **Đánh giá nhanh {ticker}:** Trạng thái: **{suc_khoe}**. ADX {last['ADX']:.1f} cho thấy xu hướng {'đã hình thành' if last['ADX']>23 else 'đang tích lũy'}. RS đạt {last['RS']:.2f}.")
