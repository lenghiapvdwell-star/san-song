import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import base64
import requests
import yfinance as yf

# --- CẤU HÌNH GITHUB ---
GITHUB_TOKEN = "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"
GITHUB_USER = "lenghiapvdwell-star"
REPO_NAME = "san-song"

st.set_page_config(page_title="Hệ Thống Săn Sóng V32", layout="wide")

# --- HÀM TÍNH TOÁN (GIỮ NGUYÊN KỸ THUẬT V32) ---
def calculate_full_signals(df, vni_df):
    if df is None or len(df) < 35: return None
    df = df.copy()
    df.columns = df.columns.str.lower()
    df = df.loc[:, ~df.columns.duplicated()]
    if 'date' in df.columns:
        df = df.drop_duplicates(subset=['date']).reset_index(drop=True)
    cols = ['close', 'high', 'low', 'open', 'volume']
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=cols)
    c, h, l, o, v = df['close'], df['high'], df['low'], df['open'], df['volume']
    
    df['ma20'] = c.rolling(20).mean()
    df['ma20_up'] = df['ma20'] > df['ma20'].shift(1)
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

    v_c = vni_df['close'] if 'close' in vni_df.columns else vni_df['Close']
    df['rs'] = round(((c/c.shift(5)) - (v_c.iloc[-1]/v_c.iloc[-5])) * 100, 2)
    
    vol_ma20 = v.rolling(20).mean()
    df['is_buy'] = (c > df['ma20']) & (v > vol_ma20 * 1.3) & (df['rsi'] > 45) & (c > o)
    df['early_buy'] = (v > v.shift(1)) & (v > vol_ma20) & (c > o) & (c < df['ma20'] * 1.02)
    
    df['bw'] = (c.rolling(20).std() * 4) / df['ma20']
    df['is_bomb'] = df['bw'] <= df['bw'].rolling(30).min()
    df['test_sell'] = (c < o) & (v > vol_ma20 * 1.7)
    return df

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚡ HỆ THỐNG V32")
    if st.button("🔄 CẬP NHẬT DỮ LIỆU GITHUB"):
        with st.spinner("Đang xử lý ghi đè file..."):
            vni = yf.download("^VNINDEX", period="2y").reset_index()
            requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", 
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                json={"message":"up","content":base64.b64encode(vni.to_csv(index=False).encode()).decode(), 
                      "sha": requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", headers={"Authorization": f"token {GITHUB_TOKEN}"}).json().get('sha')})
            
            list_mã = ['HPG','SSI','DCM','DIG','VGI','TCB','FPT','DGC','NKG','HSG','PDR','VHM','MWG','VND','STB','VIC','ACB','SHB','TCH','GEX','VCI','MSH']
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
            st.success("✅ Ghi đè thành công!")

    mode = st.radio("CHẾ ĐỘ XEM:", ["🌟 SIÊU SAO THEO DÕI", "📈 SOI CHI TIẾT MÃ"])
    ticker = st.text_input("NHẬP MÃ:", "DIG").upper()

# --- HIỂN THỊ CHÍNH ---
try:
    # Tải dữ liệu từ GitHub
    vni_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/VNINDEX.csv")
    hose_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/hose.csv")

    if mode == "🌟 SIÊU SAO THEO DÕI":
        # KHỐI 1: BẢNG RŨ HÀNG (Tự động quét khi có dữ liệu)
        st.subheader("⚠️ DANH SÁCH CỔ PHIẾU ĐANG RŨ HÀNG (DÕI THEO TỔ CHỨC)")
        list_ru = []
        for s in hose_df['symbol'].unique():
            df_s = calculate_full_signals(hose_df[hose_df['symbol']==s].copy(), vni_df)
            if df_s is not None:
                l = df_s.iloc[-1]
                # Logic rũ hàng: RSI thấp (<40) và Vol kiệt (thấp hơn trung bình 20 phiên)
                if l['rsi'] < 42 and l['volume'] < df_s['volume'].rolling(20).mean():
                    list_ru.append({"Mã": s, "Giá": int(l['close']), "RSI": round(l['rsi'],1), "Trạng thái": "RŨ HÀNG - KIỆT VOL"})
        
        if list_ru:
            st.dataframe(pd.DataFrame(list_ru), use_container_width=True)
        else:
            st.info("Chưa có mã nào đạt điều kiện rũ hàng kiệt vol.")

        st.divider()

        # KHỐI 2: BẢNG SIÊU SAO (RS CAO)
        st.subheader("🚀 Danh Sách Cổ Phiếu Tạo Nền & Có Dòng Tiền")
        kq = []
        for s in hose_df['symbol'].unique():
            d = calculate_full_signals(hose_df[hose_df['symbol']==s].copy(), vni_df)
            if d is not None:
                l = d.iloc[-1]
                stt = "MUA ⬆️" if l['is_buy'] else ("TIỀN MỒI 🔹" if l['early_buy'] else "ĐANG NỀN")
                dong_tien = "MẠNH 🔥" if l['volume'] > d['volume'].rolling(20).mean() * 1.5 else "BÌNH THƯỜNG"
                kq.append({"Mã": s, "Giá": int(l['close']), "RS": l['rs'], "Trạng thái": stt, "Dòng tiền": dong_tien})
        st.dataframe(pd.DataFrame(kq).sort_values("RS", ascending=False), use_container_width=True)

    elif mode == "📈 SOI CHI TIẾT MÃ":
        df_c = calculate_full_signals(hose_df[hose_df['symbol'] == ticker].copy(), vni_df)
        if df_c is not None:
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.2, 0.3])
            # Giữ nguyên code vẽ chart V32
            fig.add_trace(go.Candlestick(x=df_c['date'], open=df_c['open'], high=df_c['high'], low=df_c['low'], close=df_c['close'], name=ticker), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma20'], line=dict(color='yellow', width=1.5), name="MA20"), row=1, col=1)
            
            # Điểm mua/bán
            buy = df_c[df_c['is_buy']]
            fig.add_trace(go.Scatter(x=buy['date'], y=buy['low']*0.97, mode='markers+text', text="MUA", marker=dict(symbol='triangle-up', size=15, color='lime')), row=1, col=1)
            bm = df_c[df_c['is_bomb']]; ts = df_c[df_c['test_sell']]
            fig.add_trace(go.Scatter(x=bm['date'], y=bm['high']*1.03, mode='text', text="💣"), row=1, col=1)
            fig.add_trace(go.Scatter(x=ts['date'], y=ts['high']*1.05, mode='text', text="🛑 SELL"), row=1, col=1)

            # Chỉ báo
            fig.add_trace(go.Bar(x=df_c['date'], y=df_c['volume'], name="Vol", marker_color='gray'), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rsi'], name="RSI", line=dict(color='orange')), row=3, col=1)
            
            fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.info("Nhấn CẬP NHẬT DỮ LIỆU GITHUB để tải dữ liệu.")
