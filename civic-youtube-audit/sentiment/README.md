# Sentiment Module (`sentiment/analyzer.py`)

## Overview

The sentiment module scores comments using two complementary NLP approaches and combines them with ensemble logic. It answers: **What is the sentiment of this comment? How confident are we?**

---

## Sentiment Models

### VADER (Valence Aware Dictionary sEntiment Reasoner)

**Type:** Lexicon-based (rules + word dictionary)

**Speed:** ~1ms per text (CPU only)

**Strengths:**
- Interpretable (you can see which words triggered positive/negative)
- No training needed
- Works on social media short text
- Handles emoticons, slang, punctuation emphasis

**Weaknesses:**
- Can't learn new word meanings (hasn't seen all civic vocabulary)
- Struggles with sarcasm ("fantastic, just what we needed" = negative)

**Output:**
```python
{
    "neg": 0.0,        # proportion of negative tokens
    "neu": 0.0,        # proportion of neutral tokens  
    "pos": 1.0,        # proportion of positive tokens
    "compound": 1.0,   # composite score: -1.0 → +1.0
}
```

**Threshold logic:**
```
compound >= +0.05  → positive
compound <= -0.05  → negative
else               → neutral
```

**Example:**

```python
from sentiment.analyzer import VADERSentimentAnalyzer

analyzer = VADERSentimentAnalyzer()
result = analyzer.score("This budget is AMAZING!!!")
# compound = 0.7836
# label = "positive"
```

---

### HuggingFace Transformer

**Type:** Neural network (fine-tuned on social media)

**Model:** `cardiffnlp/twitter-roberta-base-sentiment-latest`

**Speed:** ~100ms per text (CPU) or ~10ms per text (GPU)

**Strengths:**
- More accurate on real-world social media text
- Learns word context and nuance
- Handles sarcasm better

**Weaknesses:**
- Black box (can't see decision reasoning)
- Requires GPU for speed
- Slower on CPU
- Larger model (requires ~2GB disk)

**Output:**
```python
{
    "label": "positive",    # or "negative", "neutral"
    "score": 0.9234,        # confidence 0.0 → 1.0
}
```

**Example:**

```python
from sentiment.analyzer import TransformerSentimentAnalyzer

analyzer = TransformerSentimentAnalyzer()
result = analyzer.score("This budget is AMAZING!!!")
# label = "positive"
# score = 0.9234  (94% confident)
```

---

## Ensemble Strategy

**Why combine two models?**

Each has different strengths. An ensemble leverages both:

```
Comment: "not bad I guess"

VADER:
  compound = 0.0619
  label = "neutral"

Transformer:
  label = "positive"
  score = 0.6432

Ensemble logic:
  They disagree. Transformer score (0.64) < 0.70 threshold.
  → Defer to VADER
  Final label = "neutral"

Interpretation:
  The comment is ambiguous. VADER's conservative label is safer
  than the transformer's less-confident prediction.
```

**Flow:**

```
Input text
    ↓
[VADER] → {compound, label}
    ↓
Agreement check
    ├─ YES → use common label
    └─ NO  → check transformer confidence
            ├─ score ≥ 0.70 → use transformer
            └─ score < 0.70 → use VADER (default to conservative)
    ↓
Output: ensemble_label
```

---

## SentimentPipeline Class

**Purpose:** Orchestrate VADER + optional transformer on full DataFrame.

```python
from sentiment.analyzer import SentimentPipeline

# VADER only (fast)
pipe = SentimentPipeline(use_transformer=False)

# VADER + transformer (accurate)
pipe = SentimentPipeline(use_transformer=True)

# Score all comments
comments_scored = pipe.run(comments_clean, text_col="text_clean")
```

**Output columns added:**

| Column | Type | Description |
|---|---|---|
| `vader_compound` | float | VADER composite score [-1, 1] |
| `vader_pos` | float | VADER positive proportion [0, 1] |
| `vader_neg` | float | VADER negative proportion [0, 1] |
| `vader_label` | str | VADER label: pos/neu/neg |
| `transformer_label` | str | Transformer label (if enabled) |
| `transformer_score` | float | Transformer confidence [0, 1] |
| `ensemble_label` | str | Final label (VADER or transformer) |
| `sentiment_confidence` | float | Confidence proxy [0, 1] |

---

## Analysis Functions

### `sentiment_summary()`

Aggregate sentiment stats by optional grouping columns.

```python
from sentiment.analyzer import sentiment_summary

# Overall stats
summary = sentiment_summary(comments_scored)

# By channel
summary = sentiment_summary(comments_scored, group_by=["channel_title"])

# By channel × language
summary = sentiment_summary(
    comments_scored,
    group_by=["channel_title", "language_detected"]
)
```

**Output:**

```
        channel_title  language_detected  total_comments  mean_compound  ...
0       PolicyPulse    en                892             0.1245         ...
1       PolicyPulse    fr                124             0.0856         ...
2       CiviqueMtl     en                156             0.2134         ...
3       CiviqueMtl     fr                376             0.3456         ...
```

**Columns:**
- `total_comments` — N comments in group
- `mean_compound` — mean VADER score
- `std_compound` — std dev of scores
- `positive_pct` — % ensemble_label == "positive"
- `neutral_pct` — % ensemble_label == "neutral"
- `negative_pct` — % ensemble_label == "negative"

---

### `sentiment_by_language()`

Convenience wrapper for EN/FR breakdown.

```python
from sentiment.analyzer import sentiment_by_language

lang_summary = sentiment_by_language(comments_scored)
# Equivalent to:
# sentiment_summary(comments_scored, group_by=["channel_title", "language_detected"])
```

**Useful for:** Comparing how Anglophone vs. Francophone audiences respond.

---

### `detect_sentiment_drift()`

Flag periods of significant audience sentiment shift.

```python
from sentiment.analyzer import detect_sentiment_drift

drift_df = detect_sentiment_drift(
    comments_scored,
    window_days=14,
    threshold=0.15,
    group_col="channel_title"
)

events = drift_df[drift_df["drift_flagged"]]
```

**Output:**

| Column | Description |
|---|---|
| `date` | Date |
| `daily_mean` | Mean sentiment for that day |
| `rolling_mean` | N-day rolling mean |
| `prior_mean` | Rolling mean N days ago |
| `delta` | \|rolling_mean - prior_mean\| |
| `drift_flagged` | True if delta ≥ threshold |

**Use case:** Hypothesis testing

```python
# Mar 5: drift event detected (sentiment +0.18 → -0.06)
# What happened on Mar 5?
# → Federal budget announcement
# Hypothesis: Budget triggered negative audience response
```

---

### `top_comments()`

Retrieve extreme comments for qualitative validation.

```python
from sentiment.analyzer import top_comments

# Most positive comments
top_pos = top_comments(comments_scored, label="positive", n=10)

# Most negative comments
top_neg = top_comments(comments_scored, label="negative", n=10)

print(top_neg.iloc[0]["text_clean"])
# "absolutely terrible policy decision"
```

**Use case:** QA check — read the actual extreme comments to validate scores make sense.

---

## Performance

### Timing

For 1,000 comments:

| Model | Time | Hardware |
|---|---|---|
| VADER only | ~1 second | CPU |
| Transformer (first load) | ~100 seconds | CPU (+ 500MB download) |
| Transformer (cached) | ~100 seconds | CPU |
| Transformer | ~10 seconds | GPU (NVIDIA) |

### Optimization

Use VADER for fast iteration:

```bash
python pipeline.py --demo  # VADER only, <1 second
```

Use transformer when accuracy matters:

```bash
python pipeline.py --demo --transformer  # VADER + transformer
```

For production with GPU:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118
python pipeline.py --demo --transformer  # ~10 seconds
```

---

## Limitations

### VADER Limitations

- **Slang/new words:** "lit", "salty", "yeet" may not be recognized
- **Sarcasm:** "great policy" (sarcastic) scored as positive
- **Domain-specific:** Civic vocabulary like "election" need reinforcement
- **No context:** Doesn't understand sentence relationships

### Transformer Limitations

- **Black box:** Can't explain why it scored something a way
- **Overfitting:** May overfit to training data (Twitter, not civic discourse)
- **Slow on CPU:** Need GPU for interactive use
- **Memory:** Requires ~2GB disk + 2GB RAM for model

### Combined Limitations

- **No aspect-based sentiment:** Can't distinguish "policy good, implementation bad"
- **No intensity:** Only 3 labels (pos/neu/neg), not strong/weak
- **Language:** Only EN/FR detected; code-switching handled poorly
- **Context:** Comments analyzed in isolation, not threads

---

## Customisation

### Change VADER Thresholds

```python
# Current (neutral if compound in [-0.05, 0.05])
if compound >= 0.05:
    label = "positive"
elif compound <= -0.05:
    label = "negative"
else:
    label = "neutral"

# Stricter (less neutral)
if compound >= 0.10:
    label = "positive"
elif compound <= -0.10:
    label = "negative"
else:
    label = "neutral"
```

Edit in `sentiment/analyzer.py` `_vader_label()` function.

### Change Ensemble Confidence Threshold

```python
# Current
if transformer_score >= 0.70:
    ensemble_label = transformer_label
else:
    ensemble_label = vader_label

# More conservative (trust transformer less)
if transformer_score >= 0.90:
    ensemble_label = transformer_label
else:
    ensemble_label = vader_label
```

Edit in `SentimentPipeline._ensemble_row()`.

### Use Different Transformer Model

```python
pipe = SentimentPipeline(use_transformer=True)
pipe.transformer.MODEL = "distilbert-base-uncased-finetuned-sst-2-english"
```

Other models:
- `facebook/roberta-large-mnli` (zero-shot)
- `distilbert-base-uncased-finetuned-sst-2-english` (SST-2 dataset)
- `xlm-roberta-large` (multilingual)

---

## Future Enhancements

- [ ] Support multiple languages (beyond EN/FR)
- [ ] Aspect-based sentiment ("policy good, implementation bad")
- [ ] Intensity scores (strong positive vs. mild positive)
- [ ] Emotion detection (anger, joy, fear, etc.)
- [ ] Sarcasm detection
- [ ] Fine-tuning on civic discourse domain
- [ ] Batch GPU inference for speed

---

## References

- **VADER paper:** "VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text"
- **cardiffnlp model:** https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest
- **Ensemble learning:** https://en.wikipedia.org/wiki/Ensemble_learning
