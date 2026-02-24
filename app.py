import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import yfinance as yf
import os
import time
from datetime import datetime

# --- CẤU HÌNH ---
st.set_page_config(page_title="SĂN SÓNG V32.9 PRO - REALTIME", layout="wide")

# Link Github của bạn (Chỉ dùng để đọc dữ liệu gốc)
GITHUB_USER = "lenghiapvdwell-star"
REPO_NAME = "san-song"
URL_VNI = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/VNINDEX.csv"
URL_HOSE = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/hose.csv"

# --- 1. HÀM CẬP NHẬT REAL-TIME (KHÔNG GHI ĐÈ GITHUB - TRỘN TRỰC TIẾP) ---
def fetch_realtime_data(symbol, existing_df):
    try:
        ticker_yf = f"{symbol}.VN" if symbol != "^VNINDEX" else "^VNINDEX"
        # Lấy dữ liệu 7 ngày gần nhất để bù đắp các ngày nghỉ
        new_data = yf.download(ticker_yf, period="7d", interval="1d", progress=False)
        
        if new_data.empty: return existing_df
        
        if isinstance(new_data.columns, pd.MultiIndex):
            new_data.columns = new_data.columns.get_level_values(0)
            
        new_data = new_data.reset_index()
        new_data.columns = [str(c).lower() for c in new_data.columns]
        new_data = new_data.rename(columns={'adj close': 'close'})
        
        # Hợp nhất và loại bỏ trùng lặp theo ngày
        combined = pd.concat([existing_df, new_data], ignore_index=True)
        combined['date'] = pd.to_datetime(combined['date'])
        combined = combined.drop_duplicates(subset=['date'], keep='last')
        return combined.sort_values('date').reset_index(drop=True)
    except Exception as e:
        st.warning(f"Lỗi Real-time {symbol}: {e}")
        return existing_df

# --- 2. HÀM TÍNH TOÁN V32 GỐC (ĐÃ TỐI ƯU) ---
def calculate_full_signals(df, vni_df):
    if df is None or len(df) < 50: return None
    df = df.copy()
    
    # Ép kiểu dữ liệu số
    for col in ['close', 'high', 'low', 'open', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df.dropna(subset=['close']).reset_index(drop=True)
    c, h, l, v = df['close'], df['high'], df['low'], df['volume']
    
    # 1. MA & Bollinger Bands
    df['ma20'] = c.rolling(20).mean()
    df['ma50'] = c.rolling(50).mean()
    std = c.rolling(20).std()
    df['bb_width'] = (std * 4) / df['ma20']
    
    # 2. RSI
    p = 14
    delta = c.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/p, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/p, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + gain/(loss + 0.000001)))
    
    # 3. ADX
    tr = pd.concat([h-l, (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/p, adjust=False).mean()
    pdm = pd.Series(np.where((h.diff()>l.shift(1)-l)&(h.diff()>0), h.diff(), 0))
    mdm = pd.Series(np.where((l.shift(1)-l>h.diff())&(l.shift(1)-l>0), l.shift(1)-l, 0))
    pdi = 100 * (pdm.ewm(alpha=1/p, adjust=False).mean() / atr)
    mdi = 100 * (mdm.ewm(alpha=1/p, adjust=False).mean() / atr)
    df['adx'] = (100 * (abs(pdi-mdi)/(pdi+mdi).replace(0, np.nan))).ewm(alpha=1/p, adjust=False).mean()

    # 4. RS (Sức mạnh so với VNI)
    if vni_df is not None:
        vni_c = vni_df['close'].iloc[-1]
        vni_c_old = vni_df['close'].iloc[-5] if len(vni_df) > 5 else vni_df['close'].iloc[0]
        df['rs'] = round(((c/c.shift(5)) - (vni_c/vni_c_old)) * 100, 2)
    else:
        df['rs'] = 0

    # 5. Các trạng thái
    df['is_bomb'] = df['bb_width'] <= df['bb_width'].rolling(30).min()
    df['vol_trend'] = v.rolling(5).mean() > v.shift(5).rolling(5).mean()
    df['is_buy'] = (c > df['ma20']) & (df['ma20'] >= df['ma50'] * 0.99) & \
                   (v > v.rolling(20).mean() * 1.25) & (df['rsi'] > 45)
    
    return df

# --- 3. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.header("⚡ V32.9 REAL-TIME")
    update_btn = st.button("🔄 CẬP NHẬT GIÁ MỚI (REALTIME)", use_container_width=True)
    
    mode = st.radio("CHẾ ĐỘ XEM:", ["🌟 SIÊU SAO THEO DÕI", "📈 SOI CHI TIẾT MÃ"])
    ticker_input = st.text_input("NHẬP MÃ SOI:", "DIG").upper()

# Tải dữ liệu từ GitHub về máy khách (Cache)
@st.cache_data(ttl=600)
def load_base_data(url):
    df = pd.read_csv(url)
    df.columns = df.columns.str.lower()
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
    return df

try:
    vni_base = load_base_data(URL_VNI)
    hose_base = load_base_data(URL_HOSE)

    # Xử lý cập nhật VNI
    if update_btn:
        with st.spinner("Đang lấy nến VNI hôm nay..."):
            vni_df = fetch_realtime_data("^VNINDEX", vni_base)
            st.session_state['vni_live'] = vni_df
    else:
        vni_df = st.session_state.get('vni_live', vni_base)

    if mode == "🌟 SIÊU SAO THEO DÕI":
        st.subheader("🚀 BỘ LỌC SIÊU SAO V32 - CẬP NHẬT REALTIME")
        
        vip_list = []
        ru_list = []
        
        # Chỉ quét các mã có trong dữ liệu
        symbols = hose_base['symbol'].unique()
        
        progress_bar = st.progress(0)
        for i, s in enumerate(symbols):
            df_s = hose_base[hose_base['symbol'] == s].copy()
            
            # Cập nhật giá realtime cho từng mã khi quét (nếu bấm nút)
            if update_btn:
                df_s = fetch_realtime_data(s, df_s)
            
            d = calculate_full_signals(df_s, vni_df)
            if d is not None:
                l = d.iloc[-1]
                
                # 1. Lọc Siêu sao
                if bool(l['ma20'] >= l['ma50'] * 0.99) and (bool(l['vol_trend']) or bool(l['is_bomb'])):
                    vip_list.append({
                        "Mã": s, "Giá": round(l['close'],0), "RS": l['rs'], "RSI": round(l['rsi'],1), 
                        "Tín hiệu": "MUA ⚡" if bool(l['is_buy']) else ("BÓ CHẶT 💣" if l['is_bomb'] else "Theo dõi")
                    })
                
                # 2. Lọc Rũ hàng
                if l['rsi'] < 42 and l['volume'] < d['volume'].rolling(20).mean().iloc[-1] * 0.85:
                    ru_list.append({"Mã": s, "Giá": round(l['close'],0), "RS": l['rs'], "RSI": round(l['rsi'],1)})
            
            progress_bar.progress((i + 1) / len(symbols))

        # Hiển thị kết quả
        c1, c2 = st.columns([2,1])
        with c1:
            st.markdown("### 🔥 Top Siêu Sao (RS cao nhất)")
            if vip_list:
                st.dataframe(pd.DataFrame(vip_list).sort_values("RS", ascending=False), use_container_width=True)
            else: st.info("Chưa có mã đạt chuẩn.")
        
        with c2:
            st.markdown("### ⚠️ Cạn kiệt / Rũ hàng")
            if ru_list:
                st.table(pd.DataFrame(ru_list).sort_values("RS", ascending=False))

    elif mode == "📈 SOI CHI TIẾT MÃ":
        df_s = hose_base[hose_base['symbol'] == ticker_input].copy()
        if update_btn:
            df_s = fetch_realtime_data(ticker_input, df_s)
            
        df_c = calculate_full_signals(df_s, vni_df)
        
        if df_c is not None:
            # Vẽ biểu đồ FireAnt Style
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.01, row_heights=[0.5, 0.1, 0.2, 0.2])
            
            fig.add_trace(go.Candlestick(x=df_c['date'], open=df_c['open'], high=df_c['high'], low=df_c['low'], close=df_c['close'], name=ticker_input), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma20'], line=dict(color='yellow', width=2), name="MA20"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma50'], line=dict(color='cyan', width=1.5), name="MA50"), row=1, col=1)
            
            # Bom & Mua
            bombs = df_c[df_c['is_bomb']]
            fig.add_trace(go.Scatter(x=bombs['date'], y=bombs['high']*1.02, mode='text', text="💣", textfont=dict(size=20), name="Bóp chặt"), row=1, col=1)
            buys = df_c[df_c['is_buy']]
            fig.add_trace(go.Scatter(x=buys['date'], y=buys['low']*0.98, mode='markers', marker=dict(symbol='triangle-up', size=12, color='lime'), name="MUA"), row=1, col=1)

            fig.add_trace(go.Bar(x=df_c['date'], y=df_c['volume'], name="Khối lượng"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rsi'], name="RSI", line=dict(color='orange')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rs'], name="Sức mạnh RS", line=dict(color='magenta')), row=4, col=1)

            fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
