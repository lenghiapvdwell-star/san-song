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

st.set_page_config(page_title="Hệ Thống Săn Sóng V33 - Pro", layout="wide")

# --- HÀM TÍNH TOÁN (GIỮ NGUYÊN LOGIC V32) ---
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

# --- HÀM QUÉT RŨ HÀNG (TÁI LẬP LOGIC .BAT) ---
def scan_shakeout(hose_df, vni_df):
    shakeout_results = []
    for s in hose_df['symbol'].unique():
        d = calculate_full_signals(hose_df[hose_df['symbol']==s].copy(), vni_df)
        if d is not None:
            l = d.iloc[-1]
            reasons = []
            score = 0
            # Logic Rũ hàng
            if l['close'] < d['low'].rolling(10).min().shift(1): 
                reasons.append("Gãy hỗ trợ (Rũ hàng)")
                score += 40
            if l['volume'] < d['volume'].rolling(20).mean() * 0.8:
                reasons.append("Kiệt Vol (Tổ chức giữ hàng)")
                score += 30
            if l['rsi'] < 35:
                reasons.append("Quá bán (RSI thấp)")
                score += 20
            if l['close'] > l['low'] + (l['high'] - l['low']) * 0.5:
                reasons.append("Nến rút chân (Cầu ẩn)")
                score += 10
            
            if score >= 50:
                shakeout_results.append({
                    "Mã": s, "Điểm Rũ": score, "Giá": int(l['close']), "Lý do": ", ".join(reasons)
                })
    return pd.DataFrame(shakeout_results).sort_values("Điểm Rũ", ascending=False)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚡ HỆ THỐNG V33")
    
    # NÚT 1: UPDATE GITHUB
    if st.button("🔄 UPDATE & GHI ĐÈ GITHUB"):
        with st.spinner("Đang cập nhật dữ liệu..."):
            vni = yf.download("^VNINDEX", period="2y").reset_index()
            # Code push GitHub giữ nguyên...
            requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", 
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                json={"message":"up","content":base64.b64encode(vni.to_csv(index=False).encode()).decode(), 
                      "sha": requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", headers={"Authorization": f"token {GITHUB_TOKEN}"}).json().get('sha')})
            
            list_mã = ['HPG','SSI','DCM','DIG','VGI','TCB','FPT','DGC','NKG','HSG','PDR','VHM','MWG','VND','STB','VIC','ACB','SHB','TCH']
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

    # NÚT 2: QUÉT RŨ HÀNG (MỚI)
    st.markdown("---")
    show_shakeout = st.button("🔍 QUÉT SIÊU SAO RŨ HÀNG")
    
    mode = st.radio("CHẾ ĐỘ XEM:", ["📊 BIỂU ĐỒ CHI TIẾT", "🌟 SIÊU SAO THEO DÕI"])
    ticker = st.text_input("NHẬP MÃ:", "HPG").upper()

# --- HIỂN THỊ CHÍNH ---
try:
    vni_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/VNINDEX.csv")
    hose_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/hose.csv")

    # Hiển thị bảng Rũ hàng nếu nhấn nút
    if show_shakeout:
        st.subheader("⚠️ DANH SÁCH CỔ PHIẾU ĐANG RŨ HÀNG (THEO DÕI TỔ CHỨC)")
        df_shake = scan_shakeout(hose_df, vni_df)
        if not df_shake.empty:
            st.table(df_shake)
        else:
            st.info("Hiện tại chưa có mã nào đạt tiêu chí rũ hàng.")

    if mode == "🌟 SIÊU SAO THEO DÕI":
        st.subheader("🚀 Top Cổ Phiếu Có Tín Hiệu")
        kq = []
        for s in hose_df['symbol'].unique():
            d = calculate_full_signals(hose_df[hose_df['symbol']==s].copy(), vni_df)
            if d is not None:
                l = d.iloc[-1]
                stt = "MUA ⬆️" if l['is_buy'] else ("TIỀN MỒI 🔹" if l['early_buy'] else "Theo dõi")
                kq.append({"Mã": s, "Giá": int(l['close']), "RS": l['rs'], "Tín hiệu": stt, "RSI": round(l['rsi'],1)})
        st.dataframe(pd.DataFrame(kq).sort_values("RS", ascending=False))

    elif mode == "📊 BIỂU ĐỒ CHI TIẾT":
        df_c = calculate_full_signals(hose_df[hose_df['symbol'] == ticker].copy(), vni_df)
        if df_c is not None:
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.2, 0.3])
            fig.add_trace(go.Candlestick(x=df_c['date'], open=df_c['open'], high=df_c['high'], low=df_c['low'], close=df_c['close'], name=ticker), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma20'], line=dict(color='yellow', width=1.5), name="MA20"), row=1, col=1)
            
            # Tín hiệu Mua
            buy = df_c[df_c['is_buy']]
            fig.add_trace(go.Scatter(x=buy['date'], y=buy['low']*0.97, mode='markers+text', text="MUA", marker=dict(symbol='triangle-up', size=15, color='lime')), row=1, col=1)
            
            early = df_c[df_c['early_buy'] & ~df_c['is_buy']]
            fig.add_trace(go.Scatter(x=early['date'], y=early['low']*0.98, mode='markers', marker=dict(symbol='circle', size=8, color='cyan'), name="Tiền mồi"), row=1, col=1)
            
            bm = df_c[df_c['is_bomb']]; ts = df_c[df_c['test_sell']]
            fig.add_trace(go.Scatter(x=bm['date'], y=bm['high']*1.03, mode='text', text="💣"), row=1, col=1)
            fig.add_trace(go.Scatter(x=ts['date'], y=ts['high']*1.05, mode='text', text="🛑 SELL"), row=1, col=1)

            # Targets
            cur = df_c.iloc[-1]['close']
            fig.add_hline(y=cur*1.07, line_dash="dash", line_color="lime", annotation_text="T1+7%", row=1, col=1)
            fig.add_hline(y=cur*1.15, line_dash="dash", line_color="cyan", annotation_text="T2+15%", row=1, col=1)
            fig.add_hline(y=cur*0.94, line_dash="dash", line_color="red", annotation_text="SL-6%", row=1, col=1)

            # Vol & Indicators
            fig.add_trace(go.Bar(x=df_c['date'], y=df_c['volume'], name="Vol", marker_color='gray'), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['adx'], name="ADX", line=dict(color='cyan')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rsi'], name="RSI", line=dict(color='orange')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rs'], name="RS", line=dict(color='magenta')), row=3, col=1)
            
            fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.info("Nhấn UPDATE để tải dữ liệu.")
