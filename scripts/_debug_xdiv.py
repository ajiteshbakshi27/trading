"""Debug cross-platform divergence."""
from app.services import sentiment_divergence

# Test individual platform sentiment
for sym in ["NVDA", "TSLA", "AAPL"]:
    r = sentiment_divergence._reddit_sentiment(sym)
    x = sentiment_divergence._x_sentiment(sym)
    p = sentiment_divergence._prediction_sentiment(sym)
    print(f"{sym}: reddit={r['bullish_pct']}% x={x['bullish_pct']}% pred={p['bullish_pct']}%")

# Test full divergence
d = sentiment_divergence.compute_divergence("NVDA")
print(f"\nNVDA divergence: {d['divergence_score']} outlier={d['outlier_platform']}")
print(f"  retail_split: {d['retail_split']}")
print(f"  per_platform: {len(d['per_platform'])} platforms")
