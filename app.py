"""Kalpi Tax Lens - Streamlit demo UI.

Run with:  streamlit run app.py
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf

from engine import run_backtest
from metrics import compare

st.set_page_config(page_title="Kalpi Tax Lens", page_icon="🇮🇳", layout="wide")

st.markdown("""
<style>
  .stApp { background-color: #0a0a0a; color: #e8e8e8; }
  h1, h2, h3 { color: #ffffff; }
  .stat-card {
    background: #141414; border: 1px solid #1f1f1f;
    border-radius: 10px; padding: 18px; margin: 6px 0;
  }
  .stat-label { font-size: 13px; color: #888; }
  .stat-value { font-size: 28px; font-weight: 700; color: #fff; }
  .stat-delta-bad { color: #ff5757; font-size: 14px; }
  .stat-delta-good { color: #1ed760; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

st.title("Kalpi Tax Lens 🇮🇳")
st.markdown("**Tax-aware backtesting for Indian retail.** "
            "Shows the gap between marketing CAGR and what users actually keep "
            "after STT, GST, stamp duty, brokerage, STCG, and LTCG.")
st.caption("Prototype • Charges verified vs Zerodha calculator • Tax rates per Union Budget 2024")

with st.sidebar:
    st.header("Configure")
    basket_choice = st.selectbox("Preset basket",
    ["IT (Ashwar's demo)", "Banks", "Mixed (sector-diverse)", "Custom"], index=0)
    if basket_choice == "IT (Ashwar's demo)":
        symbols_input = ["TCS","INFY","WIPRO","TECHM","HCLTECH"]
    elif basket_choice == "Banks":
        symbols_input = ["HDFCBANK","ICICIBANK","SBIN","AXISBANK","KOTAKBANK"]
    elif basket_choice == "Mixed (sector-diverse)":
        symbols_input = ["RELIANCE", "HDFCBANK", "TCS", "ITC", "MARUTI", "SUNPHARMA", "LT", "BHARTIARTL"]
    else:
        symbols_input = st.text_area("NSE symbols (no .NS)", "TCS, INFY, WIPRO").replace(" ","").split(",")

    st.markdown("---")
    freq = st.selectbox("Rebalance frequency", ["NONE","ANNUAL","QUARTERLY","MONTHLY"], index=2,
                       help="Higher frequency = more taxable events = bigger drag")
    col1, col2 = st.columns(2)
    with col1: start_date = st.date_input("Start", value=pd.Timestamp("2020-09-30").date())
    with col2: end_date = st.date_input("End", value=pd.Timestamp("today").date())

    st.markdown("---")
    initial_cash = st.number_input("Initial capital (Rs)", value=1_000_000, min_value=10_000, step=50_000)
    brokerage = st.number_input("Brokerage per order (Rs)", value=20.0, min_value=0.0, step=5.0,
                                help="Zerodha = Rs 0 for delivery. Default Rs 20.")
    st.markdown("---")
    run = st.button("Run Tax Lens", type="primary", width='stretch')

@st.cache_data(show_spinner=False)
def fetch_prices(symbols, start, end):
    tickers = [f"{s}.NS" for s in symbols]
    data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    prices = data["Close"].copy() if isinstance(data.columns, pd.MultiIndex) else data[["Close"]].copy()
    rev = {f"{s}.NS": s for s in symbols}
    prices.columns = [rev.get(c, c) for c in prices.columns]
    return prices[symbols].dropna()

if not run:
    st.info("Configure the portfolio in the sidebar and hit **Run Tax Lens**.")
    st.markdown("### What this measures")
    st.markdown("""
    Most Indian retail backtesters report **gross CAGR**. This tool adds two more:
    1. **Net of cost CAGR** — after STT, stamp, exchange/SEBI, GST, brokerage
    2. **Net of cost + tax CAGR** — also STCG (20%), LTCG (12.5% post Rs 1.25L)
       with FIFO lot accounting and FY-end settlement.
    """)
    st.stop()

with st.spinner("Fetching NSE data..."):
    try:
        prices = fetch_prices(symbols_input, start_date, end_date)
    except Exception as e:
        st.error(f"Failed to load price data: {e}")
        st.stop()

if len(prices) == 0:
    st.error("No price data returned. Check symbols / dates.")
    st.stop()

st.success(f"Loaded {len(prices)} trading days, {len(prices.columns)} symbols "
           f"({prices.index[0].date()} to {prices.index[-1].date()})")

missing = set(symbols_input) - set(prices.columns)
if missing:
    st.warning(f"Skipped (no data for full period): {', '.join(missing)}")

weights = {s: 1/len(prices.columns) for s in prices.columns}
with st.spinner("Running tax-aware backtest..."):
    res = run_backtest(prices, weights, freq, float(initial_cash), brokerage)

curves = {"Gross": res["gross_curve"], "Net of Cost": res["net_cost_curve"],
          "Net of Cost + Tax": res["net_tax_curve"]}
mdf = compare(curves)

st.markdown("### Three CAGRs")
c1, c2, c3 = st.columns(3)
g, cc, tc = mdf.loc["Gross","cagr"], mdf.loc["Net of Cost","cagr"], mdf.loc["Net of Cost + Tax","cagr"]
with c1:
    st.markdown(f"""<div class="stat-card">
      <div class="stat-label">Gross CAGR (marketing number)</div>
      <div class="stat-value">{g*100:.2f}%</div></div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="stat-card">
      <div class="stat-label">Net of Cost CAGR</div>
      <div class="stat-value">{cc*100:.2f}%</div>
      <div class="stat-delta-bad">-{(g-cc)*100:.2f} pp cost drag</div></div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="stat-card">
      <div class="stat-label">Net of Cost + Tax (what user keeps)</div>
      <div class="stat-value">{tc*100:.2f}%</div>
      <div class="stat-delta-bad">-{(g-tc)*100:.2f} pp total drag</div></div>""", unsafe_allow_html=True)

t = res["totals"]
st.markdown(f"""<div class="stat-card" style="border-color:#1ed760;">
  <div class="stat-label">Total drag over period</div>
  <div class="stat-value" style="color:#1ed760;">Rs {t['total_drag_rupees']:,.0f}</div>
  <div class="stat-label">Cost: Rs {t['cost_drag_rupees']:,.0f} &nbsp;|&nbsp; Tax: Rs {t['tax_drag_rupees']:,.0f}</div>
  </div>""", unsafe_allow_html=True)

st.markdown("### Equity curves")
fig = go.Figure()
fig.add_trace(go.Scatter(x=res["gross_curve"].index, y=res["gross_curve"].values,
                         name="Gross", line=dict(color="#5c9eff", width=2)))
fig.add_trace(go.Scatter(x=res["net_cost_curve"].index, y=res["net_cost_curve"].values,
                         name="Net of Cost", line=dict(color="#ffa657", width=2)))
fig.add_trace(go.Scatter(x=res["net_tax_curve"].index, y=res["net_tax_curve"].values,
                         name="Net of Cost + Tax", line=dict(color="#1ed760", width=2.5)))
fig.update_layout(template="plotly_dark", paper_bgcolor="#0a0a0a", plot_bgcolor="#0a0a0a",
                  height=480, margin=dict(t=20,b=40,l=40,r=20),
                  legend=dict(orientation="h", y=1.05), yaxis_title="Portfolio value (Rs)")
st.plotly_chart(fig, width='stretch')

st.markdown("### Side-by-side metrics")
d = mdf[["cagr","vol","sharpe","max_drawdown","total_return"]].copy()
d.columns = ["CAGR","Volatility","Sharpe","Max DD","Total Return"]
for col in ["CAGR","Volatility","Max DD","Total Return"]:
    d[col] = (d[col]*100).round(2).astype(str) + "%"
d["Sharpe"] = d["Sharpe"].round(3)
st.dataframe(d, width='stretch')

if res["tax_log"]:
    st.markdown("### FY-end tax events")
    tdf = pd.DataFrame(res["tax_log"])[["fy_label","stcg_gain","ltcg_gain","stcg_tax","ltcg_tax","total_tax","paid_on"]]
    tdf.columns = ["FY","Realized STCG","Realized LTCG","STCG Tax (20%)","LTCG Tax (12.5%, post Rs 1.25L)","Total Tax","Paid on"]
    for col in ["Realized STCG","Realized LTCG","STCG Tax (20%)","LTCG Tax (12.5%, post Rs 1.25L)","Total Tax"]:
        tdf[col] = tdf[col].apply(lambda x: f"Rs {x:,.0f}")
    st.dataframe(tdf, width='stretch', hide_index=True)

with st.expander("Methodology"):
    st.markdown("""
    **Charge stack (per trade):**
    - STT: 0.1% both sides; Stamp: 0.015% buy-side
    - Exchange: 0.00297% both sides; SEBI: 0.0001% both sides
    - GST: 18% on (brokerage + exchange + SEBI)
    - Brokerage: configurable (Rs 20 default; Zerodha = Rs 0 for delivery)

    **Tax (post Union Budget 2024):**
    - STCG: 20% on gains, holding <= 365 days
    - LTCG: 12.5% on gains, holding > 365 days, Rs 1.25L annual exemption
    - FIFO lot accounting (Indian default)
    - FY = Apr 1 to Mar 31; tax deducted on 31-Mar

    **Out of scope for v0:** Tax-loss harvesting, set-off/carry-forward, dividend tax, per-broker profiles.
    """)
st.caption("Kalpi Tax Lens prototype | Built for retail backtest launch")
