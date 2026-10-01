"""
Load a trained per-ticker XGBoost model and produce a next-day up-probability.

Usage
-----
    python -m meridian.research.predict NVDA AAPL
"""
from __future__ import annotations

import argparse
import logging
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from meridian.research.train_xgboost import add_features  # type: ignore  # noqa

MODELS_DIR = Path(__file__).parent / "models"
log = logging.getLogger("predict")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def predict_symbol(symbol: str) -> Dict[str, Any]:
    path = MODELS_DIR / f"{symbol.upper()}.pkl"
    if not path.exists():
        return {"symbol": symbol.upper(), "error": "no trained model — run train_xgboost first"}

    with open(path, "rb") as f:
        payload = pickle.load(f)

    model = payload["model"]
    feats = payload["features"]

    import yfinance as yf
    raw = yf.download(symbol, period="3mo", interval="1d", progress=False, auto_adjust=True)
    if raw is None or raw.empty:
        return {"symbol": symbol.upper(), "error": "no live data"}
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]

    df = add_features(raw).dropna()
    if df.empty:
        return {"symbol": symbol.upper(), "error": "feature window too small"}

    last = df.iloc[[-1]][feats]
    proba_up = float(model.predict_proba(last)[0, 1])
    direction = "UP" if proba_up >= 0.55 else "DOWN" if proba_up <= 0.45 else "NEUTRAL"

    return {
        "symbol": symbol.upper(),
        "as_of": str(df.index[-1].date()),
        "p_up_next_day": round(proba_up, 3),
        "p_down_next_day": round(1 - proba_up, 3),
        "direction": direction,
        "model_period": payload.get("trained_with_period"),
        "test_auc": payload.get("report", {}).get("test_auc"),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("symbols", nargs="+")
    args = p.parse_args()
    out: List[Dict[str, Any]] = [predict_symbol(s) for s in args.symbols]
    for row in out:
        print(row)


if __name__ == "__main__":
    main()
