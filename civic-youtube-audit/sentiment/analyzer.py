"""
sentiment/analyzer.py
----------------------
Multi-model sentiment analysis pipeline for civic discourse comments.

Implements two complementary approaches:
  1. VADER     — lexicon-based, fast, ideal for social media text
  2. Transformer — fine-tuned DistilBERT (cardiffnlp/twitter-roberta-base-sentiment)
                  for higher accuracy on short-form platform content

Both scores are stored so downstream analysis can compare or ensemble them.

Author: Kody
Project: Canadian Civic Influence Project — Algorithm Audit Pipeline
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class SentimentResult:
    text: str
    vader_neg: float = 0.0
    vader_neu: float = 0.0
    vader_pos: float = 0.0
    vader_compound: float = 0.0
    vader_label: str = "neutral"
    transformer_label: Optional[str] = None
    transformer_score: Optional[float] = None
    ensemble_label: Optional[str] = None


VADER_THRESHOLDS = {"positive": 0.05, "negative": -0.05}


def _vader_label(compound: float) -> str:
    if compound >= VADER_THRESHOLDS["positive"]:
        return "positive"
    if compound <= VADER_THRESHOLDS["negative"]:
        return "negative"
    return "neutral"


# ---------------------------------------------------------------------------
# VADER analyser
# ---------------------------------------------------------------------------
class VADERSentimentAnalyzer:
    """Lexicon-based sentiment using VADER. No GPU required."""

    def __init__(self):
        self._analyzer = SentimentIntensityAnalyzer()

    def score(self, text: str) -> SentimentResult:
        scores = self._analyzer.polarity_scores(text)
        return SentimentResult(
            text=text,
            vader_neg=round(scores["neg"], 4),
            vader_neu=round(scores["neu"], 4),
            vader_pos=round(scores["pos"], 4),
            vader_compound=round(scores["compound"], 4),
            vader_label=_vader_label(scores["compound"]),
        )

    def score_batch(self, texts: list[str]) -> list[SentimentResult]:
        return [self.score(t) for t in texts]


# ---------------------------------------------------------------------------
# Transformer-based analyser (optional — requires transformers + torch)
# ---------------------------------------------------------------------------
class TransformerSentimentAnalyzer:
    """
    HuggingFace pipeline wrapper using a Twitter/social-media fine-tuned model.

    Model: cardiffnlp/twitter-roberta-base-sentiment-latest
    Falls back gracefully if transformers is not installed.

    Parameters
    ----------
    model_name : str
        Any HuggingFace sentiment model identifier.
    batch_size : int
        Batch size for GPU/CPU inference. Reduce if OOM.
    device : int
        -1 for CPU, 0 for first CUDA GPU.
    """

    MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
    LABEL_MAP = {"negative": "negative", "neutral": "neutral", "positive": "positive"}

    def __init__(
        self,
        model_name: str = MODEL,
        batch_size: int = 32,
        device: int = -1,
        max_length: int = 128,
    ):
        try:
            from transformers import pipeline as hf_pipeline

            self._pipe = hf_pipeline(
                "sentiment-analysis",
                model=model_name,
                tokenizer=model_name,
                device=device,
                max_length=max_length,
                truncation=True,
                batch_size=batch_size,
            )
            self._available = True
            logger.info(f"Transformer model loaded: {model_name}")
        except ImportError:
            logger.warning(
                "transformers/torch not installed. Transformer sentiment unavailable."
            )
            self._available = False

    def score_batch(self, texts: list[str]) -> list[dict]:
        if not self._available:
            return [{"label": None, "score": None}] * len(texts)
        results = self._pipe(texts)
        return [
            {
                "label": self.LABEL_MAP.get(r["label"].lower(), r["label"].lower()),
                "score": round(r["score"], 4),
            }
            for r in results
        ]

    @property
    def available(self) -> bool:
        return self._available


# ---------------------------------------------------------------------------
# Ensemble pipeline
# ---------------------------------------------------------------------------
class SentimentPipeline:
    """
    Orchestrates VADER + (optionally) transformer sentiment scoring
    on a comments DataFrame.

    Ensemble strategy
    -----------------
    If both models are available, the ensemble label is determined by:
      - Agreement → that label
      - Disagreement → trust transformer if score > 0.70, else VADER
    """

    def __init__(
        self,
        use_transformer: bool = True,
        transformer_kwargs: Optional[dict] = None,
    ):
        self.vader = VADERSentimentAnalyzer()
        self.transformer = (
            TransformerSentimentAnalyzer(**(transformer_kwargs or {}))
            if use_transformer
            else None
        )

    def run(self, df: pd.DataFrame, text_col: str = "text_clean") -> pd.DataFrame:
        """
        Score all rows in ``df[text_col]`` and append sentiment columns.

        New columns added
        -----------------
        vader_compound, vader_label,
        transformer_label, transformer_score,
        ensemble_label, sentiment_confidence
        """
        texts = df[text_col].fillna("").tolist()
        df = df.copy()

        # ── VADER ────────────────────────────────────────────────────────
        logger.info("Running VADER scoring…")
        vader_results = self.vader.score_batch(texts)
        df["vader_compound"] = [r.vader_compound for r in vader_results]
        df["vader_pos"] = [r.vader_pos for r in vader_results]
        df["vader_neg"] = [r.vader_neg for r in vader_results]
        df["vader_label"] = [r.vader_label for r in vader_results]

        # ── Transformer ──────────────────────────────────────────────────
        if self.transformer and self.transformer.available:
            logger.info("Running transformer scoring…")
            tf_results = self.transformer.score_batch(texts)
            df["transformer_label"] = [r["label"] for r in tf_results]
            df["transformer_score"] = [r["score"] for r in tf_results]
            df["ensemble_label"] = df.apply(self._ensemble_row, axis=1)
            df["sentiment_confidence"] = df["transformer_score"]
        else:
            df["transformer_label"] = None
            df["transformer_score"] = None
            df["ensemble_label"] = df["vader_label"]
            # Confidence proxy: |compound| mapped to [0,1]
            df["sentiment_confidence"] = df["vader_compound"].abs()

        logger.info("Sentiment scoring complete.")
        return df

    @staticmethod
    def _ensemble_row(row: pd.Series) -> str:
        v_label = row["vader_label"]
        t_label = row["transformer_label"]
        t_score = row["transformer_score"] or 0.0

        if v_label == t_label:
            return v_label
        # Disagree — trust transformer if confident
        return t_label if t_score >= 0.70 else v_label


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------
def sentiment_summary(df: pd.DataFrame, group_by: Optional[list[str]] = None) -> pd.DataFrame:
    """
    Aggregate sentiment scores by optional grouping columns (e.g. channel, date).

    Returns a summary DataFrame with:
      mean/std compound score, label distribution (%), total comments.
    """
    if group_by:
        g = df.groupby(group_by)
    else:
        g = df.groupby(lambda _: "all")

    summary = g.agg(
        total_comments=("vader_compound", "count"),
        mean_compound=("vader_compound", "mean"),
        std_compound=("vader_compound", "std"),
        positive_pct=("ensemble_label", lambda x: (x == "positive").mean() * 100),
        neutral_pct=("ensemble_label", lambda x: (x == "neutral").mean() * 100),
        negative_pct=("ensemble_label", lambda x: (x == "negative").mean() * 100),
    ).round(4)

    return summary.reset_index()


def top_comments(
    df: pd.DataFrame,
    label: str = "positive",
    n: int = 10,
    score_col: str = "vader_compound",
) -> pd.DataFrame:
    """Return the N most extreme comments for a given sentiment label."""
    subset = df[df["ensemble_label"] == label].copy()
    ascending = label == "negative"
    return subset.nsmallest(n, score_col) if ascending else subset.nlargest(n, score_col)


# ---------------------------------------------------------------------------
# Language-stratified summary (EN vs. FR)
# ---------------------------------------------------------------------------
def sentiment_by_language(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sentiment summary stratified by channel and detected language.

    Convenience wrapper around sentiment_summary() for the Canadian
    bilingual civic context — produces EN vs. FR breakdowns per channel
    in a single call.

    Returns
    -------
    DataFrame with columns: channel_title, language_detected,
    total_comments, mean_compound, std_compound,
    positive_pct, neutral_pct, negative_pct.
    """
    if "language_detected" not in df.columns:
        raise ValueError(
            "language_detected column missing. Run CommentCleaner.clean() first."
        )
    return sentiment_summary(df, group_by=["channel_title", "language_detected"])
