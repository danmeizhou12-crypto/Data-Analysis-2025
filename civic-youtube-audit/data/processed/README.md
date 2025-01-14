# data/processed

Cleaned, enriched, and sentiment-scored outputs produced by the pipeline. These files are safe for analysis and visualization.

## Pipeline steps applied

```
data/raw/  →  [cleaning/cleaner.py]  →  [sentiment/analyzer.py]  →  data/processed/
```

1. **Schema normalisation** — unified column names, dtype coercion, datetime parsing
2. **Deduplication** — duplicate comments removed on `(video_id, text_clean)` composite key
3. **Text preprocessing** — URL stripping, unicode normalisation, whitespace collapsing
4. **Language detection** — heuristic EN/FR classifier (replaceable with `langdetect`)
5. **Engagement metrics** — derived rates per 1,000 views
6. **Sentiment scoring** — VADER compound score + ensemble label

## Files

| File | Format | Rows | Description |
|---|---|---|---|
| `videos_enriched.csv` | CSV | 80 | Video metadata + engagement metrics + avg. sentiment |
| `videos_enriched.parquet` | Parquet | 80 | Same, columnar |
| `comments_scored.csv` | CSV | 1,214 | Cleaned comments + full VADER scores + ensemble label |
| `comments_scored.parquet` | Parquet | 1,214 | Same, columnar |
| `sentiment_summary.csv` | CSV | 2 | Aggregated sentiment stats by channel |

## Additional columns vs. raw

### `videos_enriched`

| Column | Description |
|---|---|
| `engagement_rate` | Likes per 1,000 views |
| `comment_rate` | Comments per 1,000 views |
| `like_to_comment` | Ratio of likes to comments |
| `avg_sentiment` | Mean VADER compound score across all video comments |

### `comments_scored`

| Column | Description |
|---|---|
| `text_raw` | Original unmodified comment text |
| `text_clean` | Preprocessed text used for scoring |
| `language_detected` | `en` or `fr` |
| `vader_compound` | VADER compound score: −1.0 (most negative) → +1.0 (most positive) |
| `vader_pos` | Proportion of positive sentiment tokens |
| `vader_neg` | Proportion of negative sentiment tokens |
| `vader_label` | `positive` / `neutral` / `negative` (threshold: ±0.05) |
| `transformer_label` | Transformer model label (null if model not loaded) |
| `transformer_score` | Transformer confidence score |
| `ensemble_label` | Final label: agreement wins; disagreement defers to transformer if score > 0.70 |
| `sentiment_confidence` | Confidence proxy: transformer score or `|compound|` |

## Sentiment summary (`sentiment_summary.csv`)

| Column | Description |
|---|---|
| `channel_title` | Channel name |
| `total_comments` | Number of scored comments |
| `mean_compound` | Mean VADER compound score |
| `std_compound` | Standard deviation of compound scores |
| `positive_pct` | % comments labelled positive |
| `neutral_pct` | % comments labelled neutral |
| `negative_pct` | % comments labelled negative |
