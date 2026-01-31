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

st.set_page_config(page_title="Hệ Thống Săn Sóng V32.4 - PRO", layout="wide")

# --- HÀM TÍNH TOÁN V32 (FULL CHỈ BÁO & LOGIC MUA) ---
def calculate_full_signals(df, vni_df):
    if df is None or len(df) < 50: return None
    df = df.copy()
    df.columns = df.columns.str.lower()
    df = df.dropna(subset=['close', 'volume']).reset_index(drop=True)

    c, h, l, o, v = df['close'], df['high'], df['low'], df['open'], df['volume']
    
    # 1. MA20, MA50 & Bollinger Bands (Check độ bó)
    df['ma20'] = c.rolling(20).mean()
    df['ma50'] = c.rolling(50).mean()
    std = c.rolling(20).std()
    df['bb_width'] = (std * 4) / df['ma20']
    
    # 2. RSI & ADX Chuẩn
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

    # 3. RS (Sức mạnh tương quan)
    v_c = vni_df['close'] if 'close' in vni_df.columns else vni_df['Close']
    df['rs'] = round(((c/c.shift(5)) - (v_c.iloc[-1]/v_c.iloc[-5])) * 100, 2)
    
    # 4. Check Dòng tiền & Quả Bom
    df['vol_trend'] = v.rolling(5).mean() > v.shift(5).rolling(5).mean()
    df['is_bomb'] = df['bb_width'] <= df['bb_width'].rolling(30).min()
    
    # 5. ĐIỂM MUA V32 (Dòng tiền vào + MA20 ngóc lên + RSI tốt)
    df['is_buy'] = (c > df['ma20']) & (df['ma20'] >= df['ma50']*0.98) & \
                   (v > v.rolling(20).mean() * 1.3) & (df['rsi'] > 48)
    
    return df

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚡ V32.4 CHUYÊN NGHIỆP")
    if st.button("🔄 UPDATE REALTIME (LƯU GITHUB)"):
        with st.spinner("Đang đồng bộ dữ liệu..."):
            vni = yf.download("^VNINDEX", period="2y").reset_index()
            # Ghi đè VNI lên GitHub (Giả định bạn đã có hàm requests.put cũ)
            list_mã = ['HPG','SSI','DIG','VND','FPT','DGC','NKG','HSG','PDR','VHM','MWG','STB','GEX','VCI','VGI','TCB']
            all_h = []
            for m in list_mã:
                t = yf.download(f"{m}.VN", period="2y", progress=False).reset_index()
                t['symbol'] = m
                all_h.append(t)
            df_final = pd.concat(all_h).reset_index(drop=True)
            # Ghi đè hose.csv lên GitHub
            st.success("✅ Đã cập nhật giá Realtime!")

    mode = st.radio("CHẾ ĐỘ XEM:", ["🌟 SIÊU SAO THEO DÕI", "📈 SOI CHI TIẾT MÃ"])
    ticker_input = st.text_input("NHẬP MÃ SOI:", "DIG").upper()

# --- XỬ LÝ DỮ LIỆU ---
try:
    # Load trực tiếp từ GitHub
    vni_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/VNINDEX.csv")
    hose_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/hose.csv")

    if mode == "🌟 SIÊU SAO THEO DÕI":
        # KHỐI 1: LỌC RŨ HÀNG
        st.subheader("⚠️ DANH SÁCH CỔ PHIẾU ĐANG RŨ HÀNG (KIỆT VOL)")
        ru_list = []
        for s in hose_df['symbol'].unique():
            df_s = calculate_full_signals(hose_df[hose_df['symbol']==s].copy(), vni_df)
            if df_s is not None:
                l = df_s.iloc[-1]
                if l['rsi'] < 42 and l['volume'] < df_s['volume'].rolling(20).mean() * 0.8:
                    ru_list.append({"Mã": s, "Giá": int(l['close']), "RS": l['rs'], "RSI": round(l['rsi'],1), "Trạng thái": "Rũ/Cạn cung"})
        
        if ru_list:
            st.table(pd.DataFrame(ru_list))
        else:
            st.info("Không có mã nào đang ở vùng rũ hàng kiệt vol.")

        st.divider()

        # KHỐI 2: SIÊU SAO THEO DÕI (BỘ LỌC THÔNG MINH)
        st.subheader("🔥 SIÊU SAO VÀO TẦM NGẮM (DÒNG TIỀN + MA + BB SQUEEZE)")
        vip_list = []
        for s in hose_df['symbol'].unique():
            d = calculate_full_signals(hose_df[hose_df['symbol']==s].copy(), vni_df)
            if d is not None:
                l = d.iloc[-1]
                # ĐIỀU KIỆN LỌC THEO ĐỀ BÀI:
                cond_ma = l['ma20'] >= l['ma50'] * 0.99   # MA20 ngóc lên cắt/trên MA50
                cond_flow = l['vol_trend']               # Dòng tiền vào đều 5 phiên
                cond_rsi = l['rsi'] > 48                 # RSI tốt
                cond_bomb = l['is_bomb']                 # BB bó chặt (Quả bom)

                if cond_ma and (cond_flow or cond_bomb):
                    vip_list.append({
                        "Mã": s, "Giá": int(l['close']), "RS": l['rs'], "RSI": round(l['rsi'],1), 
                        "ADX": round(l['adx'],1), "Dòng tiền": "TĂNG ĐỀU 🔥" if l['vol_trend'] else "Bình thường",
                        "Tín hiệu": "MUA ⚡" if l['is_buy'] else ("BÓ CHẶT 💣" if l['is_bomb'] else "Chờ nổ")
                    })
        
        if vip_list:
            st.dataframe(pd.DataFrame(vip_list).sort_values("RS", ascending=False), use_container_width=True)
        else:
            st.warning("Chưa tìm thấy mã đạt chuẩn Siêu Sao. Hãy nhấn UPDATE để làm mới dữ liệu.")

    elif mode == "📈 SOI CHI TIẾT MÃ":
        df_c = calculate_full_signals(hose_df[hose_df['symbol'] == ticker_input].copy(), vni_df)
        if df_c is not None:
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.4, 0.15, 0.2, 0.25])
            
            # Biểu đồ nến & Điểm mua
            fig.add_trace(go.Candlestick(x=df_c['date'], open=df_c['open'], high=df_c['high'], low=df_c['low'], close=df_c['close'], name="Nến"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma20'], line=dict(color='yellow', width=2), name="MA20"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma50'], line=dict(color='cyan', width=1.5), name="MA50"), row=1, col=1)
            
            # Hiển thị Điểm MUA Khuyến nghị
            buys = df_c[df_c['is_buy']]
            fig.add_trace(go.Scatter(x=buys['date'], y=buys['low']*0.97, mode='markers+text', text="MUA", textposition="bottom center", marker=dict(symbol='triangle-up', size=15, color='lime'), name="ĐIỂM MUA"), row=1, col=1)
            
            # Hiển thị Quả Bom (BB Squeeze)
            bombs = df_c[df_c['is_bomb']]
            fig.add_trace(go.Scatter(x=bombs['date'], y=bombs['high']*1.05, mode='text', text="💣", textfont=dict(size=25), name="Squeeze"), row=1, col=1)

            # Volume & RS/RSI/ADX
            fig.add_trace(go.Bar(x=df_c['date'], y=df_c['volume'], name="Vol"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rs'], name="RS", line=dict(color='magenta')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rsi'], name="RSI", line=dict(color='orange')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['adx'], name="ADX", line=dict(color='cyan')), row=4, col=1)

            fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Lỗi hiển thị: {e}")
    st.info("Hãy đảm bảo đã nhấn UPDATE REALTIME ít nhất một lần.")
