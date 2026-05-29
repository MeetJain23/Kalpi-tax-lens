"""Tax-aware backtest engine.

Generates three parallel equity curves:
  1. gross         - ignores all costs and taxes
  2. net_of_cost   - applies STT/stamp/exchange/SEBI/GST/brokerage
  3. net_of_all    - also applies STCG (20%) and LTCG (12.5%, post Rs 1.25L)
                     with FIFO lot tracking and FY-end settlement.

Indian FY: April 1 - March 31. Tax settles as cash outflow on 31-March.
"""
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List
import pandas as pd
from charges import TAX, compute_charges
from lots import LotTracker, TaxEvent

@dataclass
class RebalanceLog:
    date: pd.Timestamp
    trades: List[dict]
    tax_events: List[TaxEvent]

def _financial_year(d):
    return d.year if d.month >= 4 else d.year - 1

def _build_rebalance_dates(start, end, freq, available):
    freq = freq.upper()
    if freq == "NONE":
        return [available[0]]
    freq_map = {"MONTHLY": "MS", "QUARTERLY": "QS", "ANNUAL": "YS"}
    if freq not in freq_map:
        raise ValueError(f"freq must be NONE/MONTHLY/QUARTERLY/ANNUAL, got {freq}")
    target = pd.date_range(start, end, freq=freq_map[freq])
    snapped = []
    for t in target:
        fut = available[available >= t]
        if len(fut) > 0:
            snapped.append(fut[0])
    seen, out = set(), []
    for d in snapped:
        if d not in seen:
            out.append(d)
            seen.add(d)
    return out

def run_backtest(prices, target_weights, rebalance_frequency="QUARTERLY",
                 initial_cash=1_000_000.0, brokerage_per_order=20.0):
    """
    Args:
      prices: DataFrame indexed by date, columns are symbols
      target_weights: dict symbol -> weight, must sum to 1.0
      rebalance_frequency: NONE / MONTHLY / QUARTERLY / ANNUAL
      initial_cash: starting capital in INR
      brokerage_per_order: configurable broker cost (Rs per order)

    Returns:
      dict with gross_curve, net_cost_curve, net_tax_curve,
      rebalance_log, tax_log, totals
    """
    if abs(sum(target_weights.values()) - 1.0) > 1e-6:
        raise ValueError(f"weights must sum to 1.0, got {sum(target_weights.values())}")
    for s in target_weights:
        if s not in prices.columns:
            raise ValueError(f"{s} not in price data")
    prices = prices.sort_index().ffill().dropna(how="all")
    symbols = list(target_weights.keys())
    rebal = _build_rebalance_dates(prices.index[0], prices.index[-1],
                                   rebalance_frequency, prices.index)
    rebal_set = set(rebal)

    tracker = LotTracker()
    cash_g = cash_c = cash_t = initial_cash
    fy_stcg, fy_ltcg = defaultdict(float), defaultdict(float)
    rebalance_log, tax_log = [], []
    last_fy = None
    gc = pd.Series(index=prices.index, dtype=float)
    cc = pd.Series(index=prices.index, dtype=float)
    tc = pd.Series(index=prices.index, dtype=float)

    for cd in prices.index:
        # FY rollover: settle tax for the FY that just ended
        cfy = _financial_year(cd)
        if last_fy is None:
            last_fy = cfy
        if cfy != last_fy:
            closed = last_fy
            stcg_amt = max(0.0, fy_stcg[closed])
            ltcg_amt = max(0.0, fy_ltcg[closed] - TAX["ltcg_exemption_annual"])
            stcg_tax = stcg_amt * TAX["stcg_rate"]
            ltcg_tax = ltcg_amt * TAX["ltcg_rate"]
            total_tax = stcg_tax + ltcg_tax
            cash_t -= total_tax
            tax_log.append({
                "fy_start_year": closed,
                "fy_label": f"FY{str(closed)[-2:]}-{str(closed+1)[-2:]}",
                "stcg_gain": fy_stcg[closed],
                "ltcg_gain": fy_ltcg[closed],
                "stcg_tax": stcg_tax,
                "ltcg_tax": ltcg_tax,
                "total_tax": total_tax,
                "paid_on": str(cd.date()),
            })
            last_fy = cfy

        # Rebalance
        if cd in rebal_set:
            px = prices.loc[cd]
            curr = tracker.all_positions()
            pv = cash_t + sum(curr.get(s, 0) * px[s] for s in symbols)
            trades, events_today = [], []

            # Sells first (free up cash)
            for s in symbols:
                target_qty = (target_weights[s] * pv) / px[s]
                cq = curr.get(s, 0.0)
                delta = target_qty - cq
                if delta < -1e-6:
                    sq = -delta
                    sv = sq * px[s]
                    sc = compute_charges(sv, "SELL", brokerage_per_order)
                    evs = tracker.consume_fifo(s, sq, float(px[s]), cd.date())
                    events_today.extend(evs)
                    for ev in evs:
                        fy = _financial_year(pd.Timestamp(ev.sell_date))
                        if ev.is_stcg:
                            fy_stcg[fy] += ev.realized_pnl
                        else:
                            fy_ltcg[fy] += ev.realized_pnl
                    cash_g += sv
                    cash_c += sv - sc.total
                    cash_t += sv - sc.total
                    trades.append({"symbol": s, "side": "SELL", "qty": sq,
                                   "price": float(px[s]), "value": sv,
                                   "charges": sc.total})

            # Then buys
            for s in symbols:
                target_qty = (target_weights[s] * pv) / px[s]
                cq = tracker.position(s)
                delta = target_qty - cq
                if delta > 1e-6:
                    bq = delta
                    bv = bq * px[s]
                    bc = compute_charges(bv, "BUY", brokerage_per_order)
                    tracker.add_lot(s, bq, float(px[s]), cd.date(), bc.total)
                    cash_g -= bv
                    cash_c -= bv + bc.total
                    cash_t -= bv + bc.total
                    trades.append({"symbol": s, "side": "BUY", "qty": bq,
                                   "price": float(px[s]), "value": bv,
                                   "charges": bc.total})

            rebalance_log.append(RebalanceLog(cd, trades, events_today))

        # Mark-to-market
        px_t = prices.loc[cd]
        pos = tracker.all_positions()
        hv = sum(pos.get(s, 0) * px_t[s] for s in symbols)
        gc.loc[cd] = cash_g + hv
        cc.loc[cd] = cash_c + hv
        tc.loc[cd] = cash_t + hv

    cost_drag = gc.iloc[-1] - cc.iloc[-1]
    tax_drag = cc.iloc[-1] - tc.iloc[-1]
    return {
        "gross_curve": gc,
        "net_cost_curve": cc,
        "net_tax_curve": tc,
        "rebalance_log": rebalance_log,
        "tax_log": tax_log,
        "totals": {
            "initial_cash": initial_cash,
            "gross_final": float(gc.iloc[-1]),
            "net_cost_final": float(cc.iloc[-1]),
            "net_tax_final": float(tc.iloc[-1]),
            "cost_drag_rupees": float(cost_drag),
            "tax_drag_rupees": float(tax_drag),
            "total_drag_rupees": float(cost_drag + tax_drag),
        },
    }
