import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import os

# 1. CẤU HÌNH GIAO DIỆN MOBILE
st.set_page_config(page_title="ADX Scanner V16", layout="wide")

# CSS để nút bấm trông chuyên nghiệp hơn trên điện thoại
st.markdown("""
    <style>
    .stButton>button { width: 100%; height: 3em; background-color: #00ffcc; color: black; font-weight: bold; border-radius: 10px; }
    .stTextInput>div>div>input { background-color: #1e1e1e; color: #00ffcc; }
    </style>
    """, unsafe_allow_html=True)

# 2. HÀM TÍNH TOÁN KỸ THUẬT (CHUẨN WILDER)
def tinh_chi_bao(df, period=14):
    high, low, close = df['high'], df['low'], df['close']
    
    # Tính ADX chuẩn
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
    
    # Tính RSI chuẩn
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
    
    # Quả bom & Điểm mua (Nhạy trong phiên)
    df['sma20'] = close.rolling(20).mean()
    df['bb_w'] = (close.rolling(20).std() * 4) / df['sma20']
    df['bomb'] = df['bb_w'] <= df['bb_w'].rolling(20).min()
    df['vol_sma10'] = df['volume'].rolling(10).mean()
    df['is_buy'] = (df['volume'] > df['vol_sma10'] * 0.8) & (close > df['open']) & (df['adx'] > 20)
    return df

# 3. GIAO DIỆN CHÍNH
st.title("🚀 ADX SMART SCANNER")

tab1, tab2 = st.tabs(["🔍 BỘ LỌC HOSE", "📈 SOI ĐỒ THỊ"])

with tab1:
    st.info("Hệ thống quét dữ liệu từ file hose.csv trên GitHub của bạn.")
    
    if st.button("🔥 NHẤN ĐỂ QUÉT SIÊU PHẨM (ADX > 20)"):
        try:
            # Đọc danh sách mã từ file bạn đã upload lên GitHub
            if os.path.exists("hose.csv"):
                df_hose = pd.read_csv("hose.csv")
                danh_sach = df_hose['symbol'].unique().tolist()
            else:
                st.warning("Không tìm thấy file hose.csv. Đang dùng danh sách mặc định.")
                danh_sach = ['VGI', 'DIG', 'DXG', 'GEX', 'HPG', 'SSI', 'CII', 'PDR', 'VNM', 'FPT']

            # Giới hạn quét 50-100 mã để app chạy nhanh trên mobile
            danh_sach = danh_sach[:100]
            
            ket_qua = []
            progress_text = st.empty()
            bar = st.progress(0)

            for i, m in enumerate(danh_sach):
                progress_text.text(f"Đang kiểm tra: {m}")
                df = yf.download(f"{m}.VN", period="60d", progress=False, auto_adjust=True)
                if not df.empty and len(df) > 30:
                    df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
                    df.columns = [col.lower() for col in df.columns]
                    df = tinh_chi_bao(df)
                    last = df.iloc[-1]
                    
                    if last['adx'] >= 20:
                        status = "💣 NÉN" if last['bomb'] else "🚀 CHẠY"
                        ket_qua.append({
                            "Mã": m, 
                            "Giá": f"{int(last['close']):,}", 
                            "ADX": round(last['adx'], 1), 
                            "RSI": round(last['rsi'], 1),
                            "Trạng thái": status
                        })
                bar.progress((i + 1) / len(danh_sach))
            
            progress_text.empty()
            if ket_qua:
                df_res = pd.DataFrame(ket_qua).sort_values(by='ADX', ascending=False)
                st.success(f"Tìm thấy {len(df_res)} mã đạt tiêu chuẩn!")
                st.dataframe(df_res, use_container_width=True)
            else:
                st.error("Không tìm thấy mã nào có ADX > 20.")
        except Exception as e:
            st.error(f"Lỗi: {e}")

with tab2:
    ticker = st.text_input("NHẬP MÃ CẦN SOI (VD: DIG, VGI):", value="").upper().strip()
    
    if ticker:
        with st.spinner(f"Đang phân tích {ticker}..."):
            df_plot = yf.download(f"{ticker}.VN", period="1y", progress=False, auto_adjust=True)
            if not df_plot.empty:
                df_plot.columns = [col[0] if isinstance(col, tuple) else col for col in df_plot.columns]
                df_plot.columns = [col.lower() for col in df_plot.columns]
                df_plot = tinh_chi_bao(df_plot)
                
                # Vẽ biểu đồ
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.7, 0.3])
                
                # Nến & Điểm mua
                fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'], name='Nến Giá'), row=1, col=1)
                
                # Vẽ icon MUA và BOM
                buys = df_plot[df_plot['is_buy']]
                fig.add_trace(go.Scatter(x=buys.index, y=buys['low']*0.97, mode='text', text="▲ MUA", textfont=dict(color="#00ff00", size=14), name='Điểm Mua'), row=1, col=1)
                
                bombs = df_plot[df_plot['bomb']]
                fig.add_trace(go.Scatter(x=bombs.index, y=bombs['high']*1.03, mode='markers', marker=dict(symbol='star', size=10, color='orange'), name='Tích lũy 💣'), row=1, col=1)

                # ADX & RSI
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['adx'], name='ADX (Sóng)', line=dict(color='cyan', width=2)), row=2, col=1)
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['rsi'], name='RSI', line=dict(color='orange', width=1.5)), row=2, col=1)
                fig.add_hline(y=23, line_dash="dash", line_color="white", row=2, col=1)

                fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=5, r=5, t=10, b=10), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                # Bảng thông số nhanh
                l = df_plot.iloc[-1]
                st.write(f"**Giá:** {int(l['close']):,} | **ADX:** {round(l['adx'],1)} | **RSI:** {round(l['rsi'],1)}")
            else:
                st.error("Mã không tồn tại hoặc lỗi dữ liệu.")
