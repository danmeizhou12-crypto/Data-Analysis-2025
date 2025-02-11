"""
cleaning/cleaner.py
-------------------
Cross-platform data cleaning, schema normalization, and text preprocessing.

Designed for a unified civic-discourse dataset that may eventually include
TikTok, Instagram, or other platforms alongside YouTube. Each platform's
raw extract is normalised to a common schema before sentiment analysis.

Author: Kody
Project: Canadian Civic Influence Project — Algorithm Audit Pipeline
"""

import re
import logging
import unicodedata
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unified output schema
# ---------------------------------------------------------------------------
COMMENT_SCHEMA = {
    "comment_id": "string",
    "video_id": "string",
    "channel_title": "string",
    "platform": "string",
    "text_raw": "string",
    "text_clean": "string",
    "language_detected": "string",
    "like_count": "int64",
    "reply_count": "int64",
    "published_at": "datetime64[us, UTC]",
    "extracted_at": "datetime64[us, UTC]",
}

VIDEO_SCHEMA = {
    "video_id": "string",
    "channel_id": "string",
    "channel_title": "string",
    "platform": "string",
    "title": "string",
    "description": "string",
    "language": "string",
    "published_at": "datetime64[us, UTC]",
    "view_count": "int64",
    "like_count": "int64",
    "comment_count": "int64",
    "duration_seconds": "int64",
    "is_short": "bool",
    "extracted_at": "datetime64[us, UTC]",
}


# ---------------------------------------------------------------------------
# Text preprocessing
# ---------------------------------------------------------------------------
URL_RE = re.compile(r"https?://\S+|www\.\S+")
MENTION_RE = re.compile(r"@\w+")
HASHTAG_RE = re.compile(r"#\w+")
EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002700-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "]+",
    flags=re.UNICODE,
)
WHITESPACE_RE = re.compile(r"\s+")


def clean_text(
    text: str,
    remove_urls: bool = True,
    remove_mentions: bool = False,
    remove_hashtags: bool = False,
    remove_emoji: bool = False,
    lowercase: bool = True,
    normalize_unicode: bool = True,
) -> str:
    """
    Apply a configurable cleaning pipeline to a raw comment string.

    Defaults are tuned for sentiment analysis — URLs are stripped but
    mentions and hashtags are preserved as they carry civic-signal.
    """
    if not isinstance(text, str) or not text.strip():
        return ""

    if normalize_unicode:
        text = unicodedata.normalize("NFKC", text)
    if remove_urls:
        text = URL_RE.sub(" ", text)
    if remove_mentions:
        text = MENTION_RE.sub(" ", text)
    if remove_hashtags:
        text = HASHTAG_RE.sub(" ", text)
    if remove_emoji:
        text = EMOJI_RE.sub(" ", text)
    if lowercase:
        text = text.lower()

    text = WHITESPACE_RE.sub(" ", text).strip()
    return text


def detect_language_simple(text: str) -> str:
    """
    Heuristic language detection for English vs. French (Canadian context).
    For production use, swap with ``langdetect`` or ``lingua``.
    """
    french_markers = {
        "le", "la", "les", "de", "du", "des", "un", "une",
        "est", "sont", "avec", "pour", "dans", "sur", "qui",
        "que", "elle", "nous", "vous", "ils", "leur",
    }
    tokens = set(re.findall(r"\b[a-zéàèùâêîôûëïüç]+\b", text.lower()))
    overlap = tokens & french_markers
    return "fr" if len(overlap) >= 2 else "en"


# ---------------------------------------------------------------------------
# Comment cleaner
# ---------------------------------------------------------------------------
class CommentCleaner:
    """Clean and normalise a raw comments DataFrame to the unified schema."""

    def __init__(self, min_chars: int = 5, dedup: bool = True):
        self.min_chars = min_chars
        self.dedup = dedup

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        logger.info(f"Cleaning {len(df):,} raw comments…")
        df = df.copy()

        # ── Rename to unified schema if platform columns differ ──────────
        df = self._normalise_columns(df)

        # ── Preserve raw text ────────────────────────────────────────────
        df["text_raw"] = df["text"].astype(str)
        df["text_clean"] = df["text_raw"].apply(clean_text)

        # ── Drop short / empty comments ──────────────────────────────────
        before = len(df)
        df = df[df["text_clean"].str.len() >= self.min_chars].copy()
        logger.info(f"  Dropped {before - len(df):,} short/empty comments.")

        # ── Deduplicate on (video_id, text_clean) ────────────────────────
        if self.dedup:
            before = len(df)
            df = df.drop_duplicates(subset=["video_id", "text_clean"])
            logger.info(f"  Dropped {before - len(df):,} duplicate comments.")

        # ── Language detection ───────────────────────────────────────────
        df["language_detected"] = df["text_raw"].apply(detect_language_simple)

        # ── Numeric coercions ────────────────────────────────────────────
        for col in ["like_count", "reply_count"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
            else:
                df[col] = 0

        # ── Datetime coercions ───────────────────────────────────────────
        for col in ["published_at", "extracted_at"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

        # ── Select and order output columns ──────────────────────────────
        out_cols = [c for c in COMMENT_SCHEMA if c in df.columns]
        df = df[out_cols]
        logger.info(f"  Final comment count: {len(df):,}")
        return df.reset_index(drop=True)

    @staticmethod
    def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Map platform-specific column names to unified schema."""
        rename_map = {
            "body": "text",
            "content": "text",
            "message": "text",
            "likes": "like_count",
            "replies": "reply_count",
            "created_at": "published_at",
            "timestamp": "published_at",
        }
        return df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})


# ---------------------------------------------------------------------------
# Video metadata cleaner
# ---------------------------------------------------------------------------
class VideoMetadataCleaner:
    """Clean and normalise raw video metadata to the unified schema."""

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        logger.info(f"Cleaning {len(df):,} video records…")
        df = df.copy()

        # Fill missing numeric fields with 0
        for col in ["view_count", "like_count", "comment_count", "duration_seconds"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")

        # Boolean is_short (≤ 60 s)
        if "duration_seconds" in df.columns:
            df["is_short"] = df["duration_seconds"] <= 60

        # Datetime fields
        for col in ["published_at", "extracted_at"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

        # Drop exact duplicates
        before = len(df)
        df = df.drop_duplicates(subset=["video_id"])
        logger.info(f"  Dropped {before - len(df):,} duplicate video records.")

        # Clean title and description whitespace
        for col in ["title", "description"]:
            if col in df.columns:
                df[col] = df[col].fillna("").str.strip()

        out_cols = [c for c in VIDEO_SCHEMA if c in df.columns]
        df = df[out_cols]
        logger.info(f"  Final video count: {len(df):,}")
        return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Engagement metrics
# ---------------------------------------------------------------------------
def add_engagement_metrics(videos_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute normalised engagement ratios useful for auditing algorithmic reach.

    Metrics added
    -------------
    engagement_rate : likes per 1 000 views
    comment_rate    : comments per 1 000 views
    like_to_comment : ratio of likes to comments (interaction balance)
    """
    df = videos_df.copy()
    views = df["view_count"].replace(0, np.nan)
    df["engagement_rate"] = (df["like_count"] / views * 1_000).round(4)
    df["comment_rate"] = (df["comment_count"] / views * 1_000).round(4)
    df["like_to_comment"] = (
        df["like_count"] / df["comment_count"].replace(0, np.nan)
    ).round(4)
    return df


# ---------------------------------------------------------------------------
# Civic keyword tagger
# ---------------------------------------------------------------------------
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


def tag_civic_keywords(df: pd.DataFrame, text_col: str = "text_clean") -> pd.DataFrame:
    """
    Flag comments that contain keywords from each civic category.

    Adds boolean columns: ``kw_policy``, ``kw_identity``, ``kw_sentiment_signal``.
    Useful for downstream topic-stratified sentiment analysis.
    """
    df = df.copy()
    for group, keywords in CIVIC_KEYWORD_GROUPS.items():
        pattern = r"\b(" + "|".join(keywords) + r")\b"
        df[f"kw_{group}"] = df[text_col].str.contains(pattern, case=False, na=False, regex=True)
    return df
