import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import base64
import requests

# --- CẤU HÌNH ---
GITHUB_TOKEN = "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" 
GITHUB_USER = "lenghiapvdwell-star"
REPO_NAME = "san-song"

st.set_page_config(page_title="Hệ Thống Săn Sóng V23", layout="wide")

# --- HÀM TÍNH TOÁN (ĐẢM BẢO ĐẦY ĐỦ CHỈ BÁO) ---
def calculate_all_signals(df, df_vni=None):
    if df is None or len(df) < 20: return None
    
    # Đồng bộ tên cột
    df.columns = df.columns.str.lower()
    
    # Tính ADX
    high, low, close = df['high'], df['low'], df['close']
    tr = pd.concat([high-low, (high-close.shift(1)).abs(), (low-close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/14, adjust=False).mean()
    up = high.diff(); dw = low.shift(1) - low
    pdm = np.where((up>dw)&(up>0), up, 0); mdm = np.where((dw>up)&(dw>0), dw, 0)
    pdi = 100 * (pd.Series(pdm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr)
    mdi = 100 * (pd.Series(mdm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr)
    dx = 100 * (abs(pdi-mdi)/(pdi+mdi).replace(0, np.nan))
    df['adx_line'] = dx.ewm(alpha=1/14, adjust=False).mean()
    
    # RSI
    df['rsi_line'] = 100 - (100/(1+(close.diff().where(close.diff()>0,0).ewm(alpha=1/14).mean()/(-close.diff().where(close.diff()<0,0)).ewm(alpha=1/14).mean())))

    # LOGIC NỀN 5 THÁNG & DÒNG TIỀN
    df['max_100'] = close.shift(1).rolling(100).max()
    df['min_100'] = close.shift(1).rolling(100).min()
    df['nen_tich_luy'] = (df['max_100'] - df['min_100']) / df['min_100'] < 0.15
    
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['money_in'] = (df['volume'] > df['vol_ma20'] * 1.4) & (close > df['open'])
    
    # TÍN HIỆU: MUA - BOM - TEST SELL
    df['is_buy'] = df['nen_tich_luy'] & (close > df['max_100']) & df['money_in']
    df['bw'] = (close.rolling(20).std() * 4) / close.rolling(20).mean()
    df['is_bomb'] = df['bw'] <= df['bw'].rolling(30).min()
    df['test_sell'] = (close < df['open']) & (df['volume'] > df['vol_ma20'] * 1.5) # Bán tháo mạnh
    
    # RS
    if df_vni is not None:
        v_c = df_vni['close'].values.flatten() if 'close' in df_vni.columns else df_vni['Close'].values.flatten()
        v_change = (v_c[-1]/v_c[-5]-1)*100
        s_change = (close.iloc[-1]/close.iloc[-5]-1)*100
        df['rs_score'] = round(s_change - v_change, 2)
    
    return df

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚡ BẢNG ĐIỀU KHIỂN")
    if st.button("🔄 CẬP NHẬT DỮ LIỆU GITHUB"):
        st.info("Đang xử lý ghi đè file...")
        # Code Push GitHub của bạn ở đây...
        
    mode = st.radio("CHẾ ĐỘ XEM:", ["SOI CHI TIẾT MÃ", "🌟 SIÊU SAO THEO DÕI"])
    ticker_input = st.text_input("NHẬP MÃ:", "DIG").upper()

# --- ĐỌC DATA ---
try:
    vni_df = pd.read_csv("VNINDEX.csv")
    hose_df = pd.read_csv("hose.csv")
except:
    st.error("Thiếu file dữ liệu trên GitHub!")

# --- MÀN HÌNH 1: SIÊU SAO THEO DÕI ---
if mode == "🌟 SIÊU SAO THEO DÕI":
    st.subheader("🚀 Danh Sách Cổ Phiếu Tạo Nền & Có Dòng Tiền")
    kq_list = []
    list_mã = hose_df['symbol'].unique()[:40] # Quét 40 mã
    for m in list_mã:
        d = hose_df[hose_df['symbol'] == m].copy()
        d = calculate_all_signals(d, vni_df)
        if d is not None:
            l = d.iloc[-1]
            if l['nen_tich_luy'] or l['is_buy'] or l['is_bomb']:
                kq_list.append({
                    "Mã": m, "Giá": int(l['close']), "RS": l.get('rs_score', 0),
                    "Trạng Thái": "🔥 BREAKOUT" if l['is_buy'] else ("💣 CHỜ NỔ" if l['is_bomb'] else "🧱 ĐANG NỀN"),
                    "Dòng Tiền": "MẠNH 💪" if l['money_in'] else "BÌNH THƯỜNG"
                })
    st.dataframe(pd.DataFrame(kq_list), use_container_width=True)

# --- MÀN HÌNH 2: CHART CHI TIẾT ---
elif mode == "SOI CHI TIẾT MÃ":
    df_chart = hose_df[hose_df['symbol'] == ticker_input].copy()
    df_chart = calculate_all_signals(df_chart, vni_df)
    
    if df_chart is not None:
        l = df_chart.iloc[-1]
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.2, 0.3])
        
        # Tầng 1: Nến + Buy + Bom + Target
        fig.add_trace(go.Candlestick(x=df_chart['date'], open=df_chart['open'], high=df_chart['high'], low=df_chart['low'], close=df_chart['close'], name=ticker_input), row=1, col=1)
        
        # Điểm MUA & BOM & TEST SELL
        buy_pts = df_chart[df_chart['is_buy']]
        fig.add_trace(go.Scatter(x=buy_pts['date'], y=buy_pts['low']*0.97, mode='markers+text', text="MUA", marker=dict(symbol='triangle-up', size=15, color='lime')), row=1, col=1)
        
        bomb_pts = df_chart[df_chart['is_bomb']]
        fig.add_trace(go.Scatter(x=bomb_pts['date'], y=bomb_pts['high']*1.03, mode='text', text="💣"), row=1, col=1)
        
        sell_pts = df_chart[df_chart['test_sell']]
        fig.add_trace(go.Scatter(x=sell_pts['date'], y=sell_pts['high']*1.03, mode='text', text="🛑 SELL"), row=1, col=1)

        # Target 1, 2 & Stoploss
        p_close = float(l['close'])
        fig.add_hline(y=p_close*1.07, line_dash="dash", line_color="#00ff00", annotation_text="T1 +7%", row=1, col=1)
        fig.add_hline(y=p_close*1.15, line_dash="dash", line_color="#00ffff", annotation_text="T2 +15%", row=1, col=1)
        fig.add_hline(y=p_close*0.94, line_dash="dash", line_color="#ff0000", annotation_text="SL -6%", row=1, col=1)

        # Tầng 2: Volume + Dòng tiền tăng dần (Màu xanh khi có tiền vào)
        colors = ['#00ff00' if m else '#555555' for m in df_chart['money_in']]
        fig.add_trace(go.Bar(x=df_chart['date'], y=df_chart['volume'], marker_color=colors, name="Dòng Tiền"), row=2, col=1)

        # Tầng 3: ADX & RSI & RS
        fig.add_trace(go.Scatter(x=df_chart['date'], y=df_chart['adx_line'], line=dict(color='cyan', width=2), name="ADX"), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_chart['date'], y=df_chart['rsi_line'], line=dict(color='orange', width=2), name="RSI"), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_chart['date'], y=df_chart['rs_score'], line=dict(color='magenta', dash='dot'), name="RS"), row=3, col=1)
        
        fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
