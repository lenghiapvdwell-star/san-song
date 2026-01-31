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

st.set_page_config(page_title="Hệ Thống Săn Sóng V29", layout="wide")

# --- HÀM TÍNH TOÁN FULL CHỈ BÁO ---
def calculate_full_signals(df, vni_df):
    if df is None or len(df) < 50: return None
    df.columns = df.columns.str.lower()
    if 'date' not in df.columns: df = df.reset_index().rename(columns={'Date': 'date', 'index': 'date'})
    
    c, h, l, o, v = df['close'], df['high'], df['low'], df['open'], df['volume']
    
    # 1. MA20 & ADX & RSI
    df['ma20'] = c.rolling(20).mean()
    df['ma20_up'] = df['ma20'] > df['ma20'].shift(1)
    
    # ADX Calculation
    p = 14
    tr = pd.concat([h-l, (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/p).mean()
    up, dw = h.diff(), l.shift(1) - l
    pdm = np.where((up>dw)&(up>0), up, 0)
    mdm = np.where((dw>up)&(dw>0), dw, 0)
    pdi = 100 * (pd.Series(pdm).ewm(alpha=1/p).mean() / atr)
    mdi = 100 * (pd.Series(mdm).ewm(alpha=1/p).mean() / atr)
    df['adx'] = 100 * (abs(pdi-mdi)/(pdi+mdi)).ewm(alpha=1/p).mean().values
    
    # RSI
    delta = c.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/p).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/p).mean()
    df['rsi'] = 100 - (100 / (1 + gain/loss))

    # 2. RS & VNINDEX Health
    v_c = vni_df['close'] if 'close' in vni_df.columns else vni_df['Close']
    vni_healthy = (v_c.iloc[-1] >= v_c.rolling(20).mean().iloc[-1])
    df['rs'] = round(((c.iloc[-1]/c.iloc[-5]) - (v_c.iloc[-1]/v_c.iloc[-5])) * 100, 2)
    
    # 3. TÍN HIỆU: MUA - BOM - TEST SELL
    # MUA: MA20 lên + Tiền vào + RSI ngóc + RS khỏe
    df['is_buy'] = (vni_healthy) & (df['ma20_up']) & (c > df['ma20']) & (v > v.rolling(20).mean()*1.3) & (df['rsi'] > 50)
    # BOM: Nén chặt độ lệch chuẩn
    df['bw'] = (c.rolling(20).std() * 4) / df['ma20']
    df['is_bomb'] = df['bw'] <= df['bw'].rolling(30).min()
    # TEST SELL: Giá giảm + Vol cực lớn
    df['test_sell'] = (c < o) & (v > v.rolling(20).mean() * 1.8)
    
    return df

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚡ HỆ THỐNG V29")
    if st.button("🔄 UPDATE DATA"):
        with st.spinner("Ghi đè dữ liệu..."):
            vni = yf.download("^VNINDEX", period="2y").reset_index()
            res1 = requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", 
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                json={"message":"up","content":base64.b64encode(vni.to_csv(index=False).encode()).decode(), 
                      "sha": requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/VNINDEX.csv", headers={"Authorization": f"token {GITHUB_TOKEN}"}).json().get('sha')})
            
            list_mã = ['HPG','SSI','DCM','DIG','VGI','TCB','FPT','DGC','NKG','HSG','PDR','VHM','MWG']
            df_h = pd.concat([yf.download(f"{m}.VN", period="2y").assign(symbol=m).reset_index() for m in list_mã])
            res2 = requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/hose.csv", 
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                json={"message":"up","content":base64.b64encode(df_h.to_csv(index=False).encode()).decode(),
                      "sha": requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/hose.csv", headers={"Authorization": f"token {GITHUB_TOKEN}"}).json().get('sha')})
            st.success("✅ Đã ghi đè GitHub!")

    mode = st.radio("XEM:", ["🌟 SIÊU SAO THEO DÕI", "📈 SOI CHI TIẾT MÃ"])
    ticker = st.text_input("MÃ:", "HPG").upper()

# --- HIỂN THỊ ---
try:
    vni_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/VNINDEX.csv")
    hose_df = pd.read_csv(f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/hose.csv")

    if mode == "🌟 SIÊU SAO THEO DÕI":
        kq = []
        for m in hose_df['symbol'].unique():
            d = calculate_full_signals(hose_df[hose_df['symbol']==m].copy(), vni_df)
            if d is not None:
                l = d.iloc[-1]
                if l['is_buy'] or l['is_bomb']:
                    kq.append({"Mã": m, "Giá": int(l['close']), "RS": l['rs'], "RSI": round(l['rsi'],1), "Trạng thái": "🚀 MUA" if l['is_buy'] else "💣 BOM"})
        st.table(pd.DataFrame(kq).sort_values("RS", ascending=False))

    elif mode == "📈 SOI CHI TIẾT MÃ":
        df_c = calculate_full_signals(hose_df[hose_df['symbol']==ticker].copy(), vni_df)
        if df_c is not None:
            l = df_c.iloc[-1]
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.2, 0.3])
            
            # Tầng 1: Candle + MA20 + MUA + BOM + TEST SELL
            fig.add_trace(go.Candlestick(x=df_c['date'], open=df_c['open'], high=df_c['high'], low=df_c['low'], close=df_c['close'], name=ticker), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['ma20'], line=dict(color='yellow', width=1.5), name="MA20"), row=1, col=1)
            
            # Tín hiệu Mua, Bom, Sell
            b = df_c[df_c['is_buy']]
            fig.add_trace(go.Scatter(x=b['date'], y=b['low']*0.96, mode='markers+text', text="⬆️ MUA", marker=dict(symbol='triangle-up', size=12, color='lime')), row=1, col=1)
            bm = df_c[df_c['is_bomb']]
            fig.add_trace(go.Scatter(x=bm['date'], y=bm['high']*1.04, mode='text', text="💣"), row=1, col=1)
            ts = df_c[df_c['test_sell']]
            fig.add_trace(go.Scatter(x=ts['date'], y=ts['high']*1.06, mode='text', text="🛑 SELL"), row=1, col=1)

            # Target & Stoploss
            cur = l['close']
            fig.add_hline(y=cur*1.07, line_dash="dash", line_color="lime", annotation_text="T1 +7%", row=1, col=1)
            fig.add_hline(y=cur*1.15, line_dash="dash", line_color="cyan", annotation_text="T2 +15%", row=1, col=1)
            fig.add_hline(y=cur*0.94, line_dash="dash", line_color="red", annotation_text="SL -6%", row=1, col=1)

            # Tầng 2: Volume + Dòng tiền
            v_colors = ['#00ff00' if v > df_c['volume'].rolling(20).mean().iloc[i]*1.3 else '#555555' for i, v in enumerate(df_c['volume'])]
            fig.add_trace(go.Bar(x=df_c['date'], y=df_c['volume'], marker_color=v_colors, name="Vol"), row=2, col=1)

            # Tầng 3: ADX, RSI, RS
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['adx'], name="ADX", line=dict(color='cyan')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rsi'], name="RSI", line=dict(color='orange')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_c['date'], y=df_c['rs'], name="RS", line=dict(color='magenta', dash='dot')), row=3, col=1)
            
            fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.info("Nhấn UPDATE DATA để khởi tạo hệ thống.")
