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

st.set_page_config(page_title="Hệ Thống Săn Sóng V32 - REALTIME", layout="wide")

# --- HÀM TÍNH TOÁN V32 GỐC (GIỮ NGUYÊN ADX, RS, RS VÀ ĐIỂM MUA) ---
def calculate_full_signals(df, vni_df):
    if df is None or len(df) < 50: return None
    df = df.copy()
    df.columns = df.columns.str.lower()
    df = df.loc[:, ~df.columns.duplicated()]
    
    cols = ['close', 'high', 'low', 'open', 'volume']
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=cols).reset_index(drop=True)

    c, h, l, o, v = df['close'], df['high'], df['low'], df['open'], df['volume']
    
    # 1. MA20 & MA50
    df['ma20'] = c.rolling(20).mean()
    df['ma50'] = c.rolling(50).mean()
    df['ma20_up'] = df['ma20'] > df['ma20'].shift(1)
    
    # 2. RSI & ADX
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

    # 3. RS (Relative Strength)
    v_c = vni_df['close'] if 'close' in vni_df.columns else vni_df['Close']
    df['rs'] = round(((c/c.shift(5)) - (v_c.iloc[-1]/v_c.iloc[-5])) * 100, 2)
    
    # 4. DÒNG TIỀN (TĂNG DẦN TRONG 5 PHIÊN)
    df['vol_trend'] = v.rolling(5).mean() > v.shift(5).rolling(5).mean()
    vol_ma20 = v.rolling(20).mean()
    
    # 5. LOGIC ĐIỂM MUA CHUẨN V32 + ĐIỀU KIỆN KHẮT KHE
    # Điều kiện: Giá > MA20, MA20 > MA50, Vol > 1.3 MA20, RSI > 45, Dòng tiền đang tăng
    df['is_buy'] = (c > df['ma20']) & (df['ma20'] > df['ma50']) & \
                   (v > vol_ma20 * 1.3) & (df['rsi'] > 45) & (df['vol_trend'] == True)
    
    df['early_buy'] = (v > v.shift(1)) & (v > vol_ma20) & (c > o) & (c < df['ma20'] * 1.02)
    
    # 6. BOM & TEST SELL
    df['bw'] = (c.rolling(20).std() * 4) / df['ma20']
    df['is_bomb'] = df['bw'] <= df['bw'].rolling(30).min()
    df['test_sell'] = (c < o) & (v > vol_ma20 * 1.7)
    
    return df

# --- SIDEBAR & UPDATE REALTIME ---
with st.sidebar:
    st.header("⚡ HỆ THỐNG V32 - PRO")
    if st.button("🔄 UPDATE REALTIME (GHI ĐÈ)"):
        with st.spinner("Đang lấy giá Realtime và ghi đè GitHub..."):
            # Update VNINDEX
            vni = yf.download("^VNINDEX", period="2y").reset_index()
            requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", 
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                json={"message":"Update Realtime VNI","content":base64.b64encode(vni.to_csv(index=False).encode()).decode(), 
                      "sha": requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", headers={"Authorization": f"token {GITHUB_TOKEN}"}).json().get('sha')})
            
            # Update HOSE
            list_mã = ['HPG','SSI','DCM','DIG','VGI','TCB','FPT','DGC','NKG','HSG','PDR','VHM','MWG','VND','STB','VIC','ACB','GEX','VCI']
            all_h = []
            for m in list_mã:
                t = yf.download(f"{m}.VN", period="2y", progress=False).reset_index()
                t['symbol'] = m
                all_h.append(t)
            df_final = pd.concat(all_h).reset_index(drop=True)
            requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/hose.csv", 
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                json={"message":"Update Realtime HOSE","content":base64.b64encode(df_final.to_csv(index=False).encode()).decode(),
                      "sha": requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/hose.csv", headers={"Authorization": f"token {GITHUB_TOKEN}"}).json().get('sha')})
            st.success("✅ Đã ghi đè dữ liệu mới nhất!")

    mode = st.radio("CHẾ ĐỘ:", ["🌟 SIÊU SAO THEO DÕI", "📈 SOI CHI TIẾT MÃ"])
    ticker = st.text_input("NHẬP MÃ:", "DIG").upper()

# --- HIỂN THỊ ---
try:
    vni_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/VNINDEX.csv")
    hose_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/hose.csv")

    if mode == "🌟 SIÊU SAO THEO DÕI":
        # BẢNG RŨ HÀNG
        st.subheader("⚠️ DANH SÁCH CỔ PHIẾU ĐANG RŨ HÀNG (KIỆT VOL)")
        ru_data = []
        for s in hose_df['symbol'].unique():
            df_s = calculate_full_signals(hose_df[hose_df['symbol']==s].copy(), vni_df)
            if df_s is not None:
                l = df_s.iloc[-1]
                if l['rsi'] < 40 and l['volume'] < df_s['volume'].rolling(20).mean() * 0.8:
                    ru_data.append({"Mã": s, "Giá": int(l['close']), "RSI": round(l['rsi'],1), "Dòng tiền": "Cạn kiệt (Tốt)"})
        st.table(pd.DataFrame(ru_data))

        # BẢNG SIÊU SAO RS
        st.subheader("🚀 Top Cổ Phiếu Có Tín Hiệu (RS & Dòng tiền)")
        kq = []
        for s in hose_df['symbol'].unique():
            d = calculate_full_signals(hose_df[hose_df['symbol']==s].copy(), vni_df)
            if d is not None:
                l = d.iloc[-1]
                stt = "MUA 🔥" if l['is_buy'] else ("TIỀN MỒI 🔹" if l['early_buy'] else "Theo dõi")
                kq.append({"Mã": s, "Giá": int(l['close']), "RS": l['rs'], "Tín hiệu": stt, "ADX": round(l['adx'],1), "MA20>MA50": "OK" if l['ma20']>l['ma50'] else "NO"})
        st.dataframe(pd.DataFrame(kq).sort_values("RS", ascending=False))

    elif mode == "📈 SOI CHI TIẾT MÃ":
        df_c = calculate_full_signals(hose_df[hose_df['symbol'] == ticker].copy(), vni_df)
        if df_c is not None:
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.4, 0.15, 0.2, 0.25])
            
            # Chart 1: Nến & MA
            fig.add_trace(go.Candlestick(x=df_c['date'], open=df_c['open'], high=df_c['high'], low=df_c['low'], close=df_c['close'], name=ticker), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma20'], line=dict(color='yellow', width=2), name="MA20"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma50'], line=dict(color='blue', width=1), name="MA50"), row=1, col=1)
            
            # Vẽ điểm mua
            buy = df_c[df_c['is_buy']]
            fig.add_trace(go.Scatter(x=buy['date'], y=buy['low']*0.97, mode='markers', marker=dict(symbol='triangle-up', size=15, color='lime'), name="MUA CHUẨN"), row=1, col=1)

            # Chart 2: Volume
            fig.add_trace(go.Bar(x=df_c['date'], y=df_c['volume'], name="Volume"), row=2, col=1)
            
            # Chart 3: RS & RSI
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rs'], name="RS (Sức mạnh)", line=dict(color='magenta')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rsi'], name="RSI", line=dict(color='orange')), row=3, col=1)
            
            # Chart 4: ADX
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['adx'], name="ADX (Xu hướng)", line=dict(color='cyan')), row=4, col=1)

            fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.info("Vui lòng nhấn UPDATE REALTIME để tải dữ liệu.")
