import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Hệ Thống Săn Sóng V20 - Local Data", layout="wide")

# --- HÀM TÍNH TOÁN KỸ THUẬT (SỬ DỤNG DATA CÓ SẴN) ---
def calculate_technical_indices(df, df_vni=None):
    if df is None or len(df) < 5:
        return None
    
    # Chuẩn hóa tên cột về chữ thường để khớp với file CSV của bạn
    df.columns = df.columns.str.lower()
    
    close = df['close']
    high = df['high']
    low = df['low']
    open_p = df['open']
    vol = df['volume']

    # 1. RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
    
    # 2. RS (So sánh với file VNINDEX.csv đã có)
    df['rs_score'] = 0.0
    if df_vni is not None and len(df_vni) >= 5:
        df_vni.columns = df_vni.columns.str.lower()
        vni_close = df_vni['close']
        vni_change = (vni_close.iloc[-1] / vni_close.iloc[-5] - 1) * 100
        stock_change = (close.iloc[-1] / close.iloc[-5] - 1) * 100
        df['rs_score'] = round(stock_change - vni_change, 2)
    
    # 3. ADX & Điểm Mua & Quả Bom (Cần tối thiểu 20 phiên)
    if len(df) >= 20:
        # ADX Simple
        tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/14, adjust=False).mean()
        # Tính ADX đơn giản hóa để tránh lỗi Index
        df['adx'] = (atr / close * 100).rolling(14).mean() # Chỉ số biến động
        
        df['sma20'] = close.rolling(20).mean()
        df['bw'] = (close.rolling(20).std() * 4) / df['sma20']
        df['bomb'] = df['bw'] <= df['bw'].rolling(20).min()
        df['vol_sma10'] = vol.rolling(10).mean()
        df['is_buy'] = (vol > df['vol_sma10'] * 1.3) & (close > open_p)
    else:
        df['adx'] = 0; df['bomb'] = False; df['is_buy'] = False
        
    return df

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚡ HỆ THỐNG V20 (OFFLINE)")
    btn_sieu_sao = st.button("🌟 SIÊU SAO THEO DÕI")
    ticker_input = st.text_input("📈 SOI CHI TIẾT MÃ:", value="DIG").upper().strip()
    st.info("Dữ liệu được lấy từ: `hose.csv` và `VNINDEX.csv` trên GitHub của bạn.")

# --- ĐỌC DỮ LIỆU TỪ FILE ---
try:
    df_hose_all = pd.read_csv("hose.csv")
    df_vni_all = pd.read_csv("VNINDEX.csv")
    data_ready = True
except Exception as e:
    st.error(f"Lỗi đọc file CSV: {e}. Vui lòng kiểm tra file hose.csv và VNINDEX.csv")
    data_ready = False

# --- CHỨC NĂNG: SIÊU SAO THEO DÕI ---
if data_ready and btn_sieu_sao:
    st.subheader("🔥 Tổng Quan Siêu Sao (Dữ liệu từ hose.csv)")
    watch_list = ['SSI', 'VND', 'DIG', 'SHB', 'HPG', 'VPB', 'GEX', 'MBB', 'VHM', 'VIC', 'VGI']
    kq = []
    
    for t in watch_list:
        df_mã = df_hose_all[df_hose_all['symbol'] == t].copy().sort_values('date')
        if not df_mã.empty:
            df_mã = calculate_technical_indices(df_mã, df_vni_all)
            l = df_mã.iloc[-1]
            
            trigger_p = df_mã['high'].iloc[-2:].max()
            status = "XÁC NHẬN NỔ 🔥" if l['close'] >= trigger_p and l['rs_score'] > 0 else "Theo dõi"
            
            kq.append({
                "Mã": t, "Giá": int(l['close']), "Điểm RS": l['rs_score'],
                "Trạng Thái": status, "RSI": round(l['rsi'], 1),
                "Target": int(l['close'] * 1.15), "Stoploss": int(l['close'] * 0.93)
            })
    st.table(pd.DataFrame(kq))

# --- CHỨC NĂNG: SOI CHI TIẾT CHART ---
if data_ready and ticker_input:
    df_chart = df_hose_all[df_hose_all['symbol'] == ticker_input].copy().sort_values('date')
    if not df_chart.empty:
        df_chart = calculate_technical_indices(df_chart, df_vni_all)
        l = df_chart.iloc[-1]

        # Đồ thị 3 tầng
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.2, 0.3])
        
        # Tầng 1: Candle
        fig.add_trace(go.Candlestick(x=df_chart['date'], open=df_chart['open'], high=df_chart['high'], 
                                     low=df_chart['low'], close=df_chart['close'], name='Giá'), row=1, col=1)
        
        # Target & Stoploss
        t1, sl = float(l['close']*1.07), float(l['close']*0.94)
        fig.add_hline(y=t1, line_dash="dash", line_color="lime", annotation_text="T1", row=1, col=1)
        fig.add_hline(y=sl, line_dash="dash", line_color="red", annotation_text="SL", row=1, col=1)

        # MUA & BOM
        buy_pts = df_chart[df_chart['is_buy']]
        fig.add_trace(go.Scatter(x=buy_pts['date'], y=buy_pts['low']*0.98, mode='markers', 
                                 marker=dict(symbol='triangle-up', size=12, color='lime'), name='MUA'), row=1, col=1)
        
        bomb_pts = df_chart[df_chart['bomb']]
        fig.add_trace(go.Scatter(x=bomb_pts['date'], y=bomb_pts['high']*1.02, mode='text', text="💣", name='BOM'), row=1, col=1)

        # Tầng 2: Volume
        fig.add_trace(go.Bar(x=df_chart['date'], y=df_chart['volume'], name='Vol', marker_color='gray'), row=2, col=1)

        # Tầng 3: Chỉ báo
        fig.add_trace(go.Scatter(x=df_chart['date'], y=df_chart['rsi'], line=dict(color='orange'), name='RSI'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_chart['date'], y=df_chart['rs_score'], line=dict(color='magenta', dash='dot'), name='RS Score'), row=3, col=1)
        
        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"Không tìm thấy mã {ticker_input} trong file hose.csv")
