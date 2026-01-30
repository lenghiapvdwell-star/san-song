import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta

# Cấu hình giao diện Mobile-First
st.set_page_config(page_title="Săn Sóng ADX V15", layout="wide")

# --- HÀM TÍNH TOÁN CHUẨN WILDER ---
def tinh_chi_bao(df, period=14):
    # Tính ADX
    high, low, close = df['high'], df['low'], df['close']
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    up_move = high.diff(1)
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (pd.Series(plus_dm).ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm).ewm(alpha=1/period, adjust=False).mean() / atr)
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan))
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # Tính RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
    
    # Quả bom & Điểm mua
    df['sma20'] = close.rolling(20).mean()
    df['bb_w'] = (close.rolling(20).std() * 4) / df['sma20']
    df['bomb'] = df['bb_w'] <= df['bb_w'].rolling(20).min()
    df['vol_sma10'] = df['volume'].rolling(10).mean()
    df['is_buy'] = (df['volume'] > df['vol_sma10'] * 0.8) & (close > df['open']) & (df['adx'] > 20)
    return df

# --- GIAO DIỆN APP ---
st.title("🌊 Hệ Thống Săn Sóng ADX")

tab1, tab2 = st.tabs(["🔍 BỘ LỌC", "📈 ĐỒ THỊ"])

with tab1:
    st.subheader("Danh sách siêu phẩm (ADX > 20)")
    # Danh sách mã HOSE tiêu biểu (Vì trên web app không đọc được file CSV cục bộ của bạn)
    danh_sach = ['VGI', 'DIG', 'DXG', 'GEX', 'HPG', 'SSI', 'VNM', 'FPT', 'TCB', 'MBB', 'PDR', 'CII', 'HHV', 'KBC', 'DGC']
    
    if st.button("🚀 BẮT ĐẦU QUÉT MÃ", use_container_width=True):
        kq = []
        bar = st.progress(0)
        for i, m in enumerate(danh_sach):
            df = yf.download(f"{m}.VN", period="60d", progress=False, auto_adjust=True)
            if not df.empty:
                df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
                df.columns = [col.lower() for col in df.columns]
                df = tinh_chi_bao(df)
                last = df.iloc[-1]
                if last['adx'] > 20:
                    status = "💣 NÉN" if last['bomb'] else "🔥 CHẠY"
                    kq.append({"Mã": m, "Giá": int(last['close']), "ADX": round(last['adx'],1), "Trạng thái": status})
            bar.progress((i+1)/len(danh_sach))
        
        st.dataframe(pd.DataFrame(kq), use_container_width=True)

with tab2:
    ticker = st.text_input("Nhập mã cổ phiếu:", value="DIG").upper()
    if ticker:
        df_plot = yf.download(f"{ticker}.VN", period="1y", progress=False, auto_adjust=True)
        if not df_plot.empty:
            df_plot.columns = [col[0] if isinstance(col, tuple) else col for col in df_plot.columns]
            df_plot.columns = [col.lower() for col in df_plot.columns]
            df_plot = tinh_chi_bao(df_plot)
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
            # Nến & Điểm mua
            fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'], name='Giá'), row=1, col=1)
            
            buy_points = df_plot[df_plot['is_buy']]
            fig.add_trace(go.Scatter(x=buy_points.index, y=buy_points['low']*0.97, mode='text', text="▲ MUA", textfont=dict(color="lime", size=15), name='MUA'), row=1, col=1)

            # ADX & RSI
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['adx'], name='ADX', line=dict(color='cyan', width=2)), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['rsi'], name='RSI', line=dict(color='orange', width=2)), row=2, col=1)
            fig.add_hline(y=23, line_dash="dash", line_color="white", row=2, col=1)

            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=5, r=5, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
