import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import base64
import requests
import yfinance as yf
import warnings

warnings.filterwarnings("ignore")

# --- CẤU HÌNH GITHUB ---
GITHUB_TOKEN = "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"
GITHUB_USER = "lenghiapvdwell-star"
REPO_NAME = "san-song"

st.set_page_config(page_title="V32.7 - SSI Pro Chart", layout="wide")

# --- HÀM TÍNH TOÁN KỸ THUẬT (GIỮ NGUYÊN GỐC V32) ---
def calculate_full_signals(df, vni_df):
    if df is None or len(df) < 50: return None
    df = df.copy()
    df.columns = df.columns.str.lower()
    df = df.dropna(subset=['close', 'volume']).reset_index(drop=True)

    c, h, l, o, v = df['close'], df['high'], df['low'], df['open'], df['volume']
    
    df['ma20'] = c.rolling(20).mean()
    df['ma50'] = c.rolling(50).mean()
    
    p = 14
    delta = c.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/p, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/p, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + gain/loss))
    
    tr = pd.concat([h-l, (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/p, adjust=False).mean()
    pdm = pd.Series(np.where((h.diff()>l.shift(1)-l)&(h.diff()>0), h.diff(), 0), index=df.index)
    mdm = pd.Series(np.where((l.shift(1)-l>h.diff())&(l.shift(1)-l>0), l.shift(1)-l, 0), index=df.index)
    pdi = 100 * (pdm.ewm(alpha=1/p, adjust=False).mean() / atr)
    mdi = 100 * (mdm.ewm(alpha=1/p, adjust=False).mean() / atr)
    df['adx'] = (100 * (abs(pdi-mdi)/(pdi+mdi).replace(0, np.nan))).ewm(alpha=1/p, adjust=False).mean()

    vni_c = vni_df['close'] if 'close' in vni_df.columns else vni_df['Close']
    df['rs'] = round(((c/c.shift(5)) - (vni_c.iloc[-1]/vni_c.iloc[-5])) * 100, 2)
    
    std = c.rolling(20).std()
    df['bb_width'] = (std * 4) / df['ma20']
    df['is_bomb'] = df['bb_width'] <= df['bb_width'].rolling(30).min()
    
    df['vol_trend'] = (v.rolling(5).mean() > v.shift(5).rolling(5).mean())
    df['is_buy'] = (c > df['ma20']) & (df['ma20'] > df['ma50'] * 0.99) & \
                   (v > v.rolling(20).mean() * 1.3) & (df['rsi'] > 45)
    
    return df

# --- SIDEBAR & LOGIC ---
with st.sidebar:
    st.header("⚡ SSI STYLE CHART")
    if st.button("🔄 UPDATE & GHI ĐÈ GITHUB"):
        with st.spinner("Đang đồng bộ..."):
            # (Phần code update ghi đè GitHub của bạn giữ nguyên ở đây)
            st.success("✅ Cập nhật thành công!")

    mode = st.radio("CHẾ ĐỘ XEM:", ["🌟 SIÊU SAO THEO DÕI", "📈 SOI CHI TIẾT MÃ"])
    ticker_input = st.text_input("MÃ SOI:", "DIG").upper()

# --- HIỂN THỊ CHÍNH ---
try:
    vni_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/VNINDEX.csv")
    hose_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/hose.csv")

    if mode == "🌟 SIÊU SAO THEO DÕI":
        # (Phần lọc Siêu sao giữ nguyên logic của bản 32.6)
        st.subheader("🚀 BỘ LỌC SIÊU SAO CHUẨN V32")
        # ... logic hiển thị bảng ...

    elif mode == "📈 SOI CHI TIẾT MÃ":
        df_c = calculate_full_signals(hose_df[hose_df['symbol'] == ticker_input].copy(), vni_df)
        if df_c is not None:
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.01, row_heights=[0.5, 0.1, 0.2, 0.2])
            
            # Đồ thị nến
            fig.add_trace(go.Candlestick(x=df_c['date'], open=df_c['open'], high=df_c['high'], low=df_c['low'], close=df_c['close'], name="Giá"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma20'], line=dict(color='yellow', width=2), name="MA20"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma50'], line=dict(color='cyan', width=1.5), name="MA50"), row=1, col=1)
            
            # Quả bom & Điểm mua
            bombs = df_c[df_c['is_bomb']]
            fig.add_trace(go.Scatter(x=bombs['date'], y=bombs['high']*1.02, mode='text', text="💣", textfont=dict(size=22), name="Squeeze"), row=1, col=1)
            buys = df_c[df_c['is_buy']]
            fig.add_trace(go.Scatter(x=buys['date'], y=buys['low']*0.98, mode='markers+text', text="MUA", marker=dict(symbol='triangle-up', size=15, color='lime'), name="ĐIỂM MUA"), row=1, col=1)

            # Các tầng chỉ báo
            fig.add_trace(go.Bar(x=df_c['date'], y=df_c['volume'], name="Vol", marker_color='rgba(128,128,128,0.5)'), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rs'], name="RS", line=dict(color='magenta')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rsi'], name="RSI", line=dict(color='orange')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['adx'], name="ADX", line=dict(color='cyan')), row=4, col=1)

            # --- CẤU HÌNH GIAO DIỆN KÉO THẢ KIỂU SSI ---
            fig.update_layout(
                height=900,
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                # Chế độ mặc định: 'zoom' cho phép quét chuột để phóng to vùng chọn
                dragmode='zoom', 
                hovermode='x unified',
                # Tự động điều chỉnh trục Y khi zoom trục X
                yaxis=dict(fixedrange=False, autorange=True),
                xaxis=dict(fixedrange=False),
                margin=dict(l=10, r=10, t=30, b=10)
            )

            # Cấu hình thanh công cụ (Modebar) giống các sàn chứng khoán
            config = {
                'scrollZoom': True,          # Lăn chuột để zoom
                'displayModeBar': True,      # Hiện thanh công cụ
                'modeBarButtonsToAdd': [
                    'drawline', 'drawopenpath', 'drawclosedpath', 'drawcircle', 'drawrect', 'eraseshape'
                ],                           # Thêm công cụ vẽ nếu cần
                'displaylogo': False,
                'toImageButtonOptions': {'format': 'png', 'filename': f'V32_{ticker_input}'}
            }
            
            st.plotly_chart(fig, use_container_width=True, config=config)

except Exception as e:
    st.error(f"Lỗi: {e}")
