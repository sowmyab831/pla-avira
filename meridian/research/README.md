# Meridian Research — Per-Ticker Direction Predictor

Lightweight, fully open-source ML pipeline that trains an **XGBoost** classifier
on **2 years** of daily OHLCV per ticker, with engineered technical indicators,
then exposes a `predict()` that the trading bot can use as a *secondary signal*
on top of its rules + LLM layers.

> Why XGBoost over a transformer? On tabular indicator features, gradient
> boosted trees match or beat deep nets at a fraction of compute, and they're
> *fully introspectable* — feature importances feed AVIRA's "why this trade?"
> explainability layer.

## Train

```bash
# Single ticker, 2 years
python -m meridian.research.train_xgboost NVDA

# Whole AI-boom universe
python -m meridian.research.train_xgboost --universe ai_boom

# Custom period + tickers
python -m meridian.research.train_xgboost --period 5y AAPL MSFT GOOGL
```

Output:

- `meridian/research/models/{SYMBOL}.pkl` — pickled model + feature spec + report
- `meridian/research/models/training_report.json` — combined metrics

Each model reports `train_acc`, `test_acc`, `test_auc`, and feature importances.

## Predict

```bash
python -m meridian.research.predict NVDA AAPL
```

Returns:

```json
{
  "symbol": "NVDA",
  "as_of": "2026-05-07",
  "p_up_next_day": 0.61,
  "p_down_next_day": 0.39,
  "direction": "UP",
  "test_auc": 0.572
}
```

## Features Used

Returns (1/3/5/10/20d) · SMA/EMA deviation · MACD · MACD signal · MACD histogram ·
RSI(14) · ATR%, Bollinger band position · 20d volume z-score · OBV z-score ·
realized 20d volatility · day-of-week · month.

## Honest Caveats

- A daily directional model rarely exceeds ~0.55–0.60 AUC. **Use it as a tilt,
  not an oracle.**
- Training is non-walk-forward (single time-ordered split). For production move
  to expanding-window CV with `TimeSeriesSplit`.
- News, options flow, and macro features are **not yet** in this model — the
  bot fuses them at the decision layer (technical + LLM + ML) instead of inside
  XGBoost.
- Past performance ≠ future returns. AVIRA is a research/paper-trading
  assistant; do not trust any single signal blindly.
