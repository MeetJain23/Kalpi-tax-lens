"""FIFO lot tracker for Indian equity tax accounting.

India uses First-In-First-Out by default for tax lot accounting.
This module tracks lots and classifies sells as STCG (<=365d) or LTCG (>365d).
"""
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date
from typing import List
from charges import TAX

@dataclass
class Lot:
    symbol: str; qty: float; buy_price: float
    buy_date: date; cost_basis_per_share: float

@dataclass
class TaxEvent:
    symbol: str; qty: float; buy_price: float; sell_price: float
    buy_date: date; sell_date: date; holding_days: int
    bucket: str
    realized_pnl: float
    @property
    def is_ltcg(self): return self.bucket == "LTCG"
    @property
    def is_stcg(self): return self.bucket == "STCG"

class LotTracker:
    def __init__(self):
        self._lots = defaultdict(deque)
    def add_lot(self, symbol, qty, buy_price, buy_date, buy_charges_total=0.0):
        if qty <= 0: return
        cost_basis = buy_price + (buy_charges_total / qty)
        self._lots[symbol].append(Lot(symbol, qty, buy_price, buy_date, cost_basis))
    def consume_fifo(self, symbol, qty, sell_price, sell_date):
        if qty <= 0: return []
        events, remaining = [], qty
        while remaining > 1e-9:
            if not self._lots[symbol]:
                raise ValueError(f"Tried to sell {qty} of {symbol} but only {qty-remaining:.2f} available")
            lot = self._lots[symbol][0]
            consumed = min(lot.qty, remaining)
            days = (sell_date - lot.buy_date).days
            bucket = "LTCG" if days > TAX["ltcg_threshold_days"] else "STCG"
            realized = (sell_price - lot.cost_basis_per_share) * consumed
            events.append(TaxEvent(symbol, consumed, lot.cost_basis_per_share, sell_price,
                                   lot.buy_date, sell_date, days, bucket, realized))
            lot.qty -= consumed; remaining -= consumed
            if lot.qty < 1e-9: self._lots[symbol].popleft()
        return events
    def position(self, symbol):
        return sum(l.qty for l in self._lots[symbol])
    def all_positions(self):
        return {s: sum(l.qty for l in lots) for s, lots in self._lots.items() if sum(l.qty for l in lots) > 1e-9}
