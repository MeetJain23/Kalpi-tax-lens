"""Indian equity trading charges + tax constants (post Union Budget 2024).

Charge rates verified against Zerodha brokerage calculator.
Tax rates per Finance (No. 2) Act 2024, effective 23-July-2024.
"""
from dataclasses import dataclass

CHARGES = {
    "stt_buy": 0.001, "stt_sell": 0.001,          # 0.1% both sides
    "stamp_buy": 0.00015,                          # 0.015% buy-side only
    "exchange_txn": 0.0000297,                     # NSE cash, both sides
    "sebi": 0.000001,                              # 0.0001% both sides
    "gst_rate": 0.18,                              # on (brokerage+exchange+sebi)
    "brokerage_per_order": 20.0,                   # configurable
}

TAX = {
    "stcg_rate": 0.20,                # post-Budget 2024 (was 15%)
    "ltcg_rate": 0.125,               # post-Budget 2024 (was 10%)
    "ltcg_exemption_annual": 125000,  # post-Budget 2024 (was 100000)
    "ltcg_threshold_days": 365,
}

@dataclass
class TradeCost:
    brokerage: float; stt: float; stamp_duty: float
    exchange_txn: float; sebi: float; gst: float; total: float
    def as_dict(self):
        return {k: round(getattr(self, k), 2) for k in
                ["brokerage","stt","stamp_duty","exchange_txn","sebi","gst","total"]}

def compute_charges(trade_value, side, brokerage_per_order=None):
    side = side.upper()
    if side not in ("BUY","SELL"): raise ValueError(f"side must be BUY/SELL, got {side}")
    brokerage = CHARGES["brokerage_per_order"] if brokerage_per_order is None else brokerage_per_order
    stt = trade_value * (CHARGES["stt_buy"] if side=="BUY" else CHARGES["stt_sell"])
    stamp_duty = trade_value * CHARGES["stamp_buy"] if side=="BUY" else 0.0
    exchange_txn = trade_value * CHARGES["exchange_txn"]
    sebi = trade_value * CHARGES["sebi"]
    gst = (brokerage + exchange_txn + sebi) * CHARGES["gst_rate"]
    total = brokerage + stt + stamp_duty + exchange_txn + sebi + gst
    return TradeCost(brokerage, stt, stamp_duty, exchange_txn, sebi, gst, total)
