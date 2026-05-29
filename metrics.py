"""Performance metrics: CAGR, vol, Sharpe, max drawdown."""
import numpy as np
import pandas as pd

def cagr(eq):
    if len(eq)<2 or eq.iloc[0]<=0: return 0.0
    days = (eq.index[-1]-eq.index[0]).days
    if days<=0: return 0.0
    if eq.iloc[-1]<=0: return -1.0
    return (eq.iloc[-1]/eq.iloc[0])**(365.25/days) - 1

def annualized_vol(eq):
    r = eq.pct_change().dropna()
    return r.std()*np.sqrt(252) if len(r)>=2 else 0.0

def sharpe(eq, rf=0.0):
    r = eq.pct_change().dropna()
    if len(r)<2 or r.std()==0: return 0.0
    return (r.mean()-rf)/r.std()*np.sqrt(252)

def max_drawdown(eq):
    if len(eq)<2: return 0.0
    return ((eq - eq.cummax())/eq.cummax()).min()

def summarize(eq, label=""):
    return {"label": label,
            "start_value": float(eq.iloc[0]), "end_value": float(eq.iloc[-1]),
            "total_return": float(eq.iloc[-1]/eq.iloc[0]-1),
            "cagr": float(cagr(eq)), "vol": float(annualized_vol(eq)),
            "sharpe": float(sharpe(eq)), "max_drawdown": float(max_drawdown(eq))}

def compare(curves):
    return pd.DataFrame([summarize(s,l) for l,s in curves.items()]).set_index("label")
