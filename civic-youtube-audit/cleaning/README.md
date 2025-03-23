# Cleaning Module (`cleaning/cleaner.py`)

## Overview

The cleaning module standardizes raw data from multiple sources into a unified schema, applies text preprocessing, and derives new features. It's the "glue" between extraction and analysis.

---

## Design Principle: Schema Normalisation

Raw data from YouTube, TikTok, Instagram (future) will have different column names and types:

```
YouTube raw:           TikTok raw:           Instagram raw:
─────────────────      ───────────────      ──────────────
video_id               id                   pk
title                  desc                 caption
view_count             play_count           view_count
like_count             favorite_count       engagement_count
comment_count          comment_count        comment_count
```

The cleaning layer **normalizes** these to a unified schema:

```
Unified schema:
───────────────
video_id
title
description
view_count
like_count
comment_count
platform  ← tracks source
```

This allows downstream layers (sentiment, viz) to work identically across platforms.

---

## Core Classes

### `CommentCleaner`

**Purpose:** Clean and standardise comments.

**Initialization:**

```python
from cleaning.cleaner import CommentCleaner

cleaner = CommentCleaner(
    min_chars=5,  # drop comments shorter than 5 chars after cleaning
    dedup=True    # deduplicate on (video_id, text_clean)
)
```

**Usage:**

```python
comments_clean = cleaner.clean(comments_raw)
```

**Pipeline (in order):**

1. **Schema normalisation**
   - Rename platform-specific columns (`body` → `text`, `likes` → `like_count`, etc.)
   - Defined in `_normalise_columns()` mapping

2. **Preserve raw text**
   - Add `text_raw` column (unmodified original)
   - Allows tracing back to source if needed

3. **Text cleaning** (via `clean_text()`)
   - Unicode NFKC normalisation (compatibility decomposition)
   - URL stripping (http/www patterns)
   - Emoji removal (optional)
   - Whitespace collapsing (multiple spaces → single)
   - Lowercase
   - Add to `text_clean` column

4. **Drop short comments**
   - Comments with `len(text_clean) < min_chars` are dropped
   - Default: 5 characters
   - Example: "lol" → dropped, "great!" → kept

5. **Deduplication**
   - Drop exact duplicates on `(video_id, text_clean)` composite key
   - Keeps first occurrence
   - Logs number of duplicates removed

6. **Language detection**
   - Call `detect_language_simple()` on `text_raw`
   - Returns "en" or "fr"
   - Add to `language_detected` column

7. **Type coercion**
   - Convert `like_count`, `reply_count` → int64 (handle NaN/errors)
   - Convert `published_at`, `extracted_at` → datetime64[UTC]
   - Fill missing numeric with 0

8. **Column selection**
   - Select only unified schema columns (in order)
   - Drop platform-specific remnants
   - Reset index

**Output shape:**

```
Input:  (2000 rows, 8 cols)  ← raw from YouTube API
Process:
  - Drop 400 short comments   (1600 rows)
  - Dedup 386 duplicates      (1214 rows)
Output: (1214 rows, 11 cols)  ← cleaned, deduplicated
```

---

### `VideoMetadataCleaner`

**Purpose:** Standardise video metadata.

**Initialization:**

```python
from cleaning.cleaner import VideoMetadataCleaner

cleaner = VideoMetadataCleaner()
```

**Pipeline:**

1. **Numeric coercion** — view_count, like_count, comment_count, duration_seconds → int64
2. **Datetime coercion** — published_at, extracted_at → datetime64[UTC]
3. **Boolean derivation** — is_short = duration_seconds ≤ 60
4. **Deduplication** — exact duplicates on video_id
5. **Text cleanup** — title, description whitespace stripping
6. **Column selection** — unified schema columns only

**Output shape:**

```
Input:  (100 rows, 14 cols)  ← raw from API
Output: (100 rows, 14 cols)  ← same, clean types + schema
```

---

## Text Preprocessing

### `clean_text()` Function

Configurable text cleaning pipeline.

```python
from cleaning.cleaner import clean_text

text = "Check this: https://t.co/abc123 #policy @PolicyPulse 🔥 AMAZING!!!"

# Default (sentiment analysis friendly)
clean_text(text)
# → "check this #policy @policypulse amazing"
# (URLs stripped, mentions/hashtags preserved, emoji removed by default is False)

# Strict mode
clean_text(text, remove_mentions=True, remove_hashtags=True, remove_emoji=True)
# → "check this amazing"

# Case-sensitive keyword analysis
clean_text(text, lowercase=False)
# → "Check this #policy @PolicyPulse AMAZING"
```

**Defaults tuned for sentiment analysis:**
- URLs stripped (no semantic content for civic discourse)
- Mentions/hashtags preserved (carry social signal)
- Emoji removed (optional)
- Whitespace collapsed
- Unicode normalised

---

### `detect_language_simple()` Function

Heuristic EN/FR detection.

```python
from cleaning.cleaner import detect_language_simple

detect_language_simple("The budget was disappointing")
# → "en"

detect_language_simple("Le budget était décevant")
# → "fr"

detect_language_simple("C'est vraiment decevant and disappointing")  # code-switching
# → "fr"  (has 2+ French markers: "vraiment", "et" → counts as overlap)
```

**Method:**

```python
FRENCH_MARKERS = {
    "le", "la", "les", "de", "du", "des", "un", "une",
    "est", "sont", "avec", "pour", "dans", "sur", "qui",
    "que", "elle", "nous", "vous", "ils", "leur",
}

def detect_language_simple(text):
    tokens = set(re.findall(r"\b[a-zéàèùâêîôûëïüç]+\b", text.lower()))
    overlap = tokens & FRENCH_MARKERS
    return "fr" if len(overlap) >= 2 else "en"
```

**Limitations:**
- Only EN/FR (Canadian context)
- Doesn't handle code-switching perfectly
- No probability scores
- **For production:** use `langdetect` or `lingua-py`

---

## Feature Engineering

### `add_engagement_metrics()` Function

Compute normalised engagement ratios.

```python
from cleaning.cleaner import add_engagement_metrics

videos_with_metrics = add_engagement_metrics(videos_clean)
```

**Added columns:**

```python
engagement_rate = likes / views * 1000    # likes per 1,000 views
comment_rate = comments / views * 1000    # comments per 1,000 views
like_to_comment = likes / comments        # balance of reactions vs. discussion
```

**Interpretation:**

```
Example video 1:
  views: 100,000
  likes: 5,000
  comments: 500
  
  engagement_rate: (5,000 / 100,000) × 1,000 = 50
  comment_rate: (500 / 100,000) × 1,000 = 5
  like_to_comment: 5,000 / 500 = 10
  
  Interpretation:
    High like_to_comment ratio (10:1) = reactive audience (lots of quick likes)
    Low comment_rate (5 per 1k) = limited discussion

Example video 2:
  views: 50,000
  likes: 1,500
  comments: 1,000
  
  engagement_rate: (1,500 / 50,000) × 1,000 = 30
  comment_rate: (1,000 / 50,000) × 1,000 = 20
  like_to_comment: 1,500 / 1,000 = 1.5
  
  Interpretation:
    Lower like_to_comment (1.5:1) = discussion-focused audience
    High comment_rate (20 per 1k) = engaged discussion
```

---

### `tag_civic_keywords()` Function

Flag comments containing civic keyword groups.

```python
from cleaning.cleaner import tag_civic_keywords

comments_tagged = tag_civic_keywords(comments_clean, text_col="text_clean")
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
# text_clean:             "the budget is corrupt"
# kw_policy:              True     (contains "budget")
# kw_identity:            False
# kw_sentiment_signal:    True     (contains "corrupt")

comments_tagged[comments_tagged["kw_policy"]].shape
# (387, 14)  ← 387 comments mention policy terms
```

**Use case:**

```python
# Sentiment by topic
policy_df = comments_tagged[comments_tagged["kw_policy"]]
sentiment_by_policy = policy_df["ensemble_label"].value_counts()

identity_df = comments_tagged[comments_tagged["kw_identity"]]
sentiment_by_identity = identity_df["ensemble_label"].value_counts()

print("Policy framing:")
print(sentiment_by_policy)
# positive    162
# neutral     149
# negative     76

print("\nIdentity framing:")
print(sentiment_by_identity)
# positive     32
# neutral      24
# negative     54  ← identity framing gets MORE negative sentiment
```

---

## Data Transformation Examples

### Example 1: Raw → Cleaned

```
INPUT (raw):
┌─────────────────────────────────────────────────────┐
│ video_id  text                  like_count          │
├─────────────────────────────────────────────────────┤
│ vid_001   "Great! https://t.co/abc"   10            │
│ vid_001   "great! https://t.co/abc"   9             │ ← duplicate
│ vid_002   "lol"                       1              │ ← too short
│ vid_002   "Disappointed with the      23            │
│           policy..."                                │
│ vid_003   ""                          0              │ ← empty
└─────────────────────────────────────────────────────┘

PROCESS:
  1. Clean text: "Great! https://t.co/abc" → "great"
  2. Dedup: drop identical (vid_001, "great")
  3. Drop short: "lol" has len=3 < min_chars=5
  4. Drop empty: "" filtered out
  
OUTPUT (cleaned):
┌────────────────────────────────────────────────────┐
│ video_id  text_raw              text_clean  like   │
├────────────────────────────────────────────────────┤
│ vid_001   "Great! https://t..."  "great"    10     │
│ vid_002   "Disappointed with"    "disappointed"    │
│           ...                    "with the policy" │
│           ...                                23    │
└────────────────────────────────────────────────────┘

Result: 2 rows (from 5) — 60% of raw data was noise
```

---

### Example 2: Engagement Metrics

```
Input video:
  title: "Breaking Down the Budget"
  view_count: 45,302
  like_count: 2,156
  comment_count: 387

Computed:
  engagement_rate = 2,156 / 45,302 × 1,000 = 47.6
  comment_rate = 387 / 45,302 × 1,000 = 8.5
  like_to_comment = 2,156 / 387 = 5.6

Interpretation:
  - 47.6 likes per 1,000 views = strong reaction
  - 8.5 comments per 1,000 views = moderate discussion
  - 5.6 ratio = mostly reactions, not deep discussion
```

---

## Integration with Pipeline

```
etl/
  videos_raw.parquet
  comments_raw.parquet
        ↓
   cleaning/cleaner.py
        ↓
processed/
  videos_clean.parquet
  comments_clean.parquet
        ↓
  sentiment/analyzer.py
        ↓
processed/
  videos_enriched.parquet
  comments_scored.parquet
```

---

## Configuration

### Customizing Cleaners

```python
# Strict cleaning (remove more)
strict_cleaner = CommentCleaner(min_chars=10, dedup=True)

# Lenient cleaning (keep more)
lenient_cleaner = CommentCleaner(min_chars=3, dedup=False)

comments_strict = strict_cleaner.clean(raw)    # fewer rows
comments_lenient = lenient_cleaner.clean(raw)  # more rows
```

---

### Customizing Text Processing

```python
# For different use cases
clean_text(
    "Check https://t.co/abc #policy @PolicyPulse 🔥",
    remove_urls=True,        # default: True
    remove_mentions=False,   # default: False (keep for civic signal)
    remove_hashtags=False,   # default: False
    remove_emoji=False,      # default: False
    lowercase=True,          # default: True
    normalize_unicode=True,  # default: True
)
```

---

## Performance

For a 100-video audit (1,214 final comments):

| Step | Time |
|---|---|
| Schema normalisation | <1s |
| Text cleaning (1,214 comments) | ~500ms |
| Language detection | ~200ms |
| Deduplication | <100ms |
| Type coercion | <100ms |
| **Total** | **~1 second** |

Memory footprint: ~10MB for 1,214 comments

---

## Testing

```bash
# Test with demo data
python pipeline.py --demo

# Check output
head -5 outputs/comments_clean.csv
```

---

## Future Enhancements

- [ ] Support for reply threads (nested comments)
- [ ] Multi-language support (more than EN/FR)
- [ ] Emoji sentiment analysis (preserve emoji + score separately)
- [ ] Named entity recognition (extract people/places mentioned)
- [ ] Aspect-based sentiment (what specifically is the sentiment about?)
