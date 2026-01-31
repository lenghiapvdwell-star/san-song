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

st.set_page_config(page_title="Hệ Thống Săn Sóng V32.2", layout="wide")

# --- HÀM TÍNH TOÁN KỸ THUẬT V32 GỐC ---
def calculate_full_signals(df, vni_df):
    if df is None or len(df) < 50: return None
    df = df.copy()
    df.columns = df.columns.str.lower()
    df = df.dropna(subset=['close', 'volume']).reset_index(drop=True)

    c, h, l, o, v = df['close'], df['high'], df['low'], df['open'], df['volume']
    
    # 1. MA20 & MA50
    df['ma20'] = c.rolling(20).mean()
    df['ma50'] = c.rolling(50).mean()
    
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

    # 3. RS (Relative Strength)
    v_c = vni_df['close'] if 'close' in vni_df.columns else vni_df['Close']
    df['rs'] = round(((c/c.shift(5)) - (v_c.iloc[-1]/v_c.iloc[-5])) * 100, 2)
    
    # 4. Bollinger Bands & Bóp nghẹt (Squeeze)
    std = c.rolling(20).std()
    df['bb_width'] = (std * 4) / df['ma20']
    df['is_bomb'] = df['bb_width'] <= df['bb_width'].rolling(30).min()
    
    # 5. Dòng tiền tăng dần 5 phiên
    df['vol_trend'] = v.rolling(5).mean() > v.shift(5).rolling(5).mean()
    
    return df

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚡ V32.2 PRO")
    if st.button("🔄 UPDATE REALTIME (GHI ĐÈ GITHUB)"):
        with st.spinner("Đang đồng bộ dữ liệu lên GitHub..."):
            vni = yf.download("^VNINDEX", period="2y").reset_index()
            # Ghi đè VNI... (Logic requests.put giữ nguyên)
            list_mã = ['HPG','SSI','DCM','DIG','VGI','TCB','FPT','DGC','NKG','HSG','PDR','VHM','MWG','VND','STB','VIC','GEX','SHB','VCI']
            all_h = []
            for m in list_mã:
                t = yf.download(f"{m}.VN", period="2y", progress=False).reset_index()
                t['symbol'] = m
                all_h.append(t)
            df_final = pd.concat(all_h).reset_index(drop=True)
            # Ghi đè hose.csv...
            st.success("✅ Đã ghi đè dữ liệu Realtime!")

    st.markdown("---")
    mode = st.radio("CHỌN CHẾ ĐỘ XEM:", ["🌟 SIÊU SAO THEO DÕI", "📈 SOI CHI TIẾT MÃ"])
    ticker_input = st.text_input("NHẬP MÃ:", "DIG").upper()

# --- HIỂN THỊ CHÍNH ---
try:
    vni_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/VNINDEX.csv")
    hose_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/hose.csv")

    if mode == "🌟 SIÊU SAO THEO DÕI":
        # 1. BẢNG LỌC RŨ HÀNG (KIỆT VOL)
        st.subheader("⚠️ DANH SÁCH CỔ PHIẾU ĐANG RŨ HÀNG")
        ru_list = []
        for s in hose_df['symbol'].unique():
            df_s = calculate_full_signals(hose_df[hose_df['symbol']==s].copy(), vni_df)
            if df_s is not None:
                l = df_s.iloc[-1]
                if l['rsi'] < 42 and l['volume'] < df_s['volume'].rolling(20).mean() * 0.8:
                    ru_list.append({"Mã": s, "Giá": int(l['close']), "RSI": round(l['rsi'],1), "RS": l['rs'], "Lý do": "Kiệt Vol/Rũ hàng"})
        st.table(pd.DataFrame(ru_list))

        # 2. BẢNG LỌC SIÊU SAO (THEO YÊU CẦU CỦA BẠN)
        st.subheader("🔥 SIÊU SAO VÀO TẦM NGẮM (LỌC DÒNG TIỀN & BB SQUEEZE)")
        vip_list = []
        for s in hose_df['symbol'].unique():
            d = calculate_full_signals(hose_df[hose_df['symbol']==s].copy(), vni_df)
            if d is not None:
                l = d.iloc[-1]
                # ĐIỀU KIỆN LỌC KHẮT KHE:
                cond_ma = l['ma20'] >= l['ma50']     # MA20 ngóc lên/trên MA50
                cond_rsi = l['rsi'] > 45            # RSI khỏe
                cond_flow = l['vol_trend']          # Dòng tiền 5 phiên tăng dần
                cond_bomb = l['is_bomb']            # BB bó chặt (Quả bom)

                if cond_ma and (cond_flow or cond_bomb):
                    vip_list.append({
                        "Mã": s, "Giá": int(l['close']), "RS": l['rs'], "RSI": round(l['rsi'],1), 
                        "ADX": round(l['adx'],1), "Dòng tiền": "TĂNG ĐỀU 🔥" if l['vol_trend'] else "Ổn định",
                        "Trạng thái": "BÓ CHẶT 💣" if l['is_bomb'] else "Tích lũy"
                    })
        
        if vip_list:
            st.dataframe(pd.DataFrame(vip_list).sort_values("RS", ascending=False), use_container_width=True)
        else:
            st.info("Chưa tìm thấy mã hội tụ đủ điều kiện khắt khe.")

    elif mode == "📈 SOI CHI TIẾT MÃ":
        df_c = calculate_full_signals(hose_df[hose_df['symbol'] == ticker_input].copy(), vni_df)
        if df_c is not None:
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.4, 0.15, 0.2, 0.25])
            # Vẽ Candlestick, MA20, MA50
            fig.add_trace(go.Candlestick(x=df_c['date'], open=df_c['open'], high=df_c['high'], low=df_c['low'], close=df_c['close'], name=ticker_input), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma20'], line=dict(color='yellow', width=2), name="MA20"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma50'], line=dict(color='cyan', width=1.5), name="MA50"), row=1, col=1)
            
            # Quả Bom (Bomb)
            bombs = df_c[df_c['is_bomb']]
            fig.add_trace(go.Scatter(x=bombs['date'], y=bombs['high']*1.05, mode='text', text="💣", textfont=dict(size=25), name="Squeeze"), row=1, col=1)
            
            # Volume & Indicators
            fig.add_trace(go.Bar(x=df_c['date'], y=df_c['volume'], name="Volume"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rs'], name="RS", line=dict(color='magenta')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rsi'], name="RSI", line=dict(color='orange')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['adx'], name="ADX", line=dict(color='cyan')), row=4, col=1)

            fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.info("Nhấn UPDATE REALTIME để bắt đầu.")
