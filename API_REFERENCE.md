# API Reference & Code Examples

## Quick Reference

This document provides detailed API signatures, examples, and use cases for every function in the pipeline.

---

## Table of Contents

1. [ETL Layer (youtube_client.py)](#etl-layer)
2. [Cleaning Layer (cleaner.py)](#cleaning-layer)
3. [Sentiment Layer (analyzer.py)](#sentiment-layer)
4. [Visualization Layer (dashboard.py)](#visualization-layer)
5. [Pipeline Orchestration (pipeline.py)](#pipeline-orchestration)
6. [End-to-End Examples](#end-to-end-examples)

---

## ETL Layer

### `YouTubeClient`

```python
from etl.youtube_client import YouTubeClient

# Initialize with API key
client = YouTubeClient(api_key="YOUR_API_KEY")
# or via env var: export YOUTUBE_API_KEY="..."
client = YouTubeClient()
```

#### `get_channel_id(handle: str) -> str`

Resolve a YouTube channel @handle to its ID.

```python
channel_id = client.get_channel_id("@PolicyPulse")
# Returns: "UC_policy_001"
```

**Parameters:**
- `handle` (str): Channel handle, e.g., "@PolicyPulse" or "PolicyPulse"

**Returns:**
- Channel ID (str)

**Raises:**
- `ValueError` if channel not found

---

#### `get_uploads_playlist_id(channel_id: str) -> str`

Get the hidden "uploads" playlist for a channel (contains all videos).

```python
uploads_id = client.get_uploads_playlist_id("UC_policy_001")
# Returns: "UU_policy_001"
```

**Parameters:**
- `channel_id` (str): YouTube channel ID

**Returns:**
- Playlist ID (str)

---

#### `get_video_ids(playlist_id: str, max_videos: int = 200) -> list[str]`

Paginate through an uploads playlist and collect video IDs.

```python
video_ids = client.get_video_ids("UU_policy_001", max_videos=100)
# Returns: ["vid_0001", "vid_0002", ..., "vid_0100"]
```

**Parameters:**
- `playlist_id` (str): Playlist ID
- `max_videos` (int): Max videos to collect (default: 200)

**Returns:**
- List of video IDs

**Pagination:**
- Automatically handles `nextPageToken` from API
- Sleeps 2 seconds between requests (quota courtesy)

---

#### `get_video_metadata(video_ids: list[str]) -> pd.DataFrame`

Batch-fetch metadata for video IDs (50 per request).

```python
videos_df = client.get_video_metadata(["vid_0001", "vid_0002", ..., "vid_0050"])
# Returns DataFrame with schema:
# video_id, channel_id, title, description, published_at,
# view_count, like_count, comment_count, duration_seconds, is_short, ...
```

**Parameters:**
- `video_ids` (list[str]): List of YouTube video IDs

**Returns:**
- DataFrame with 13 columns (see data/raw/README.md)

**Output columns:**

| Column | Type | Description |
|---|---|---|
| `video_id` | str | YouTube video ID |
| `title` | str | Video title |
| `channel_title` | str | Channel name |
| `published_at` | datetime | Upload timestamp (UTC) |
| `view_count` | int | Total views |
| `like_count` | int | Total likes |
| `comment_count` | int | Total comments |
| `duration_seconds` | int | Duration in seconds |
| `is_short` | bool | True if duration ≤ 60s |

**Notes:**
- Batches requests in groups of 50
- Automatically coerces numeric columns
- Parses ISO 8601 durations (e.g., PT4M13S → 253 seconds)

---

#### `get_comments(video_id: str, max_comments: int = 500, order: str = "relevance") -> pd.DataFrame`

Extract top-level comments for a video.

```python
comments_df = client.get_comments("vid_0001", max_comments=200, order="relevance")
# Returns DataFrame with schema:
# comment_id, video_id, author, text, like_count, reply_count, published_at, ...
```

**Parameters:**
- `video_id` (str): YouTube video ID
- `max_comments` (int): Hard cap on comments returned (default: 500)
- `order` (str): "relevance" or "time" (default: "relevance")

**Returns:**
- DataFrame with 8 columns

**Output columns:**

| Column | Type |
|---|---|
| `comment_id` | str |
| `video_id` | str |
| `author` | str |
| `text` | str |
| `like_count` | int |
| `reply_count` | int |
| `published_at` | datetime |

**Behavior:**
- Handles disabled comments gracefully (logs warning, returns empty DataFrame)
- Sleeps between paginated requests (quota courtesy)
- Returns only top-level comments (replies not fetched)

**Example: Full video audit**

```python
video_ids = client.get_video_ids(uploads_id, max_videos=10)
videos_df = client.get_video_metadata(video_ids)
all_comments = []
for vid in video_ids:
    comments = client.get_comments(vid, max_comments=200)
    all_comments.append(comments)
    
comments_df = pd.concat(all_comments, ignore_index=True)
```

---

#### `audit_channel(handle: str, max_videos: int = 100, max_comments_per_video: int = 200, output_dir: str = "data/raw") -> tuple[pd.DataFrame, pd.DataFrame]`

End-to-end channel audit (resolve → fetch → extract → save).

```python
videos_df, comments_df = client.audit_channel(
    "@PolicyPulse",
    max_videos=100,
    max_comments_per_video=200,
    output_dir="data/raw"
)

print(f"Videos: {len(videos_df)}, Comments: {len(comments_df)}")
# Videos: 100, Comments: 18243
```

**Parameters:**
- `handle` (str): Channel @handle
- `max_videos` (int): Max videos to audit (default: 100)
- `max_comments_per_video` (int): Max comments per video (default: 200)
- `output_dir` (str): Directory for Parquet output

**Returns:**
- Tuple of (videos_df, comments_df)
- Also saves to `{output_dir}/{handle}_videos.parquet` and `{handle}_comments.parquet`

**Quota cost:**
- Approximately 300–400 units for a 100-video × 200-comment audit
- Well within daily limit of 10,000 units

---

### `RecommendationCrawler`

```python
from etl.youtube_client import YouTubeClient, RecommendationCrawler

client = YouTubeClient()
crawler = RecommendationCrawler(client, depth=5)
```

#### `crawl(seed_video_id: str, persona_label: str = "general") -> pd.DataFrame`

Follow the recommendation chain ("Up Next") from a seed video.

```python
recs_df = crawler.crawl("dQw4w9WgXcQ", persona_label="policy_focused")
# Returns DataFrame:
#   hop | recommended_video_id | recommended_title | persona
#   1   | <id>                 | <title>           | policy_focused
#   2   | <id>                 | <title>           | policy_focused
#   ...
```

**Parameters:**
- `seed_video_id` (str): Starting YouTube video ID
- `persona_label` (str): Label for this recommendation trajectory (e.g., "policy_focused", "general_interest", "francophone")

**Returns:**
- DataFrame with columns: `hop`, `seed_video_id`, `recommended_video_id`, `recommended_title`, `recommended_channel`, `persona`, `crawled_at`

**Use case:**
Compare recommendation chains for different personas to detect algorithmic bias:

```python
seed_civic_video = "vid_0001"

# Persona 1: Policy-focused anglophone
recs_policy = crawler.crawl(seed_civic_video, persona_label="policy_focused_en")

# Persona 2: General interest francophone
recs_general = crawler.crawl(seed_civic_video, persona_label="general_interest_fr")

# Combine and analyse
all_recs = pd.concat([recs_policy, recs_general])
recs_by_persona = all_recs.groupby("persona")["recommended_channel"].nunique()
# Policy-focused sees 12 different channels
# General interest sees 8 different channels
```

---

## Cleaning Layer

### `clean_text(text: str, remove_urls: bool = True, lowercase: bool = True, remove_emoji: bool = False, ...) -> str`

Configurable text preprocessing pipeline.

```python
from cleaning.cleaner import clean_text

raw = "Check this out! https://t.co/abc123 #policy @PolicyPulse 🔥"
cleaned = clean_text(raw)
# Returns: "check this out #policy @policypulse"
```

**Parameters:**
- `text` (str): Raw text
- `remove_urls` (bool): Strip URLs (default: True)
- `remove_mentions` (bool): Strip @mentions (default: False — preserved for civic signal)
- `remove_hashtags` (bool): Strip hashtags (default: False)
- `remove_emoji` (bool): Strip emoji (default: False)
- `lowercase` (bool): Lowercase (default: True)
- `normalize_unicode` (bool): NFKC normalization (default: True)

**Returns:**
- Cleaned string

**Defaults tuned for:**
- Sentiment analysis (URLs stripped, mentions/hashtags preserved)
- Social media short text (emoji okay)
- Canadian bilingual context (unicode normalization)

---

### `detect_language_simple(text: str) -> str`

Heuristic EN vs. FR language detection.

```python
from cleaning.cleaner import detect_language_simple

detect_language_simple("The budget was a disappointment")
# Returns: "en"

detect_language_simple("Le budget était décevant")
# Returns: "fr"
```

**Parameters:**
- `text` (str): Comment text

**Returns:**
- Language code: "en" or "fr"

**Method:**
- Checks token overlap with high-frequency French function words
- Simple but effective for Canadian civic discourse
- For production: replace with `langdetect` or `lingua-py`

---

### `CommentCleaner`

```python
from cleaning.cleaner import CommentCleaner

cleaner = CommentCleaner(min_chars=5, dedup=True)
comments_clean = cleaner.clean(comments_raw_df)
```

#### `__init__(min_chars: int = 5, dedup: bool = True)`

Initialize cleaner with options.

**Parameters:**
- `min_chars` (int): Minimum comment length after cleaning (default: 5)
- `dedup` (bool): Deduplicate on (video_id, text_clean) (default: True)

---

#### `clean(df: pd.DataFrame) -> pd.DataFrame`

Full comment cleaning pipeline.

```python
comments_clean = cleaner.clean(comments_raw)
# Input shape: (2000, 8)
# Output shape: (1214, 11)  — deduped, dropped short comments
```

**Pipeline steps:**
1. Schema normalisation (rename platform-specific columns)
2. Unicode normalisation (NFKC)
3. Text cleaning (URLs, emoji, whitespace)
4. Deduplication on (video_id, text_clean)
5. Language detection
6. Numeric/datetime coercion
7. Column selection and ordering

**Output columns:**

| Column | Type | Source |
|---|---|---|
| `comment_id` | str | raw |
| `video_id` | str | raw |
| `text_raw` | str | preserved from raw |
| `text_clean` | str | processed |
| `language_detected` | str | computed |
| `like_count` | int64 | raw |
| `reply_count` | int64 | raw |
| `published_at` | datetime64 | raw |
| `extracted_at` | datetime64 | raw |
| `platform` | str | raw |

---

### `VideoMetadataCleaner`

```python
from cleaning.cleaner import VideoMetadataCleaner

cleaner = VideoMetadataCleaner()
videos_clean = cleaner.clean(videos_raw_df)
```

#### `clean(df: pd.DataFrame) -> pd.DataFrame`

Normalise video metadata.

```python
videos_clean = cleaner.clean(videos_raw)
# Input shape: (80, 14)
# Output shape: (80, 14)  — same, but clean types & schema
```

**Pipeline steps:**
1. Numeric coercion (view_count, like_count, etc.)
2. Datetime coercion (published_at, extracted_at)
3. Boolean derivation (is_short = duration_seconds ≤ 60)
4. Deduplication on video_id
5. Text cleanup (title, description whitespace)
6. Column selection

---

### `add_engagement_metrics(videos_df: pd.DataFrame) -> pd.DataFrame`

Compute normalised engagement ratios.

```python
from cleaning.cleaner import add_engagement_metrics

videos_with_metrics = add_engagement_metrics(videos_clean)
# Adds 3 columns: engagement_rate, comment_rate, like_to_comment
```

**Added columns:**

| Column | Formula | Interpretation |
|---|---|---|
| `engagement_rate` | likes / views × 1,000 | Likes per 1,000 views |
| `comment_rate` | comments / views × 1,000 | Comments per 1,000 views |
| `like_to_comment` | likes / comments | Engagement balance (discussion vs. reaction) |

**Example interpretation:**
- High engagement_rate + low comment_rate = strong reaction but low discussion
- High comment_rate + low like_to_comment = engaged discussion (many replies, few "quick reacts")

---

### `tag_civic_keywords(df: pd.DataFrame, text_col: str = "text_clean") -> pd.DataFrame`

Flag comments containing civic keyword groups.

```python
from cleaning.cleaner import tag_civic_keywords

comments_tagged = tag_civic_keywords(comments_clean, text_col="text_clean")
# Adds 3 boolean columns: kw_policy, kw_identity, kw_sentiment_signal
```

**Keyword groups:**

```python
CIVIC_KEYWORD_GROUPS = {
    "policy": [
        "budget", "tax", "carbon", "healthcare", "housing", "immigration",
        "climate", "election", "policy", "parliament", "senate", "federal",
        "provincial", "legislation", "bill", "reform",
    ],
    "identity": [
        "indigenous", "francophone", "anglophone", "minority", "rights",
        "gender", "diversity", "equity", "inclusion", "bilingual",
    ],
    "sentiment_signal": [
        "shame", "proud", "disgusting", "inspiring", "corrupt", "honest",
        "misleading", "transparent", "outrage", "hope",
    ],
}
```

**Output:**

```python
comments_tagged.loc[0]
# text_clean:          "this budget is corrupt and misleading"
# kw_policy:           True    (contains "budget")
# kw_identity:         False
# kw_sentiment_signal: True    (contains "corrupt", "misleading")
```

**Use case:**

```python
# Sentiment by topic
policy_sentiment = comments_tagged[comments_tagged["kw_policy"]]["ensemble_label"].value_counts()
identity_sentiment = comments_tagged[comments_tagged["kw_identity"]]["ensemble_label"].value_counts()

print(policy_sentiment)
# positive    87
# neutral     45
# negative    23

print(identity_sentiment)
# positive    12
# neutral     8
# negative    31   ← identity framing gets more negative sentiment
```

---

## Sentiment Layer

### `SentimentPipeline`

```python
from sentiment.analyzer import SentimentPipeline

# Option 1: VADER only (fast, no GPU)
pipe = SentimentPipeline(use_transformer=False)

# Option 2: VADER + transformer (higher accuracy)
pipe = SentimentPipeline(use_transformer=True)
```

#### `run(df: pd.DataFrame, text_col: str = "text_clean") -> pd.DataFrame`

Score all comments with sentiment models.

```python
comments_scored = pipe.run(comments_clean, text_col="text_clean")
# Adds 10 columns: vader_compound, vader_pos, vader_neg, vader_label,
#                  transformer_label, transformer_score, ensemble_label, sentiment_confidence
```

**Input:**
- DataFrame with cleaned comment text

**Output:**
- Same DataFrame + sentiment columns

**Added columns:**

| Column | Type | Range | Description |
|---|---|---|---|
| `vader_compound` | float | [-1.0, 1.0] | VADER composite score |
| `vader_pos` | float | [0, 1] | Proportion of positive tokens |
| `vader_neg` | float | [0, 1] | Proportion of negative tokens |
| `vader_label` | str | {pos, neu, neg} | VADER label (threshold: ±0.05) |
| `transformer_label` | str | {pos, neu, neg} | Transformer output |
| `transformer_score` | float | [0, 1] | Transformer confidence |
| `ensemble_label` | str | {pos, neu, neg} | Final label (see ensemble logic) |
| `sentiment_confidence` | float | [0, 1] | Confidence proxy |

**Ensemble logic:**

```
if vader_label == transformer_label:
    ensemble_label = vader_label  # agreement
else:
    if transformer_score >= 0.70:
        ensemble_label = transformer_label  # high confidence
    else:
        ensemble_label = vader_label  # fall back to VADER
```

**Example:**

```python
comments_scored.loc[0]
# text_clean:             "Great analysis!"
# vader_compound:         0.6875
# vader_label:            positive
# transformer_label:      positive
# transformer_score:      0.9234
# ensemble_label:         positive    ← agreement
# sentiment_confidence:   0.9234

comments_scored.loc[1]
# text_clean:             "Not bad I guess"
# vader_compound:         0.0619
# vader_label:            neutral
# transformer_label:      positive
# transformer_score:      0.6432
# ensemble_label:         neutral     ← disagree, TF score < 0.70, defer to VADER
```

---

### `VADERSentimentAnalyzer`

```python
from sentiment.analyzer import VADERSentimentAnalyzer

analyzer = VADERSentimentAnalyzer()
```

#### `score(text: str) -> SentimentResult`

Score a single comment.

```python
result = analyzer.score("This is great news for our community!")
# Returns SentimentResult object:
# result.vader_compound = 0.7964
# result.vader_label = "positive"
# result.vader_pos = 0.333
```

---

#### `score_batch(texts: list[str]) -> list[SentimentResult]`

Score multiple texts.

```python
texts = [
    "Great analysis!",
    "Not impressed",
    "Interesting perspective"
]
results = analyzer.score_batch(texts)
# Returns list of 3 SentimentResult objects
```

---

### `sentiment_summary(df: pd.DataFrame, group_by: Optional[list[str]] = None) -> pd.DataFrame`

Aggregate sentiment statistics.

```python
from sentiment.analyzer import sentiment_summary

# Overall summary
summary = sentiment_summary(comments_scored)
# Returns 1 row

# By channel
summary = sentiment_summary(comments_scored, group_by=["channel_title"])
# Returns N rows (one per channel)

# By channel + language
summary = sentiment_summary(comments_scored, group_by=["channel_title", "language_detected"])
# Returns N×2 rows (one per channel-language pair)
```

**Output columns:**

| Column | Type | Description |
|---|---|---|
| `total_comments` | int | N comments in group |
| `mean_compound` | float | Mean VADER score |
| `std_compound` | float | Std dev of scores |
| `positive_pct` | float | % ensemble_label == "positive" |
| `neutral_pct` | float | % ensemble_label == "neutral" |
| `negative_pct` | float | % ensemble_label == "negative" |

**Example:**

```python
summary = sentiment_summary(
    comments_scored, 
    group_by=["channel_title", "language_detected"]
)
summary
#          channel_title language_detected  total_comments  mean_compound  std_compound  positive_pct  neutral_pct  negative_pct
# 0     PolicyPulse     en                 892             0.1245         0.3234        38.2         45.1          16.7
# 1     PolicyPulse     fr                 124             0.0856         0.3456        32.3         51.6          16.1
# 2     CiviqueMtl      en                 156             0.2134         0.2987        42.9         40.4          16.7
# 3     CiviqueMtl      fr                 376             0.3456         0.2654        51.3         34.6          14.1
```

**Interpretation:**
- CiviqueMtl (French-language creator) gets more positive sentiment on FR comments (+0.35) vs. EN comments (+0.21)
- PolicyPulse gets similar sentiment on both languages (en: 0.12, fr: 0.09)

---

### `sentiment_by_language(df: pd.DataFrame) -> pd.DataFrame`

Convenience wrapper for EN vs. FR comparison.

```python
from sentiment.analyzer import sentiment_by_language

lang_summary = sentiment_by_language(comments_scored)
# Equivalent to:
# sentiment_summary(comments_scored, group_by=["channel_title", "language_detected"])
```

---

### `detect_sentiment_drift(df: pd.DataFrame, window_days: int = 14, threshold: float = 0.15, ...) -> pd.DataFrame`

Flag periods of significant audience sentiment shift.

```python
from sentiment.analyzer import detect_sentiment_drift

drift_df = detect_sentiment_drift(
    comments_scored,
    window_days=14,
    threshold=0.15,
    group_col="channel_title"
)

drift_events = drift_df[drift_df["drift_flagged"] == True]
print(drift_events)
#   channel_title  date        rolling_mean  prior_mean  delta  drift_flagged
# 0 PolicyPulse    2025-02-21  0.1234       -0.0234     0.1468  True
# 1 PolicyPulse    2025-03-05  -0.0567      0.1823      0.2390  True
```

**Parameters:**
- `df` (pd.DataFrame): Comments with timestamps and scores
- `window_days` (int): Rolling window size (default: 14)
- `threshold` (float): Min absolute shift to flag (default: 0.15)
- `date_col` (str): Column with comment timestamps
- `score_col` (str): Column with sentiment scores
- `group_col` (str): Column to stratify by (default: "channel_title")

**Output columns:**

| Column | Type | Description |
|---|---|---|
| `date` | date | Date |
| `daily_mean` | float | Mean sentiment for that day |
| `rolling_mean` | float | 14-day rolling mean |
| `prior_mean` | float | Rolling mean 14 days ago |
| `delta` | float | \|rolling_mean - prior_mean\| |
| `drift_flagged` | bool | delta >= threshold |
| `channel_title` | str | Channel (if grouped) |

**Use case:**

```python
drift_df = detect_sentiment_drift(comments_scored, window_days=7, threshold=0.10)
big_shifts = drift_df[drift_df["drift_flagged"]]

# What happened on March 5?
# Sentiment shifted from +0.18 to -0.06 (delta = 0.24)
# Around this time: federal budget announcement
# Hypothesis: budget triggered negative audience response
```

---

### `top_comments(df: pd.DataFrame, label: str = "positive", n: int = 10, score_col: str = "vader_compound") -> pd.DataFrame`

Retrieve the most extreme comments for a label.

```python
from sentiment.analyzer import top_comments

# Top 10 most positive comments
top_pos = top_comments(comments_scored, label="positive", n=10)

# Top 10 most negative comments
top_neg = top_comments(comments_scored, label="negative", n=10)

print(top_pos.iloc[0]["text_clean"])
# "absolutely brilliant analysis of the budget implications"
```

**Use case:**
Qualitative validation — read the actual extreme comments to verify sentiment scores make sense.

---

## Visualization Layer

### `render_all(videos_df: pd.DataFrame, comments_df: pd.DataFrame, output_dir: str = "outputs") -> dict[str, go.Figure]`

Render all 8 dashboard figures.

```python
from visualization.dashboard import render_all

figures = render_all(videos_enriched, comments_scored, output_dir="outputs")

# Saves 8 HTML files to outputs/:
# - sentiment_over_time.html
# - label_distribution.html
# - engagement_vs_sentiment.html
# - comment_volume_heatmap.html
# - top_terms.html
# - language_breakdown.html
# - keyword_sentiment_heatmap.html
# - sentiment_drift.html

# Returns dict of Plotly Figure objects
print(list(figures.keys()))
# ['sentiment_over_time', 'label_distribution', 'engagement_vs_sentiment', ...]
```

---

### Individual Figure Functions

#### `plot_sentiment_over_time(...) -> go.Figure`

Rolling sentiment timeline.

```python
from visualization.dashboard import plot_sentiment_over_time

fig = plot_sentiment_over_time(
    comments_scored,
    channel_col="channel_title",
    window=7,
    output_path="outputs/sentiment_over_time.html"
)
```

**Shows:** 7-day rolling average VADER compound score per channel over time

---

#### `plot_label_distribution(...) -> go.Figure`

Stacked bar of pos/neu/neg distribution.

```python
from visualization.dashboard import plot_label_distribution

fig = plot_label_distribution(
    comments_scored,
    channel_col="channel_title",
    output_path="outputs/label_distribution.html"
)
```

**Shows:** 100% stacked bar with percentage breakdown per channel

---

#### `plot_engagement_vs_sentiment(...) -> go.Figure`

Scatter: engagement rate vs. avg sentiment.

```python
from visualization.dashboard import plot_engagement_vs_sentiment

fig = plot_engagement_vs_sentiment(
    videos_enriched,
    output_path="outputs/engagement_vs_sentiment.html"
)
```

**Shows:** 
- X axis: mean comment sentiment per video
- Y axis: engagement rate (likes per 1k views)
- Bubble size: view count
- Color: channel

**Insight:** If bubble cluster bottom-right (low sentiment, high engagement), provocative content drives reach

---

#### `plot_sentiment_drift(...) -> go.Figure`

Timeline with drift event markers.

```python
from visualization.dashboard import plot_sentiment_drift

fig = plot_sentiment_drift(
    drift_df,
    channel_col="channel_title",
    output_path="outputs/sentiment_drift.html"
)
```

**Shows:** Rolling mean compound score per channel with red diamond markers at flagged drift events

---

## Pipeline Orchestration

### `pipeline.py`

#### Command-line interface

```bash
# Demo mode (no API key needed)
python pipeline.py --demo

# Full audit on real YouTube channels
python pipeline.py \
  --channels @PolicyPulse @CiviqueMontréal \
  --max-videos 100 \
  --max-comments 300 \
  --transformer

# Options
python pipeline.py --help
# Usage: pipeline.py [--channels HANDLE ...] [--demo] [--max-videos N] 
#                    [--max-comments N] [--output-dir PATH] [--transformer]
```

---

#### `generate_mock_data(n_videos: int = 80, n_comments: int = 2000, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]`

Generate synthetic demo data.

```python
from pipeline import generate_mock_data

videos_df, comments_df = generate_mock_data(n_videos=100, n_comments=3000, seed=42)

# Returns realistic-looking synthetic data with:
# - 2 fictional channels (PolicyPulse, CiviqueMontréal)
# - Civic video titles and comments
# - Weighted sentiment distribution (40% pos, 35% neu, 25% neg)
# - Bilingual comments (EN and FR)
```

---

#### `run_pipeline(videos_df: pd.DataFrame, comments_df: pd.DataFrame, output_dir: str = "outputs", use_transformer: bool = False) -> dict`

End-to-end pipeline.

```python
from pipeline import generate_mock_data, run_pipeline

# Generate mock data
videos_df, comments_df = generate_mock_data()

# Run full pipeline
results = run_pipeline(
    videos_df,
    comments_df,
    output_dir="outputs",
    use_transformer=False
)

# Returns dict with:
# results["sentiment_summary"]  → DataFrame of aggregated stats
# results["figures"]            → dict of Plotly Figure objects
```

**Pipeline steps:**
1. Clean videos and comments
2. Score sentiment (VADER ± transformer)
3. Merge video + comment sentiment
4. Render 8 visualizations
5. Save all outputs

---

## End-to-End Examples

### Example 1: Minimal Demo

```python
from pipeline import generate_mock_data, run_pipeline

# Generate synthetic data
videos_df, comments_df = generate_mock_data(n_videos=50, n_comments=1000)

# Run pipeline
results = run_pipeline(videos_df, comments_df)

# Access results
print(results["sentiment_summary"])
# Shows sentiment stats by channel

# View a figure in Jupyter
results["figures"]["sentiment_over_time"].show()
```

---

### Example 2: Real YouTube Audit

```python
from etl.youtube_client import YouTubeClient
from cleaning.cleaner import CommentCleaner, VideoMetadataCleaner, add_engagement_metrics
from sentiment.analyzer import SentimentPipeline, sentiment_summary
from visualization.dashboard import render_all

# Step 1: Extract
client = YouTubeClient(api_key="YOUR_KEY")
videos_raw, comments_raw = client.audit_channel("@PolicyPulse", max_videos=100)

# Step 2: Clean
video_cleaner = VideoMetadataCleaner()
comment_cleaner = CommentCleaner()
videos_clean = video_cleaner.clean(videos_raw)
comments_clean = comment_cleaner.clean(comments_raw)
videos_clean = add_engagement_metrics(videos_clean)

# Step 3: Sentiment
pipe = SentimentPipeline(use_transformer=True)
comments_scored = pipe.run(comments_clean, text_col="text_clean")

# Step 4: Analysis
summary = sentiment_summary(comments_scored, group_by=["language_detected"])
print(summary)

# Step 5: Visualisation
figures = render_all(videos_clean, comments_scored)
```

---

### Example 3: Keyword-Based Topic Analysis

```python
from cleaning.cleaner import tag_civic_keywords
from sentiment.analyzer import sentiment_summary

# Tag keywords
comments_tagged = tag_civic_keywords(comments_scored)

# Sentiment breakdown by keyword group
policy_sentiment = sentiment_summary(
    comments_tagged[comments_tagged["kw_policy"]],
    group_by=["channel_title"]
)

identity_sentiment = sentiment_summary(
    comments_tagged[comments_tagged["kw_identity"]],
    group_by=["channel_title"]
)

print("Policy framing:")
print(policy_sentiment[["channel_title", "mean_compound", "positive_pct"]])

print("\nIdentity framing:")
print(identity_sentiment[["channel_title", "mean_compound", "positive_pct"]])

# Compare: which framing gets better reception?
```

---

### Example 4: Algorithmic Bias Audit

```python
from etl.youtube_client import YouTubeClient, RecommendationCrawler

client = YouTubeClient()
crawler = RecommendationCrawler(client, depth=5)

# Seed civic video
seed_id = "dQw4w9WgXcQ"

# Follow recommendations for different personas
recs_policy = crawler.crawl(seed_id, persona_label="policy_focused_en")
recs_general = crawler.crawl(seed_id, persona_label="general_interest_en")
recs_fr = crawler.crawl(seed_id, persona_label="francophone")

# Combine and analyse
all_recs = pd.concat([recs_policy, recs_general, recs_fr])

# Which creators are recommended most?
creator_counts = all_recs.groupby(["persona", "recommended_channel"]).size()
print(creator_counts)

# Hypothesis: algorithm surfaces different creators based on persona
# If policy_focused sees creator X but francophone doesn't, that's a signal
```

---

### Example 5: Drift Detection & Hypothesis Testing

```python
from sentiment.analyzer import detect_sentiment_drift

# Detect sentiment shifts
drift_df = detect_sentiment_drift(
    comments_scored,
    window_days=7,
    threshold=0.15
)

# Events flagged as drifts
events = drift_df[drift_df["drift_flagged"]]
print(events)

# For each event, check external calendar
# Feb 21 event: Federal budget announcement?
# Mar 5 event: Major news cycle?

# Validate hypothesis by reading actual comments
from sentiment.analyzer import top_comments

# Get most negative comments from Feb 21 drift period
drift_period = comments_scored[
    (comments_scored["published_at"] >= "2025-02-20") &
    (comments_scored["published_at"] <= "2025-02-22")
]
top_neg = top_comments(drift_period, label="negative", n=5)
print(top_neg["text_clean"].values)
# "budget is a disappointment"
# "more handouts to the wealthy"
# ... confirms policy sentiment triggered by budget announcement
```

---

**For more examples and integrations, see the notebooks/ directory (coming soon).**
