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

st.set_page_config(page_title="Hệ Thống Săn Sóng V32 - PRO", layout="wide")

# --- HÀM TÍNH TOÁN 1: SHAKEOUT SCORE (TỪ FILE BAT CỦA BẠN) ---
def calculate_shakeout_score(df):
    if df is None or len(df) < 60: return 0, "N/A"
    df = df.copy()
    df.columns = df.columns.str.lower()
    latest = df.iloc[-1]
    
    score = 0
    reasons = []

    # TIÊU CHÍ 1: THANH KHOẢN (> 400k)
    if df['volume'].mean() < 400000: return -1, "Vol quá thấp"

    # TIÊU CHÍ 2: ĐANG RŨ (Dưới MA20 và MA50)
    ma20 = df['close'].rolling(20).mean().iloc[-1]
    ma50 = df['close'].rolling(50).mean().iloc[-1]
    if latest['close'] < ma20 and latest['close'] < ma50:
        score += 30
        reasons.append("Gãy hỗ trợ (Rũ)")

    # TIÊU CHÍ 3: KIỆT VOL
    avg_vol_20 = df['volume'].rolling(20).mean().iloc[-1]
    if latest['volume'] < avg_vol_20:
        score += 40
        reasons.append("Kiệt Vol")

    # TIÊU CHÍ 4: RSI QUÁ BÁN
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs)).iloc[-1]
    if rsi < 35:
        score += 20
        reasons.append(f"Quá bán (RSI:{round(rsi,1)})")
    
    # TIÊU CHÍ 5: NẾN RÚT CHÂN
    body = abs(latest['open'] - latest['close'])
    lower_shadow = min(latest['open'], latest['close']) - latest['low']
    if lower_shadow > body * 1.5:
        score += 10
        reasons.append("Rút chân")

    return score, ", ".join(reasons)

# --- HÀM TÍNH TOÁN 2: LIVE SIGNALS (TỪ MODULE THEO DÕI LIVE) ---
def get_live_signals(ticker, hose_df, vni_df):
    try:
        df = hose_df[hose_df['symbol'] == ticker].copy().sort_values('date')
        if len(df) < 20: return None
        
        # Lấy giá Live từ yfinance (1 phút gần nhất)
        live_data = yf.download(ticker + ".VN", period="1d", interval="1m", progress=False)
        if live_data.empty: return None
        
        live_p = live_data['Close'].iloc[-1]
        live_v = live_data['Volume'].sum()
        
        vni_change = (vni_df['close'].iloc[-1] / vni_df['close'].iloc[-5] - 1) * 100
        stock_change = (live_p / df['close'].iloc[-5] - 1) * 100
        rs_score = round(stock_change - vni_change, 2)
        
        avg_vol_20 = df['volume'].tail(20).mean()
        vol_ratio = live_v / avg_vol_20
        money_flow = "BÙNG NỔ 🚀" if vol_ratio > 0.8 else "YẾU ⏳"
        
        trigger_p = df['high'].tail(2).max()
        if live_p >= trigger_p and rs_score > 0: advice = ">>> MUA <<<"
        elif live_p >= trigger_p and rs_score <= 0: advice = "BẪY BULLTRAP ⚠️"
        else: advice = "Theo dõi"
        
        return {"Mã": ticker, "Giá Live": int(live_p), "RS": rs_score, "Dòng tiền": money_flow, "Tín hiệu": advice}
    except: return None

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚡ HỆ THỐNG V32 - PRO")
    if st.button("🔄 UPDATE DỮ LIỆU GITHUB"):
        with st.spinner("Đang cập nhật..."):
            vni = yf.download("^VNINDEX", period="2y").reset_index()
            requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", 
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                json={"message":"up","content":base64.b64encode(vni.to_csv(index=False).encode()).decode(), 
                      "sha": requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", headers={"Authorization": f"token {GITHUB_TOKEN}"}).json().get('sha')})
            
            list_mã = ['SSI', 'VND', 'DIG', 'SHB', 'HPG', 'VPB', 'GEX', 'MBB', 'VHM', 'VIC', 'FPT', 'DGC', 'NKG', 'HSG', 'PDR']
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

    st.markdown("---")
    mode = st.radio("CHẾ ĐỘ QUÉT:", ["🔍 LỌC RŨ HÀNG (BAT)", "🔥 SIÊU SAO THEO DÕI (LIVE)", "📈 SOI CHI TIẾT"])
    ticker_input = st.text_input("NHẬP MÃ:", "DIG").upper()

# --- HIỂN THỊ ---
try:
    vni_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/VNINDEX.csv")
    hose_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/hose.csv")

    if mode == "🔍 LỌC RŨ HÀNG (BAT)":
        st.subheader("⚠️ DANH SÁCH CỔ PHIẾU ĐANG RŨ HÀNG (SCORE >= 50)")
        final_ru = []
        for s in hose_df['symbol'].unique():
            df_s = hose_df[hose_df['symbol']==s].copy().sort_values('date')
            score, reason = calculate_shakeout_score(df_s)
            if score >= 50:
                final_ru.append({"Mã": s, "Điểm Rũ": score, "Giá": int(df_s['close'].iloc[-1]), "Lý do": reason})
        
        if final_ru:
            st.table(pd.DataFrame(final_ru).sort_values("Điểm Rũ", ascending=False))
        else:
            st.info("Không có mã nào đang rũ hàng đạt tiêu chí.")

    elif mode == "🔥 SIÊU SAO THEO DÕI (LIVE)":
        st.subheader("🚀 TÍN HIỆU DÒNG TIỀN TRỰC TUYẾN (REAL-TIME)")
        watch_list = ['SSI', 'VND', 'DIG', 'SHB', 'HPG', 'VPB', 'GEX', 'MBB', 'VHM', 'VIC']
        live_results = []
        with st.spinner("Đang quét Live sàn HOSE..."):
            for s in watch_list:
                res = get_live_signals(s, hose_df, vni_df)
                if res: live_results.append(res)
        
        if live_results:
            df_live = pd.DataFrame(live_results)
            st.dataframe(df_live.style.applymap(lambda x: 'color: lime' if x == ">>> MUA <<<" else ('color: red' if x == "BẪY BULLTRAP ⚠️" else ''), subset=['Tín hiệu']))
            st.warning("💡 Chỉ vào lệnh khi tín hiệu là '>>> MUA <<<' và Dòng tiền 'BÙNG NỔ 🚀'")
        
    elif mode == "📈 SOI CHI TIẾT":
        # Giữ nguyên phần vẽ Chart của V32
        st.info(f"Đang hiển thị biểu đồ kỹ thuật cho mã: {ticker_input}")
        # (Phần code Chart Plotly bạn giữ nguyên từ bản cũ đưa vào đây)

except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
    st.info("Nhấn UPDATE DỮ LIỆU GITHUB để làm mới dữ liệu.")
