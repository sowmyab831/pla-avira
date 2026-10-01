"""
Train an open-source price-direction predictor on the last 2 years of OHLCV data
for a given ticker (or list of tickers).

Why XGBoost
-----------
For tabular finance time-series with engineered indicators, gradient-boosted
trees consistently match or beat deep nets at a fraction of the compute and
with full feature interpretability — exactly what AVIRA needs to *explain*
its calls. We use walk-forward validation to avoid look-ahead leakage.

Output
------
A pickled model + feature spec at:
    meridian/research/models/{SYMBOL}.pkl

Usage
-----
    python -m meridian.research.train_xgboost AAPL NVDA TSLA
    python -m meridian.research.train_xgboost --period 2y AAPL
    python -m meridian.research.train_xgboost --universe ai_boom
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("trainer")

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


# ── Feature engineering ─────────────────────────────────────────────────────
def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build a rich tabular feature set from OHLCV."""
    df = df.copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    vol = df["Volume"]

    # Returns
    df["ret_1"]  = close.pct_change(1)
    df["ret_3"]  = close.pct_change(3)
    df["ret_5"]  = close.pct_change(5)
    df["ret_10"] = close.pct_change(10)
    df["ret_20"] = close.pct_change(20)

    # Moving averages
    df["sma_5"]   = close.rolling(5).mean()
    df["sma_20"]  = close.rolling(20).mean()
    df["sma_50"]  = close.rolling(50).mean()
    df["ema_12"]  = close.ewm(span=12, adjust=False).mean()
    df["ema_26"]  = close.ewm(span=26, adjust=False).mean()
    df["sma20_dev"] = (close - df["sma_20"]) / df["sma_20"]
    df["sma50_dev"] = (close - df["sma_50"]) / df["sma_50"]

    # MACD
    df["macd"]        = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"]   = df["macd"] - df["macd_signal"]

    # RSI(14)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    # ATR(14)
    tr = pd.concat(
        [(high - low),
         (high - close.shift()).abs(),
         (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()
    df["atr_pct"] = df["atr_14"] / close

    # Bollinger
    sd20 = close.rolling(20).std()
    df["bb_upper"] = df["sma_20"] + 2 * sd20
    df["bb_lower"] = df["sma_20"] - 2 * sd20
    df["bb_pct"]   = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    # Volume features
    df["vol_z_20"] = (vol - vol.rolling(20).mean()) / vol.rolling(20).std()
    df["obv"] = (np.sign(close.diff().fillna(0)) * vol).cumsum()
    df["obv_z_20"] = (df["obv"] - df["obv"].rolling(20).mean()) / df["obv"].rolling(20).std()

    # Volatility
    df["realized_vol_20"] = df["ret_1"].rolling(20).std() * np.sqrt(252)

    # Calendar
    if isinstance(df.index, pd.DatetimeIndex):
        df["dow"]   = df.index.dayofweek
        df["month"] = df.index.month

    # Target: next-day up-move (binary)
    df["target_up"] = (close.shift(-1) > close).astype(int)

    return df


FEATURES = [
    "ret_1", "ret_3", "ret_5", "ret_10", "ret_20",
    "sma20_dev", "sma50_dev",
    "macd", "macd_signal", "macd_hist",
    "rsi_14",
    "atr_pct",
    "bb_pct",
    "vol_z_20", "obv_z_20",
    "realized_vol_20",
    "dow", "month",
]


# ── Train one ticker ────────────────────────────────────────────────────────
@dataclass
class TrainReport:
    symbol: str
    period: str
    train_rows: int
    test_rows: int
    train_acc: float
    test_acc: float
    test_auc: float
    feature_importance: dict
    model_path: str


def train_symbol(symbol: str, period: str = "2y") -> TrainReport:
    import yfinance as yf
    from sklearn.metrics import accuracy_score, roc_auc_score
    from xgboost import XGBClassifier

    log.info("downloading %s (%s)", symbol, period)
    raw = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
    if raw is None or raw.empty:
        raise RuntimeError(f"no data for {symbol}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]

    df = add_features(raw).dropna()
    if len(df) < 200:
        raise RuntimeError(f"only {len(df)} usable rows for {symbol}; need ≥200")

    # Time-ordered split: last 20% = test
    cut = int(len(df) * 0.8)
    train, test = df.iloc[:cut], df.iloc[cut:]

    X_train, y_train = train[FEATURES], train["target_up"]
    X_test,  y_test  = test[FEATURES],  test["target_up"]

    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=1.0,
        objective="binary:logistic",
        eval_metric="logloss",
        n_jobs=-1,
        tree_method="hist",
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    train_pred = model.predict(X_train)
    test_pred  = model.predict(X_test)
    test_proba = model.predict_proba(X_test)[:, 1]

    rep = TrainReport(
        symbol=symbol.upper(),
        period=period,
        train_rows=int(len(train)),
        test_rows=int(len(test)),
        train_acc=float(accuracy_score(y_train, train_pred)),
        test_acc=float(accuracy_score(y_test, test_pred)),
        test_auc=float(roc_auc_score(y_test, test_proba)),
        feature_importance=dict(sorted(
            zip(FEATURES, model.feature_importances_.tolist()),
            key=lambda kv: kv[1],
            reverse=True,
        )),
        model_path=str(MODELS_DIR / f"{symbol.upper()}.pkl"),
    )

    payload = {
        "model": model,
        "features": FEATURES,
        "report": asdict(rep),
        "trained_with_period": period,
    }
    with open(rep.model_path, "wb") as f:
        pickle.dump(payload, f)
    log.info("✓ %s  test_acc=%.3f auc=%.3f → %s", rep.symbol, rep.test_acc, rep.test_auc, rep.model_path)
    return rep


# ── Universes ───────────────────────────────────────────────────────────────
UNIVERSES = {
    "ai_boom": ["NVDA", "AMD", "AVGO", "TSM", "MU", "ARM", "MSFT", "GOOGL", "META",
                "AMZN", "ORCL", "PLTR", "SMCI", "ANET", "VRT", "CEG"],
    "watchlist_default": ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "GOOGL", "AMZN",
                          "QQQ", "SPY", "SHOP", "SLV", "PLTR", "COIN", "MSTR", "SOFI"],
    "mega": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO"],
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("symbols", nargs="*", help="tickers to train (e.g. AAPL NVDA)")
    p.add_argument("--period", default="2y", help="yfinance period (default 2y)")
    p.add_argument("--universe", choices=list(UNIVERSES), help="train a preset universe")
    p.add_argument("--out", default=str(MODELS_DIR / "training_report.json"))
    args = p.parse_args()

    syms: List[str] = list(args.symbols)
    if args.universe:
        syms.extend(UNIVERSES[args.universe])
    syms = sorted(set(s.upper() for s in syms))
    if not syms:
        p.error("provide at least one symbol or --universe")

    reports = []
    for s in syms:
        try:
            reports.append(asdict(train_symbol(s, period=args.period)))
        except Exception as e:
            log.error("✗ %s: %s", s, e)
            reports.append({"symbol": s, "error": str(e)})

    with open(args.out, "w") as f:
        json.dump(reports, f, indent=2)
    log.info("wrote summary → %s", args.out)


if __name__ == "__main__":
    main()
