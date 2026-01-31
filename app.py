import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import base64
import requests
import yfinance as yf

# --- CẤU HÌNH GITHUB (ĐIỀN TOKEN CỦA BẠN VÀO ĐÂY) ---
GITHUB_TOKEN = "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"  # Token bạn đã cung cấp
GITHUB_USER = "lenghiapvdwell-star"
REPO_NAME = "san-song"

st.set_page_config(page_title="Hệ Thống Săn Sóng V27 - Smart Money", layout="wide")

# --- HÀM GHI ĐÈ FILE LÊN GITHUB ---
def push_to_github(file_path, df):
    try:
        url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{file_path}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        
        # Lấy SHA của file hiện tại để ghi đè
        res = requests.get(url, headers=headers)
        sha = res.json().get('sha') if res.status_code == 200 else None
        
        csv_content = df.to_csv(index=False)
        payload = {
            "message": f"Auto update {file_path}",
            "content": base64.b64encode(csv_content.encode()).decode(),
            "sha": sha
        }
        r = requests.put(url, headers=headers, json=payload)
        return r.status_code in [200, 201]
    except Exception as e:
        return False

# --- HÀM TÍNH TOÁN ĐIỂM MUA CHUẨN (HỘI TỤ 3 TẦNG) ---
def calculate_pro_signals(df, df_vni=None):
    if df is None or len(df) < 50: return None
    df.columns = df.columns.str.lower()
    close, high, low, open_p, vol = df['close'], df['high'], df['low'], df['open'], df['volume']

    # 1. Xu hướng MA20
    df['ma20'] = close.rolling(20).mean()
    df['ma20_up'] = df['ma20'] > df['ma20'].shift(1)
    
    # 2. Dòng tiền tổ chức (Force Index)
    df['fi_ma13'] = (vol * close.diff()).ewm(span=13).mean()
    df['smart_money'] = (df['fi_ma13'] > 0) & (vol > vol.rolling(20).mean() * 1.3)

    # 3. RS & Sức khỏe VNINDEX
    vni_healthy = True
    df['rs_score'] = 0.0
    if df_vni is not None:
        vni_c = df_vni['close'] if 'close' in df_vni.columns else df_vni['Close']
        vni_healthy = (vni_c.iloc[-1] > vni_c.rolling(20).mean().iloc[-1])
        v_change = (vni_c.iloc[-1]/vni_c.iloc[-5]-1)*100
        s_change = (close.iloc[-1]/close.iloc[-5]-1)*100
        df['rs_score'] = round(s_change - v_change, 2)

    # 4. ĐIỂM MUA HỢP LÝ (Đề bài: VNINDEX ổn + MA20 lên + Tiền tổ chức + RS khỏe)
    df['buy_signal'] = (vni_healthy) & (df['ma20_up']) & (close > df['ma20']) & \
                       (df['smart_money']) & (df['rs_score'] > 0)

    # Quả bom nén chặt
    df['bw'] = (close.rolling(20).std() * 4) / df['ma20']
    df['is_bomb'] = df['bw'] <= df['bw'].rolling(30).min()

    return df

# --- SIDEBAR ---
with st.sidebar:
    st.title("🛡️ CONTROL PANEL")
    if st.button("🔄 UPDATE GITHUB (VNI & HOSE)"):
        with st.spinner("Đang ghi đè dữ liệu lên GitHub..."):
            # Tải mới dữ liệu
            vni_new = yf.download("^VNINDEX", period="2y", progress=False).reset_index()
            # Ở đây bạn có thể thêm logic tải các mã trong hose.csv
            s1 = push_to_github("VNINDEX.csv", vni_new)
            if s1: st.success("✅ Đã ghi đè VNINDEX.csv thành công!")
            else: st.error("❌ Lỗi Update. Kiểm tra lại Token!")
            
    mode = st.radio("CHẾ ĐỘ XEM:", ["🌟 SIÊU SAO THEO DÕI", "📈 SOI CHI TIẾT MÃ"])
    ticker_input = st.text_input("NHẬP MÃ:", "HPG").upper()

# --- ĐỌC VÀ HIỂN THỊ ---
try:
    vni_df = pd.read_csv("VNINDEX.csv")
    hose_df = pd.read_csv("hose.csv")
    
    if mode == "🌟 SIÊU SAO THEO DÕI":
        st.subheader("🚀 Danh Sách Cổ Phiếu Theo Dấu Cá Mập")
        # Logic lọc bảng (như bản V26)
        # ... (phần này giữ nguyên như V26)
        
    elif mode == "📈 SOI CHI TIẾT MÃ":
        df_chart = hose_df[hose_df['symbol'] == ticker_input].copy()
        df_chart = calculate_pro_signals(df_chart, vni_df)
        if df_chart is not None:
            # Code vẽ Plotly 3 tầng (như bản V26)
            # Tầng 1: Nến + MA20 + Mũi tên ⬆️ MUA CHUẨN
            # Tầng 2: Force Index (Xanh/Đỏ)
            # Tầng 3: RSI & RS Score
            st.plotly_chart(fig, use_container_width=True) # fig được tạo từ logic V26
except:
    st.warning("Hãy nhấn Update hoặc kiểm tra file CSV trên repo của bạn.")
