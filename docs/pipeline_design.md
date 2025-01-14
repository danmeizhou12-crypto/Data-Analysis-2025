# Civic YouTube Audit — Pipeline Design

## Motivation

The goal of this pipeline is to support algorithmic audit research on YouTube civic content. This document records key design decisions to make the codebase easier to extend and review.

---

## Schema Design

The unified comment and video schemas are defined in `cleaning/cleaner.py` as `COMMENT_SCHEMA` and `VIDEO_SCHEMA`. All platform-specific column names are mapped to these schemas in `_normalise_columns()` before any downstream processing occurs.

This design means that adding a new platform (e.g. TikTok Research API) only requires:
1. A new client in `etl/` that extracts to a raw DataFrame
2. A mapping entry in `_normalise_columns()` for any non-standard column names

No changes are needed in the sentiment or visualization layers.

---

## Sentiment Ensemble Strategy

Two models are used:

- **VADER** — fast lexicon-based scoring, no GPU required, works well for social media short text
- **`cardiffnlp/twitter-roberta-base-sentiment-latest`** — fine-tuned transformer, more accurate but requires `torch`

The ensemble rule is:
- If both models agree → that label wins
- If they disagree → trust the transformer if its confidence score is ≥ 0.70; otherwise default to VADER

This avoids over-relying on the transformer for low-confidence predictions where VADER's lexicon signal may actually be more reliable.

---

## Parquet vs. CSV

Both formats are written at each stage:

- **Parquet** is the primary format for all pipeline steps — typed columns, efficient columnar reads, ~4× smaller on disk than equivalent CSV
- **CSV** is written alongside for human readability and compatibility with non-Python tooling

---

## Language Detection

The current implementation is a heuristic keyword-overlap classifier targeting English vs. French (Canadian civic context). It checks token overlap against a set of high-frequency French function words. For production use this should be replaced with `langdetect` or `lingua-py`, which handle code-switching and dialectal variation more robustly.

---

## Quota Management

The YouTube Data API v3 has a default quota of 10,000 units/day. Cost breakdown for a typical audit:

| Operation | Units per call | Calls for 100-video audit |
|---|---|---|
| `search.list` (channel resolve) | 100 | 1 |
| `channels.list` (playlist ID) | 1 | 1 |
| `playlistItems.list` (video IDs) | 1 | 2 |
| `videos.list` (metadata, 50/call) | 1 | 2 |
| `commentThreads.list` (per video) | 1 | 100+ |

A 100-video audit with 200 comments/video consumes roughly **300–400 quota units**, well within the daily limit. Batch requests for `videos.list` (50 IDs per call) keep this efficient.
