import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import os

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Hệ Thống Săn Sóng V17", layout="wide")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
    .buy-btn { background-color: #00ff00; color: black; }
    .info-box { background-color: #1e1e1e; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- HÀM TÍNH TOÁN (TỪ SIEU_LOC_ADX_V12 & LOC_DIEM_MUA) ---
def tinh_toan_full(df, period=14):
    high, low, close = df['high'], df['low'], df['close']
    
    # ADX Wilder
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    up_move = high.diff(1); down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (pd.Series(plus_dm).ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm).ewm(alpha=1/period, adjust=False).mean() / atr)
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan))
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
    
    # Logic Quả Bom & Điểm Mua (Từ loc_diem_mua.py)
    df['sma20'] = close.rolling(20).mean()
    df['bb_w'] = (close.rolling(20).std() * 4) / df['sma20']
    df['bomb'] = df['bb_w'] <= df['bb_w'].rolling(20).min()
    df['vol_sma10'] = df['volume'].rolling(10).mean()
    
    # Tín hiệu MUA chuẩn
    df['is_buy'] = (df['volume'] > df['vol_sma10'] * 1.2) & (close > df['open']) & (df['adx'] > 20)
    return df

# --- GIAO DIỆN CHÍNH ---
st.title("🛡️ TRẠM PHÂN TÍCH SIÊU CẤP V17")

# Sidebar - Các nút chức năng từ các file của bạn
with st.sidebar:
    st.header("⚡ BẢNG ĐIỀU KHIỂN")
    btn_scan_hose = st.button("🔍 Quét ADX > 20 (V12)")
    btn_scan_buy = st.button("🎯 Tìm Điểm Mua (Loc_diem_mua)")
    btn_update_data = st.button("🔄 Cập nhật Data (Download_hose)")
    st.divider()
    st.write("Dữ liệu: `hose.csv` & `vnindex.csv` đã tải lên.")

# --- XỬ LÝ NÚT NHẤN QUÉT MÃ ---
if btn_scan_hose or btn_scan_buy:
    st.subheader("📊 Kết quả quét danh sách")
    if os.path.exists("hose.csv"):
        danh_sach = pd.read_csv("hose.csv")['symbol'].unique().tolist()[:100] # Quét 100 mã điểm hình
        kq = []
        bar = st.progress(0)
        for i, m in enumerate(danh_sach):
            df = yf.download(f"{m}.VN", period="60d", progress=False, auto_adjust=True)
            if not df.empty:
                df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]; df.columns = [col.lower() for col in df.columns]
                df = tinh_toan_full(df)
                last = df.iloc[-1]
                
                # Lọc theo yêu cầu của từng nút
                if btn_scan_hose and last['adx'] > 20:
                    kq.append({"Mã": m, "Giá": int(last['close']), "ADX": round(last['adx'],1), "RSI": round(last['rsi'],1)})
                elif btn_scan_buy and last['is_buy']:
                    kq.append({"Mã": m, "Giá": int(last['close']), "Tín hiệu": "🚀 MUA NGAY", "Vol": int(last['volume'])})
            bar.progress((i+1)/len(danh_sach))
        
        if kq: st.dataframe(pd.DataFrame(kq), use_container_width=True)
        else: st.warning("Chưa tìm thấy mã đạt tiêu chuẩn hôm nay.")
    else:
        st.error("Không tìm thấy file hose.csv trên GitHub!")

# --- PHẦN SOI CHI TIẾT CHART (YÊU CẦU CỦA BẠN) ---
st.divider()
ticker = st.text_input("🔍 NHẬP MÃ CỔ PHIẾU ĐỂ SOI CHI TIẾT:", value="DIG").upper()

if ticker:
    df = yf.download(f"{ticker}.VN", period="1y", progress=False, auto_adjust=True)
    if not df.empty:
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]; df.columns = [col.lower() for col in df.columns]
        df = tinh_toan_full(df)
        last = df.iloc[-1]
        
        # Tính Target & SL
        gia_ht = last['close']
        t1, t2, sl = gia_ht * 1.07, gia_ht * 1.15, gia_ht * 0.94

        # Layout thông số nhanh
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Giá Hiện Tại", f"{int(gia_ht):,}")
        col2.metric("ADX (Sóng)", round(last['adx'], 1))
        col3.metric("RSI", round(last['rsi'], 1))
        col4.metric("Vol/TB10", f"{round(last['volume']/last['vol_sma10'], 1)}x")

        # VẼ ĐỒ THỊ 3 TẦNG (GIÁ, VOL, RSI/ADX)
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                           row_heights=[0.5, 0.2, 0.3],
                           subplot_titles=("GIÁ - ĐIỂM MUA - TARGET", "DÒNG TIỀN (VOLUME)", "CHỈ BÁO (ADX & RSI)"))

        # Tầng 1: Nến + Target + SL + Buy
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Nến Giá'), row=1, col=1)
        
        # Hiện Target/SL bằng đường kẻ ngang cho ngày cuối
        fig.add_shape(type="line", x0=df.index[-10], y0=t1, x1=df.index[-1], y1=t1, line=dict(color="lime", width=2, dash="dash"), row=1, col=1)
        fig.add_trace(go.Scatter(x=[df.index[-1]], y=[t1], mode="text", text=[f" T1: {int(t1):,}"], textposition="middle right", name="Target 1"), row=1, col=1)
        
        fig.add_shape(type="line", x0=df.index[-10], y0=sl, x1=df.index[-1], y1=sl, line=dict(color="red", width=2, dash="dash"), row=1, col=1)
        fig.add_trace(go.Scatter(x=[df.index[-1]], y=[sl], mode="text", text=[f" SL: {int(sl):,}"], textposition="middle right", name="Stoploss"), row=1, col=1)

        # Điểm MUA/BOM
        buy_pts = df[df['is_buy']]
        fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['low']*0.98, mode='markers+text', text="MUA", marker=dict(symbol='triangle-up', size=12, color='lime'), name='Điểm MUA'), row=1, col=1)
        
        # Tầng 2: Volume
        v_color = ['red' if r['open'] > r['close'] else 'green' for _, r in df.iterrows()]
        fig.add_trace(go.Bar(x=df.index, y=df['volume'], marker_color=v_color, name='Vol'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['vol_sma10'], line=dict(color='yellow', width=1), name='TB 10 Phiên'), row=2, col=1)

        # Tầng 3: ADX & RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['adx'], line=dict(color='cyan', width=2), name='ADX'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['rsi'], line=dict(color='orange', width=2), name='RSI'), row=3, col=1)
        fig.add_hline(y=23, line_dash="dash", line_color="white", row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="red", opacity=0.3, row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="green", opacity=0.3, row=3, col=1)

        fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=50, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

        # Chú thích chiến thuật
        st.success(f"💡 **Chiến thuật {ticker}:** Target 1 (7%): **{int(t1):,}**. Cắt lỗ (6%): **{int(sl):,}**. ADX hiện tại {round(last['adx'],1)} cho thấy xu hướng đang {'MẠNH' if last['adx'] > 23 else 'YẾU'}.")
