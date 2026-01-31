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

st.set_page_config(page_title="Hệ Thống Săn Sóng V31", layout="wide")

# --- HÀM TÍNH TOÁN (SỬA LỖI LENGTH MISMATCH) ---
def calculate_full_signals(df, vni_df):
    if df is None or len(df) < 35: return None
    
    # 1. Dọn dẹp dữ liệu lặp
    df = df.copy()
    df.columns = df.columns.str.lower()
    df = df.loc[:, ~df.columns.duplicated()] # Loại bỏ cột trùng tên
    if 'date' in df.columns:
        df = df.drop_duplicates(subset=['date']).reset_index(drop=True)
    
    # 2. Ép kiểu số và xử lý NaN
    cols = ['close', 'high', 'low', 'open', 'volume']
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=cols)

    c, h, l, o, v = df['close'], df['high'], df['low'], df['open'], df['volume']
    
    # 3. MA20 & RSI
    df['ma20'] = c.rolling(20).mean()
    df['ma20_up'] = df['ma20'] > df['ma20'].shift(1)
    
    p = 14
    delta = c.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/p, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/p, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + gain/loss))
    
    # 4. ADX (Tính toán an toàn theo Series index)
    tr = pd.concat([h-l, (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/p, adjust=False).mean()
    up, dw = h.diff(), l.shift(1) - l
    pdm = pd.Series(np.where((up>dw)&(up>0), up, 0), index=df.index)
    mdm = pd.Series(np.where((dw>up)&(dw>0), dw, 0), index=df.index)
    pdi = 100 * (pdm.ewm(alpha=1/p, adjust=False).mean() / atr)
    mdi = 100 * (mdm.ewm(alpha=1/p, adjust=False).mean() / atr)
    dx = 100 * (abs(pdi-mdi)/(pdi+mdi).replace(0, np.nan))
    df['adx'] = dx.ewm(alpha=1/p, adjust=False).mean()

    # 5. RS & Sức khỏe VNINDEX
    v_c = vni_df['close'] if 'close' in vni_df.columns else vni_df['Close']
    vni_healthy = (v_c.iloc[-1] >= v_c.rolling(20).mean().iloc[-1])
    # Tính RS dựa trên 5 phiên gần nhất
    df['rs'] = round(((c/c.shift(5)) - (v_c.iloc[-1]/v_c.iloc[-5])) * 100, 2)
    
    # 6. TÍN HIỆU
    df['is_buy'] = (vni_healthy) & (df['ma20_up']) & (c > df['ma20']) & (v > v.rolling(20).mean()*1.3) & (df['rsi'] > 50)
    df['bw'] = (c.rolling(20).std() * 4) / df['ma20']
    df['is_bomb'] = df['bw'] <= df['bw'].rolling(30).min()
    df['test_sell'] = (c < o) & (v > v.rolling(20).mean() * 1.8)
    
    return df

# --- SIDEBAR & GITHUB UPDATE ---
with st.sidebar:
    st.header("⚡ HỆ THỐNG V31")
    if st.button("🔄 UPDATE & GHI ĐÈ GITHUB"):
        with st.spinner("Đang đồng bộ dữ liệu chuẩn..."):
            vni = yf.download("^VNINDEX", period="2y").reset_index()
            # Ghi VNINDEX
            requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", 
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                json={"message":"up","content":base64.b64encode(vni.to_csv(index=False).encode()).decode(), 
                      "sha": requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", headers={"Authorization": f"token {GITHUB_TOKEN}"}).json().get('sha')})
            
            # Ghi HOSE (Gom nhóm mã)
            list_mã = ['HPG','SSI','DCM','DIG','VGI','TCB','FPT','DGC','NKG','HSG','PDR','VHM','MWG','STB','VND']
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
            st.success("✅ Đã ghi đè thành công! Hãy chờ 5s để GitHub cập nhật.")

    mode = st.radio("CHẾ ĐỘ:", ["🌟 SIÊU SAO THEO DÕI", "📈 SOI CHI TIẾT MÃ"])
    ticker = st.text_input("NHẬP MÃ:", "HPG").upper()

# --- XỬ LÝ HIỂN THỊ ---
try:
    vni_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/VNINDEX.csv")
    hose_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/hose.csv")

    if mode == "🌟 SIÊU SAO THEO DÕI":
        st.subheader("🚀 Bảng Lọc Siêu Sao (Dòng Tiền & RS)")
        kq_list = []
        for s in hose_df['symbol'].unique():
            df_s = hose_df[hose_df['symbol'] == s].copy()
            df_s = calculate_full_signals(df_s, vni_df)
            if df_s is not None:
                last = df_s.iloc[-1]
                stt = "MUA ⬆️" if last['is_buy'] else ("BOM 💣" if last['is_bomb'] else "Ổn định")
                kq_list.append({"Mã": s, "Giá": int(last['close']), "RS": last['rs'], "RSI": round(last['rsi'],1), "ADX": round(last['adx'],1), "Trạng thái": stt})
        st.dataframe(pd.DataFrame(kq_list).sort_values("RS", ascending=False), use_container_width=True)

    elif mode == "📈 SOI CHI TIẾT MÃ":
        df_chart = hose_df[hose_df['symbol'] == ticker].copy()
        df_chart = calculate_full_signals(df_chart, vni_df)
        if df_chart is not None:
            l = df_chart.iloc[-1]
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.2, 0.3])
            
            # Tầng 1: Price + Targets
            fig.add_trace(go.Candlestick(x=df_chart['date'], open=df_chart['open'], high=df_chart['high'], low=df_chart['low'], close=df_chart['close'], name=ticker), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_chart['date'], y=df_chart['ma20'], line=dict(color='yellow', width=1.5), name="MA20"), row=1, col=1)
            
            # Signals
            b = df_chart[df_chart['is_buy']]; bm = df_chart[df_chart['is_bomb']]; ts = df_chart[df_chart['test_sell']]
            fig.add_trace(go.Scatter(x=b['date'], y=b['low']*0.97, mode='markers+text', text="MUA", marker=dict(symbol='triangle-up', size=12, color='lime')), row=1, col=1)
            fig.add_trace(go.Scatter(x=bm['date'], y=bm['high']*1.03, mode='text', text="💣"), row=1, col=1)
            fig.add_trace(go.Scatter(x=ts['date'], y=ts['high']*1.05, mode='text', text="🛑 SELL"), row=1, col=1)

            # Targets
            c_val = l['close']
            fig.add_hline(y=c_val*1.07, line_dash="dash", line_color="lime", annotation_text="T1+7%", row=1, col=1)
            fig.add_hline(y=c_val*1.15, line_dash="dash", line_color="cyan", annotation_text="T2+15%", row=1, col=1)
            fig.add_hline(y=c_val*0.94, line_dash="dash", line_color="red", annotation_text="SL-6%", row=1, col=1)

            # Tầng 2 & 3: Vol & Indicators
            fig.add_trace(go.Bar(x=df_chart['date'], y=df_chart['volume'], name="Vol", marker_color='gray'), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_chart['date'], y=df_chart['adx'], name="ADX", line=dict(color='cyan')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_chart['date'], y=df_chart['rsi'], name="RSI", line=dict(color='orange')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_chart['date'], y=df_chart['rs'], name="RS", line=dict(color='magenta', dash='dot')), row=3, col=1)
            
            fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.error(f"Đang chờ dữ liệu cập nhật từ GitHub... Vui lòng thử lại sau giây lát.")
