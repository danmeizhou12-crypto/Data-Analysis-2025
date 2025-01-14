"""
visualization/dashboard.py
---------------------------
Plotly-based visualizations for the civic algorithm audit pipeline.

Produces six publication-ready figures:
  1. sentiment_over_time    — rolling mean compound score per channel
  2. label_distribution     — stacked bar of pos/neu/neg % per channel
  3. engagement_vs_sentiment — scatter: engagement rate vs. avg. sentiment
  4. comment_volume_heatmap — weekly comment activity heatmap
  5. top_terms_by_sentiment  — horizontal bar of most frequent terms per label
  6. language_breakdown      — Anglophone vs. Francophone comment split

Author: Kody
Project: Canadian Civic Influence Project — Algorithm Audit Pipeline
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared style
# ---------------------------------------------------------------------------
PALETTE = {
    "positive": "#2ecc71",
    "neutral": "#95a5a6",
    "negative": "#e74c3c",
    "accent": "#2c3e50",
    "bg": "#f8f9fa",
}

LAYOUT_BASE = dict(
    font=dict(family="Inter, Arial, sans-serif", size=13, color="#2c3e50"),
    paper_bgcolor="white",
    plot_bgcolor=PALETTE["bg"],
    margin=dict(l=60, r=40, t=70, b=60),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


def _save(fig: go.Figure, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(path)
    logger.info(f"Saved → {path}")


# ---------------------------------------------------------------------------
# 1. Sentiment over time
# ---------------------------------------------------------------------------
def plot_sentiment_over_time(
    comments_df: pd.DataFrame,
    channel_col: str = "channel_title",
    window: int = 7,
    output_path: str = "outputs/sentiment_over_time.html",
) -> go.Figure:
    """
    Rolling-average VADER compound score per channel over publication date.
    Useful for detecting shifts in audience tone around political events.
    """
    df = comments_df.copy()
    df["date"] = pd.to_datetime(df["published_at"]).dt.date

    daily = (
        df.groupby([channel_col, "date"])["vader_compound"]
        .mean()
        .reset_index()
        .sort_values("date")
    )
    daily[f"rolling_{window}d"] = (
        daily.groupby(channel_col)["vader_compound"]
        .transform(lambda x: x.rolling(window, min_periods=1).mean())
    )

    fig = px.line(
        daily,
        x="date",
        y=f"rolling_{window}d",
        color=channel_col,
        labels={
            f"rolling_{window}d": f"{window}-day Rolling Avg. Sentiment",
            "date": "Comment Date",
        },
        title=f"Audience Sentiment Over Time ({window}-day Rolling Average)",
    )
    fig.add_hline(y=0, line_dash="dash", line_color="grey", opacity=0.5)
    fig.update_layout(**LAYOUT_BASE)
    _save(fig, output_path)
    return fig


# ---------------------------------------------------------------------------
# 2. Sentiment label distribution
# ---------------------------------------------------------------------------
def plot_label_distribution(
    comments_df: pd.DataFrame,
    channel_col: str = "channel_title",
    output_path: str = "outputs/label_distribution.html",
) -> go.Figure:
    """Stacked 100% bar showing pos/neu/neg proportion per channel."""
    counts = (
        comments_df.groupby([channel_col, "ensemble_label"])
        .size()
        .reset_index(name="count")
    )
    totals = counts.groupby(channel_col)["count"].transform("sum")
    counts["pct"] = (counts["count"] / totals * 100).round(2)

    fig = px.bar(
        counts,
        x=channel_col,
        y="pct",
        color="ensemble_label",
        color_discrete_map=PALETTE,
        barmode="stack",
        title="Sentiment Label Distribution by Channel",
        labels={"pct": "Percentage (%)", channel_col: "Channel"},
        text="pct",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="inside")
    fig.update_layout(**LAYOUT_BASE)
    _save(fig, output_path)
    return fig


# ---------------------------------------------------------------------------
# 3. Engagement vs. sentiment scatter
# ---------------------------------------------------------------------------
def plot_engagement_vs_sentiment(
    videos_df: pd.DataFrame,
    output_path: str = "outputs/engagement_vs_sentiment.html",
) -> go.Figure:
    """
    Scatter plot of video-level engagement rate vs. average comment sentiment.
    Bubble size = view count. Reveals whether provocative content drives reach.
    """
    df = videos_df.dropna(subset=["engagement_rate", "avg_sentiment"]).copy()

    fig = px.scatter(
        df,
        x="avg_sentiment",
        y="engagement_rate",
        size="view_count",
        color="channel_title",
        hover_name="title",
        hover_data={"view_count": True, "like_count": True},
        title="Engagement Rate vs. Average Audience Sentiment",
        labels={
            "avg_sentiment": "Avg. Comment Sentiment (VADER Compound)",
            "engagement_rate": "Engagement Rate (likes per 1k views)",
        },
        size_max=40,
    )
    fig.add_vline(x=0, line_dash="dash", line_color="grey", opacity=0.5)
    fig.update_layout(**LAYOUT_BASE)
    _save(fig, output_path)
    return fig


# ---------------------------------------------------------------------------
# 4. Comment volume heatmap (day-of-week × hour)
# ---------------------------------------------------------------------------
def plot_comment_volume_heatmap(
    comments_df: pd.DataFrame,
    channel_col: str = "channel_title",
    output_path: str = "outputs/comment_volume_heatmap.html",
) -> go.Figure:
    """
    Heatmap of comment activity by day-of-week and hour-of-day.
    Reveals when civic audiences are most active.
    """
    df = comments_df.copy()
    df["hour"] = pd.to_datetime(df["published_at"]).dt.hour
    df["day_name"] = pd.to_datetime(df["published_at"]).dt.day_name()
    df["day_num"] = pd.to_datetime(df["published_at"]).dt.dayofweek

    pivot = (
        df.groupby(["day_num", "day_name", "hour"])
        .size()
        .reset_index(name="count")
        .sort_values("day_num")
    )
    heat = pivot.pivot_table(index="day_name", columns="hour", values="count", fill_value=0)
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    heat = heat.reindex([d for d in day_order if d in heat.index])

    fig = px.imshow(
        heat,
        color_continuous_scale="Blues",
        title="Comment Activity Heatmap (Day × Hour UTC)",
        labels=dict(x="Hour of Day (UTC)", y="Day of Week", color="# Comments"),
        aspect="auto",
    )
    fig.update_layout(**LAYOUT_BASE)
    _save(fig, output_path)
    return fig


# ---------------------------------------------------------------------------
# 5. Top terms by sentiment label
# ---------------------------------------------------------------------------
def plot_top_terms(
    comments_df: pd.DataFrame,
    n_terms: int = 15,
    output_path: str = "outputs/top_terms.html",
) -> go.Figure:
    """
    Horizontal bar chart of the most frequent non-stopword tokens
    split by sentiment label. Surfaces civic framing vocabulary.
    """
    from collections import Counter
    import re

    STOP_WORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at",
        "to", "for", "of", "is", "it", "this", "that", "with",
        "her", "his", "my", "your", "we", "i", "you", "he", "she",
        "they", "are", "be", "was", "have", "has", "do", "not",
        "so", "if", "as", "by", "from", "im", "its", "just",
    }

    def top_tokens(texts: pd.Series) -> list[tuple[str, int]]:
        tokens = re.findall(r"\b[a-z]{3,}\b", " ".join(texts.dropna()))
        filtered = [t for t in tokens if t not in STOP_WORDS]
        return Counter(filtered).most_common(n_terms)

    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=["Positive Comments", "Neutral Comments", "Negative Comments"],
        shared_xaxes=False,
    )

    label_col_map = {"positive": 1, "neutral": 2, "negative": 3}
    colors = {"positive": PALETTE["positive"], "neutral": PALETTE["neutral"], "negative": PALETTE["negative"]}

    for label, col in label_col_map.items():
        subset = comments_df[comments_df["ensemble_label"] == label]["text_clean"]
        tokens = top_tokens(subset)
        if not tokens:
            continue
        words, counts = zip(*tokens)
        fig.add_trace(
            go.Bar(
                x=list(counts),
                y=list(words),
                orientation="h",
                marker_color=colors[label],
                name=label.capitalize(),
                showlegend=(col == 1),
            ),
            row=1, col=col,
        )

    fig.update_layout(
        title_text="Top Terms by Sentiment Label",
        **LAYOUT_BASE,
    )
    fig.update_yaxes(autorange="reversed")
    _save(fig, output_path)
    return fig


# ---------------------------------------------------------------------------
# 6. Language breakdown
# ---------------------------------------------------------------------------
def plot_language_breakdown(
    comments_df: pd.DataFrame,
    channel_col: str = "channel_title",
    output_path: str = "outputs/language_breakdown.html",
) -> go.Figure:
    """
    Grouped bar showing English vs. French comment proportions per channel.
    Key for the Canadian civic framing analysis.
    """
    counts = (
        comments_df.groupby([channel_col, "language_detected"])
        .size()
        .reset_index(name="count")
    )
    totals = counts.groupby(channel_col)["count"].transform("sum")
    counts["pct"] = (counts["count"] / totals * 100).round(2)

    fig = px.bar(
        counts,
        x=channel_col,
        y="pct",
        color="language_detected",
        barmode="group",
        title="Language Distribution by Channel (EN vs. FR)",
        labels={"pct": "Percentage (%)", channel_col: "Channel", "language_detected": "Language"},
        color_discrete_map={"en": "#3498db", "fr": "#e67e22"},
        text="pct",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(**LAYOUT_BASE)
    _save(fig, output_path)
    return fig


# ---------------------------------------------------------------------------
# Master render function
# ---------------------------------------------------------------------------
def render_all(
    videos_df: pd.DataFrame,
    comments_df: pd.DataFrame,
    output_dir: str = "outputs",
) -> dict[str, go.Figure]:
    """Render all six dashboard figures and return them in a dict."""
    figures = {}
    figures["sentiment_over_time"] = plot_sentiment_over_time(
        comments_df, output_path=f"{output_dir}/sentiment_over_time.html"
    )
    figures["label_distribution"] = plot_label_distribution(
        comments_df, output_path=f"{output_dir}/label_distribution.html"
    )
    if "avg_sentiment" in videos_df.columns and "engagement_rate" in videos_df.columns:
        figures["engagement_vs_sentiment"] = plot_engagement_vs_sentiment(
            videos_df, output_path=f"{output_dir}/engagement_vs_sentiment.html"
        )
    figures["comment_volume_heatmap"] = plot_comment_volume_heatmap(
        comments_df, output_path=f"{output_dir}/comment_volume_heatmap.html"
    )
    figures["top_terms"] = plot_top_terms(
        comments_df, output_path=f"{output_dir}/top_terms.html"
    )
    figures["language_breakdown"] = plot_language_breakdown(
        comments_df, output_path=f"{output_dir}/language_breakdown.html"
    )
    logger.info(f"All figures saved to {output_dir}/")
    return figures
