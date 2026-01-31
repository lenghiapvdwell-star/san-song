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

st.set_page_config(page_title="Hệ Thống Săn Sóng V32 - FINAL", layout="wide")

# --- HÀM TÍNH TOÁN V32 CHUẨN ---
def calculate_full_signals(df, vni_df):
    if df is None or len(df) < 50: return None
    df = df.copy()
    df.columns = df.columns.str.lower()
    
    cols = ['close', 'high', 'low', 'open', 'volume']
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=cols).reset_index(drop=True)

    c, h, l, o, v = df['close'], df['high'], df['low'], df['open'], df['volume']
    
    # 1. Các đường MA quan trọng
    df['ma20'] = c.rolling(20).mean()
    df['ma50'] = c.rolling(50).mean()
    
    # 2. RSI & ADX chuẩn V32
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

    # 3. RS (So với VNINDEX)
    v_c = vni_df['close'] if 'close' in vni_df.columns else vni_df['Close']
    df['rs'] = round(((c/c.shift(5)) - (v_c.iloc[-1]/v_c.iloc[-5])) * 100, 2)
    
    # 4. Tín hiệu Dòng tiền 5 phiên
    df['vol_trend'] = v.rolling(5).mean() > v.shift(5).rolling(5).mean()
    vol_ma20 = v.rolling(20).mean()
    
    # 5. ĐIỂM MUA CHỌN LỌC (MA20 > MA50 & Vol Trend)
    df['is_buy'] = (c > df['ma20']) & (df['ma20'] > df['ma50']) & \
                   (v > vol_ma20 * 1.3) & (df['rsi'] > 45) & (df['vol_trend'])
    
    # 6. QUẢ BOM (BOMB) - Biến động thắt chặt chuẩn bị nổ
    df['bw'] = (c.rolling(20).std() * 4) / df['ma20']
    df['is_bomb'] = df['bw'] <= df['bw'].rolling(30).min()
    
    return df

# --- SIDEBAR & UPDATE ---
with st.sidebar:
    st.header("⚡ V32 REALTIME PRO")
    if st.button("🔄 UPDATE & GHI ĐÈ GITHUB"):
        with st.spinner("Đang đồng bộ dữ liệu..."):
            vni = yf.download("^VNINDEX", period="2y").reset_index()
            requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", 
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                json={"message":"up","content":base64.b64encode(vni.to_csv(index=False).encode()).decode(), 
                      "sha": requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", headers={"Authorization": f"token {GITHUB_TOKEN}"}).json().get('sha')})
            
            list_mã = ['HPG','SSI','DCM','DIG','VGI','TCB','FPT','DGC','NKG','HSG','PDR','VHM','MWG','VND','STB','VIC','GEX']
            all_h = []
            for m in list_mã:
                t = yf.download(f"{m}.VN", period="2y", progress=False).reset_index()
                t['symbol'] = m
                all_h.append(t)
            df_final = pd.concat(all_h).reset_index(drop=True)
            requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/hose.csv", 
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                json={"message":"up","content":base64.b64encode(df_final.to_csv(index=False).encode()).decode(),
                      "sha": requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/hose.csv", headers={"Authorization": f"token {GITHUB_TOKEN}"}).json().get('sha')})
            st.success("✅ Đã cập nhật!")

    mode = st.radio("CHẾ ĐỘ:", ["🌟 SIÊU SAO THEO DÕI", "📈 SOI CHI TIẾT MÃ"])
    ticker = st.text_input("NHẬP MÃ:", "DIG").upper()

# --- HIỂN THỊ ---
try:
    vni_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/VNINDEX.csv")
    hose_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/hose.csv")

    if mode == "🌟 SIÊU SAO THEO DÕI":
        # 1. BẢNG RŨ HÀNG KIỆT VOL
        st.subheader("⚠️ DANH SÁCH CỔ PHIẾU ĐANG RŨ HÀNG (KIỆT VOL)")
        ru_list = []
        for s in hose_df['symbol'].unique():
            df_s = calculate_full_signals(hose_df[hose_df['symbol']==s].copy(), vni_df)
            if df_s is not None:
                l = df_s.iloc[-1]
                if l['rsi'] < 42 and l['volume'] < df_s['volume'].rolling(20).mean() * 0.85:
                    ru_list.append({"Mã": s, "Giá": int(l['close']), "RSI": round(l['rsi'],1), "Trạng thái": "Rũ/Cạn cung"})
        st.table(pd.DataFrame(ru_list))

        # 2. BẢNG SIÊU SAO RS & DÒNG TIỀN
        st.subheader("🚀 SIÊU SAO DÒNG TIỀN (RS & MA20 > MA50)")
        kq = []
        for s in hose_df['symbol'].unique():
            d = calculate_full_signals(hose_df[hose_df['symbol']==s].copy(), vni_df)
            if d is not None:
                l = d.iloc[-1]
                if l['ma20'] > l['ma50']: # Chỉ hiện mã có xu hướng tốt
                    stt = "MUA 🔥" if l['is_buy'] else "Theo dõi"
                    kq.append({"Mã": s, "Giá": int(l['close']), "RS": l['rs'], "ADX": round(l['adx'],1), "Tín hiệu": stt})
        st.dataframe(pd.DataFrame(kq).sort_values("RS", ascending=False))

    elif mode == "📈 SOI CHI TIẾT MÃ":
        df_c = calculate_full_signals(hose_df[hose_df['symbol'] == ticker].copy(), vni_df)
        if df_c is not None:
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.4, 0.15, 0.2, 0.25])
            
            # Chart 1: Giá & Quả Bom
            fig.add_trace(go.Candlestick(x=df_c['date'], open=df_c['open'], high=df_c['high'], low=df_c['low'], close=df_c['close'], name=ticker), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma20'], line=dict(color='yellow', width=2), name="MA20"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma50'], line=dict(color='cyan', width=1), name="MA50"), row=1, col=1)
            
            # Hiển thị QUẢ BOM báo hiệu biến động lớn
            bombs = df_c[df_c['is_bomb']]
            fig.add_trace(go.Scatter(x=bombs['date'], y=bombs['high']*1.05, mode='text', text="💣", textfont=dict(size=25), name="Biến động lớn"), row=1, col=1)
            
            # Điểm mua
            buys = df_c[df_c['is_buy']]
            fig.add_trace(go.Scatter(x=buys['date'], y=buys['low']*0.96, mode='markers', marker=dict(symbol='triangle-up', size=15, color='lime'), name="ĐIỂM MUA"), row=1, col=1)

            # Các tầng chỉ báo
            fig.add_trace(go.Bar(x=df_c['date'], y=df_c['volume'], name="Volume", marker_color='gray'), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rs'], name="RS", line=dict(color='magenta')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['adx'], name="ADX", line=dict(color='orange')), row=4, col=1)

            fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.info("⚠️ Vui lòng nhấn UPDATE REALTIME để đồng bộ dữ liệu từ GitHub.")
