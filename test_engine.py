"""End-to-end test with synthetic data. Run: python test_engine.py"""
import numpy as np, pandas as pd
from engine import run_backtest
from metrics import compare

np.random.seed(42)
dates = pd.date_range("2020-09-30", "2025-09-30", freq="B")
symbols = ["TCS","INFY","WIPRO","TECHM","LTIM","HCLTECH"]
prices = pd.DataFrame(index=dates, columns=symbols, dtype=float)
for s in symbols:
    drift = np.random.uniform(0.0003, 0.0007)
    vol = np.random.uniform(0.015, 0.022)
    prices[s] = 1000 * np.exp(np.cumsum(np.random.normal(drift, vol, len(dates))))

weights = {s: 1/6 for s in symbols}
for freq in ["NONE","QUARTERLY","MONTHLY"]:
    print(f"\n=== {freq} ===")
    res = run_backtest(prices, weights, freq)
    df = compare({"Gross":res["gross_curve"], "Net-Cost":res["net_cost_curve"], "Net-Tax":res["net_tax_curve"]})
    print(df[["cagr","sharpe","max_drawdown"]].round(4))
    t = res["totals"]
    print(f"Drag: cost=Rs {t['cost_drag_rupees']:,.0f}  tax=Rs {t['tax_drag_rupees']:,.0f}  total=Rs {t['total_drag_rupees']:,.0f}")
