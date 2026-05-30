"""One-time data fetcher. Run locally to build cached_data.csv.
Don't run this on Streamlit Cloud - run it on your laptop where yfinance works.
"""
import yfinance as yf
import pandas as pd

# All symbols used across all presets — fetch once, use everywhere
SYMBOLS = [
    # IT
    "TCS", "INFY", "WIPRO", "HCLTECH",
    # Banks
    "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK",
    # Mixed sector
    "RELIANCE", "ITC", "MARUTI", "SUNPHARMA", "LT", "BHARTIARTL",
    # High-volatility
    "ADANIENT", "JSWSTEEL", "HINDALCO", "BAJFINANCE",
]

print(f"Fetching {len(SYMBOLS)} symbols from yfinance...")
tickers = [f"{s}.NS" for s in SYMBOLS]
data = yf.download(tickers, start="2020-09-01", end="2026-06-01",
                   auto_adjust=True, progress=True)

prices = data["Close"].copy()
rev = {f"{s}.NS": s for s in SYMBOLS}
prices.columns = [rev.get(c, c) for c in prices.columns]
prices = prices[SYMBOLS]

# Save to CSV
prices.to_csv("cached_prices.csv")
print(f"Saved {len(prices)} rows x {len(prices.columns)} cols to cached_prices.csv")
print(f"Date range: {prices.index[0].date()} to {prices.index[-1].date()}")