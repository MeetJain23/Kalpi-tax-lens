"""Real-data test using yfinance. Run: python test_real_data.py
Loads Ashwar's IT basket from NSE and runs at multiple frequencies.
"""
import yfinance as yf, pandas as pd
from engine import run_backtest
from metrics import compare

SYMBOLS = ["TCS","INFY","WIPRO","TECHM","LTIM","HCLTECH"]
print("Fetching real NSE data...")
data = yf.download([f"{s}.NS" for s in SYMBOLS], start="2020-09-30", end="2025-09-30",
                   auto_adjust=True, progress=False)
prices = data["Close"].copy() if isinstance(data.columns, pd.MultiIndex) else data[["Close"]].copy()
prices.columns = [c.replace(".NS","") for c in prices.columns]
prices = prices[SYMBOLS].dropna()
print(f"Loaded {len(prices)} trading days, {prices.index[0].date()} to {prices.index[-1].date()}")

weights = {s: 1/6 for s in SYMBOLS}
for freq in ["NONE","ANNUAL","QUARTERLY","MONTHLY"]:
    print(f"\n=== {freq} REBALANCING ===")
    res = run_backtest(prices, weights, freq, initial_cash=1_000_000)
    df = compare({"Gross":res["gross_curve"], "Net-Cost":res["net_cost_curve"], "Net-Tax":res["net_tax_curve"]})
    print(df[["cagr","sharpe","max_drawdown"]].round(4))
    g, n = df.loc["Gross","cagr"]*100, df.loc["Net-Tax","cagr"]*100
    print(f"Gross CAGR {g:.2f}%  ->  After-Tax CAGR {n:.2f}%  (drag: {g-n:.2f} pp)")
    if res["tax_log"]:
        for tl in res["tax_log"]:
            print(f"  {tl['fy_label']}: STCG=Rs {tl['stcg_gain']:>11,.0f}  LTCG=Rs {tl['ltcg_gain']:>11,.0f}  Tax=Rs {tl['total_tax']:>9,.0f}")
