import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import base64
import requests
import yfinance as yf
from datetime import datetime, timedelta

# --- CẤU HÌNH GITHUB ---
GITHUB_TOKEN = "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"
GITHUB_USER = "lenghiapvdwell-star"
REPO_NAME = "san-song"

st.set_page_config(page_title="Săn Sóng V28 - Pro Auto", layout="wide")

# --- HÀM GIAO TIẾP GITHUB ---
def push_to_github(file_name, df):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{file_name}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    res = requests.get(url, headers=headers)
    sha = res.json().get('sha') if res.status_code == 200 else None
    
    csv_data = df.to_csv(index=False)
    content = base64.b64encode(csv_data.encode()).decode()
    payload = {"message": f"Update {file_name}", "content": content, "sha": sha} if sha else {"message": f"Create {file_name}", "content": content}
    r = requests.put(url, headers=headers, json=payload)
    return r.status_code in [200, 201]

# --- HÀM TÍNH TOÁN ĐIỂM MUA SMART MONEY ---
def calculate_signals(df, vni_df):
    if df is None or len(df) < 50: return None
    df.columns = df.columns.str.lower()
    # Chuyển đổi date nếu là index
    if 'date' not in df.columns: df = df.reset_index().rename(columns={'Date': 'date', 'index': 'date'})
    
    c, h, l, o, v = df['close'], df['high'], df['low'], df['open'], df['volume']
    
    # 1. MA20 & RSI
    df['ma20'] = c.rolling(20).mean()
    df['ma20_up'] = df['ma20'] > df['ma20'].shift(1)
    
    delta = c.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14).mean()
    df['rsi'] = 100 - (100 / (1 + gain/loss))
    
    # 2. Force Index (Dòng tiền tổ chức)
    df['fi'] = (v * delta).ewm(span=13).mean()
    df['smart_money'] = (df['fi'] > 0) & (v > v.rolling(20).mean() * 1.2)
    
    # 3. RS & VNINDEX Health
    v_c = vni_df['close'] if 'close' in vni_df.columns else vni_df['Close']
    vni_ma20 = v_c.rolling(20).mean()
    vni_healthy = (v_c.iloc[-1] >= vni_ma20.iloc[-1])
    
    v_chg = (v_c.iloc[-1]/v_c.iloc[-5]-1)*100
    s_chg = (c.iloc[-1]/c.iloc[-5]-1)*100
    df['rs'] = round(s_chg - v_chg, 2)
    
    # 4. Điểm Mua Đề Bài
    df['is_buy'] = (vni_healthy) & (df['ma20_up']) & (c > df['ma20']) & (df['smart_money']) & (df['rs'] > 0)
    return df

# --- SIDEBAR & UPDATE LOGIC ---
with st.sidebar:
    st.header("⚡ HỆ THỐNG V28")
    if st.button("🔄 UPDATE & GHI ĐÈ GITHUB"):
        with st.spinner("Đang tải dữ liệu và ghi đè..."):
            # 1. VNINDEX
            vni = yf.download("^VNINDEX", period="2y").reset_index()
            push_to_github("VNINDEX.csv", vni)
            
            # 2. HOSE (Quét danh sách mã chất lượng)
            list_mã = ['HPG','SSI','DCM','VND','DIG','VGI','TCB','FPT','DGC','NKG','HSG','PDR','VHM','MWG','VNM','VCB','STB']
            all_data = []
            for m in list_mã:
                temp = yf.download(f"{m}.VN", period="2y", progress=False).reset_index()
                temp['symbol'] = m
                all_data.append(temp)
            hose_full = pd.concat(all_data)
            push_to_github("hose.csv", hose_full)
            st.success("✅ Đã ghi đè dữ liệu mới lên GitHub!")

    mode = st.radio("CHẾ ĐỘ:", ["🌟 SIÊU SAO THEO DÕI", "📈 SOI CHI TIẾT MÃ"])
    ticker = st.text_input("NHẬP MÃ:", "HPG").upper()

# --- HIỂN THỊ ---
try:
    vni_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/VNINDEX.csv")
    hose_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/hose.csv")

    if mode == "🌟 SIÊU SAO THEO DÕI":
        st.subheader("🚀 Top Cổ Phiếu Có Dòng Tiền Tổ Chức")
        kq = []
        for m in hose_df['symbol'].unique():
            d = hose_df[hose_df['symbol'] == m].copy()
            d = calculate_signals(d, vni_df)
            if d is not None:
                l = d.iloc[-1]
                if l['is_buy'] or l['rs'] > 2:
                    kq.append({"Mã": m, "Giá": int(l['close']), "RS Score": l['rs'], "Dòng tiền": "💎 MẠNH" if l['smart_money'] else "Ổn", "Tín hiệu": "⬆️ MUA CHUẨN" if l['is_buy'] else "Theo dõi"})
        st.table(pd.DataFrame(kq).sort_values("RS Score", ascending=False))

    elif mode == "📈 SOI CHI TIẾT MÃ":
        df_c = hose_df[hose_df['symbol'] == ticker].copy()
        df_c = calculate_signals(df_c, vni_df)
        if df_c is not None:
            l = df_c.iloc[-1]
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.2, 0.3])
            # Chart nến & MA20
            fig.add_trace(go.Candlestick(x=df_c['date'], open=df_c['open'], high=df_c['high'], low=df_c['low'], close=df_c['close'], name=ticker), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma20'], line=dict(color='yellow', width=1.5), name="MA20 Trend"), row=1, col=1)
            
            # Điểm mua mũi tên
            buy_pts = df_c[df_c['is_buy']]
            fig.add_trace(go.Scatter(x=buy_pts['date'], y=buy_pts['low']*0.96, mode='markers+text', text="⬆️ MUA", marker=dict(symbol='triangle-up', size=12, color='lime')), row=1, col=1)
            
            # Target
            fig.add_hline(y=l['close']*1.07, line_dash="dash", line_color="lime", annotation_text="T1 +7%", row=1, col=1)
            fig.add_hline(y=l['close']*0.95, line_dash="dash", line_color="red", annotation_text="SL -5%", row=1, col=1)

            # Force Index & RSI/RS
            fig.add_trace(go.Bar(x=df_c['date'], y=df_c['fi'], name="Force Index", marker_color=np.where(df_c['fi']>0, 'lime', 'red')), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rsi'], name="RSI", line=dict(color='orange')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rs'], name="RS Score", line=dict(color='magenta', dash='dot')), row=3, col=1)
            
            fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.info("Vui lòng nhấn nút 'UPDATE & GHI ĐÈ GITHUB' ở bên trái để khởi tạo dữ liệu lần đầu.")
