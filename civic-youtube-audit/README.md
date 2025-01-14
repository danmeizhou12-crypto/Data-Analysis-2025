# 🇨🇦 Civic YouTube Audit Pipeline

An automated data engineering and NLP pipeline for auditing algorithmic bias and audience sentiment across YouTube civic-discourse content. Built as part of research into how influential Canadian creators frame political topics and how audiences respond.

---

## Overview

This project implements a full **Extract → Clean → Analyse → Visualise** pipeline against the YouTube Data API v3. It is designed to scale to multiple channels and support a cross-platform unified schema (ready for TikTok/Instagram extension).

**Key questions this pipeline is built to answer:**
- Does the YouTube algorithm promote or suppress specific civic framings depending on audience persona?
- How does audience sentiment vary across Anglophone vs. Francophone creators?
- Does higher engagement correlate with more polarised (positive or negative) comment sentiment?

---

## Pipeline Architecture

```
YouTube Data API v3
        │
        ▼
┌───────────────────┐
│  ETL Layer        │  youtube_client.py
│  Video metadata   │  → Paginated playlist crawl
│  Comments         │  → Thread extraction (up to 500/video)
│  Output: Parquet  │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Cleaning Layer   │  cleaner.py
│  Schema norm.     │  → Unified column names across platforms
│  Deduplication    │  → (video_id, text_clean) composite key
│  Text preprocessing│  → URL/whitespace stripping, unicode norm.
│  Lang. detection  │  → Heuristic EN/FR classifier
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Sentiment Layer  │  analyzer.py
│  VADER            │  → Lexicon-based, zero-latency
│  DistilBERT       │  → Twitter-fine-tuned transformer (optional)
│  Ensemble         │  → Agreement + confidence-weighted fallback
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Visualisation    │  dashboard.py
│  6 Plotly figures │  → Interactive HTML exports
└───────────────────┘
```

---

## Features

| Feature | Details |
|---|---|
| **YouTube API ETL** | Full channel audit: metadata + paginated comments → Parquet |
| **Unified schema** | Cross-platform JSON/Parquet schema (extensible to TikTok, IG) |
| **Dual sentiment** | VADER (fast) + HuggingFace transformer (accurate) with ensemble |
| **Language detection** | EN/FR heuristic classifier for Canadian bilingual analysis |
| **Engagement metrics** | Engagement rate, comment rate, like-to-comment ratio |
| **6 Plotly dashboards** | Sentiment over time, label distribution, engagement scatter, heatmap, top terms, language breakdown |
| **Demo mode** | Full pipeline demo with synthetic data — no API key required |

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/yourusername/civic-youtube-audit.git
cd civic-youtube-audit
pip install -r requirements.txt
```

### 2. Set API key

```bash
export YOUTUBE_API_KEY="your_key_here"
# or add to a .env file
```

### 3a. Run demo (no API key needed)

```bash
python pipeline.py --demo
```

### 3b. Run full audit on real channels

```bash
python pipeline.py \
  --channels @PolicyPulse @CiviqueMontréal \
  --max-videos 100 \
  --max-comments 300 \
  --transformer          # optional: requires torch + transformers
```

All outputs (Parquet, CSV, HTML figures) are written to `outputs/`.

---

## Output Files

```
outputs/
├── videos_clean.parquet        # Cleaned video metadata
├── videos_enriched.parquet     # + avg. sentiment per video
├── comments_clean.parquet      # Cleaned, deduplicated comments
├── comments_scored.parquet     # + VADER + transformer sentiment scores
├── sentiment_summary.csv       # Aggregated stats by channel
├── sentiment_over_time.html    # Rolling-avg sentiment timeline
├── label_distribution.html     # Pos/neu/neg % per channel
├── engagement_vs_sentiment.html # Engagement rate vs. avg. sentiment
├── comment_volume_heatmap.html # Activity by day × hour
├── top_terms.html              # Most common words by sentiment
└── language_breakdown.html     # EN vs. FR comment distribution
```

---

## Module Reference

### `etl/youtube_client.py`
- `YouTubeClient.audit_channel(handle, ...)` — full channel audit
- `YouTubeClient.get_video_metadata(video_ids)` — batch metadata fetch
- `YouTubeClient.get_comments(video_id, ...)` — paginated comment extraction

### `cleaning/cleaner.py`
- `CommentCleaner.clean(df)` — text clean + dedup + lang detect
- `VideoMetadataCleaner.clean(df)` — schema normalisation + type coercion
- `add_engagement_metrics(df)` — compute engagement/comment rates
- `clean_text(text, ...)` — configurable text preprocessing function

### `sentiment/analyzer.py`
- `SentimentPipeline.run(df)` — full scoring pipeline (VADER + transformer)
- `VADERSentimentAnalyzer.score_batch(texts)` — lexicon scoring
- `TransformerSentimentAnalyzer.score_batch(texts)` — transformer scoring
- `sentiment_summary(df, group_by)` — aggregated sentiment statistics

### `visualization/dashboard.py`
- `render_all(videos_df, comments_df)` — render and save all 6 figures
- Individual figure functions available for selective use

---

## Tech Stack

- **Python 3.11**
- **Pandas / NumPy** — data manipulation
- **Google API Python Client** — YouTube Data API v3
- **vaderSentiment** — lexicon-based NLP
- **HuggingFace Transformers** — `cardiffnlp/twitter-roberta-base-sentiment-latest`
- **Plotly** — interactive visualisations
- **PyArrow** — Parquet I/O

---

## Project Context

This pipeline was developed as part of the **Canadian Civic Influence Project**, which examines how influential female creators frame political and civic discourse and how audience sentiment responds across platforms. This phase focuses on YouTube as the primary platform, with the unified schema designed to support future TikTok and Instagram data integration.

---

## Roadmap

- [ ] Persona-based account simulation for algorithm audit crawls
- [ ] TikTok Research API integration
- [ ] LDA/BERTopic topic modelling on comment corpora
- [ ] Streamlit dashboard for interactive exploration
- [ ] Automated scheduling with GitHub Actions
