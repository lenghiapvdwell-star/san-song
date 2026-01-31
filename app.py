import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Hệ Thống Săn Sóng V17.3", layout="wide")

# --- HÀM TÍNH TOÁN KỸ THUẬT SIÊU CẤP ---
def tinh_toan_chuyen_sau(df, df_vni=None):
    # Fix lỗi MultiIndex và ép kiểu về 1D Series
    df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    df.columns = df.columns.str.capitalize()
    
    close = pd.Series(df['Close'].values.flatten(), index=df.index)
    high = pd.Series(df['High'].values.flatten(), index=df.index)
    low = pd.Series(df['Low'].values.flatten(), index=df.index)
    open_p = pd.Series(df['Open'].values.flatten(), index=df.index)
    volume = pd.Series(df['Volume'].values.flatten(), index=df.index)
    
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
    
    # 2. Tính RSI & RS
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
    
    if df_vni is not None:
        vni_close = pd.Series(df_vni['Close'].values.flatten(), index=df_vni.index)
        df['RS'] = (close / vni_close.reindex(df.index, method='ffill')) * 100
    
    # 3. Quả Bom & Điểm Mua
    df['SMA20'] = close.rolling(20).mean()
    df['BB_W'] = (close.rolling(20).std() * 4) / df['SMA20']
    df['BOMB'] = df['BB_W'] <= df['BB_W'].rolling(20).min()
    df['VOL_SMA10'] = volume.rolling(10).mean()
    df['IS_BUY'] = (volume > df['VOL_SMA10'] * 1.3) & (close > open_p) & (df['ADX'] > 20)
    
    return df

# --- GIAO DIỆN APP ---
st.title("🛡️ TRẠM PHÂN TÍCH SIÊU CẤP V17.3")

with st.sidebar:
    st.header("⚡ BẢNG ĐIỀU KHIỂN")
    if st.button("🔄 Cập nhật Data"):
        st.cache_data.clear()
        st.toast("Đã làm mới bộ nhớ đệm!")
    
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
        c4.metric("RS (Sức mạnh)", f"{last['RS']:.2f}" if 'RS' in df else "N/A")

        # Đồ thị 3 tầng
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                           row_heights=[0.5, 0.2, 0.3],
                           subplot_titles=("GIÁ - ĐIỂM MUA - QUẢ BOM 💣", "VOLUME", "CHỈ BÁO ADX - RSI - RS"))

        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'), row=1, col=1)
        
        # Điểm MUA & BOM
        buys = df[df['IS_BUY']]
        fig.add_trace(go.Scatter(x=buys.index, y=buys['Low']*0.98, mode='markers+text', text="MUA", marker=dict(symbol='triangle-up', size=12, color='lime'), name='MUA'), row=1, col=1)
        
        bombs = df[df['BOMB']]
        fig.add_trace(go.Scatter(x=bombs.index, y=bombs['High']*1.02, mode='text', text="💣", textfont=dict(size=18), name='BOM'), row=1, col=1)

        # Target 1 & Stoploss
        fig.add_hline(y=t1, line=dict(color="lime", dash="dash"), annotation_text=f"T1: {int(t1):,}", row=1, col=1)
        fig.add_hline(y=sl, line=dict(color="red", dash="dash"), annotation_text=f"SL: {int(sl):,}", row=1, col=1)

        # Tầng 2: Volume
        v_colors = ['red' if c < o else 'green' for
