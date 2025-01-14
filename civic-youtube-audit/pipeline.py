"""
pipeline.py
-----------
End-to-end orchestrator for the Canadian Civic YouTube Audit pipeline.

Usage
-----
# Full audit (requires YOUTUBE_API_KEY env var):
    python pipeline.py --channels @ExampleChannel1 @ExampleChannel2

# Demo mode (no API key needed — uses synthetic data):
    python pipeline.py --demo

Author: Kody
Project: Canadian Civic Influence Project — Algorithm Audit Pipeline
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from cleaning.cleaner import CommentCleaner, VideoMetadataCleaner, add_engagement_metrics
from sentiment.analyzer import SentimentPipeline, sentiment_summary
from visualization.dashboard import render_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock data generator (demo mode)
# ---------------------------------------------------------------------------
def generate_mock_data(
    n_videos: int = 80,
    n_comments: int = 2000,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Synthesise realistic-looking video metadata and comments for pipeline demos.

    Simulates two fictional civic creators:
      - @PolicyPulse      (policy-focused, Anglophone)
      - @CiviqueMontréal  (civic-focused, Francophone-leaning)
    """
    rng = np.random.default_rng(seed)
    now = datetime.now(timezone.utc)

    channels = {
        "@PolicyPulse": ("UC_policy_001", "PolicyPulse"),
        "@CiviqueMontréal": ("UC_civique_002", "CiviqueMontréal"),
    }

    civic_titles_en = [
        "Breaking Down the Federal Budget 2025",
        "Climate Policy: What Ottawa Got Wrong",
        "Healthcare Reform Explained in 5 Minutes",
        "The Housing Crisis: Who's Really To Blame?",
        "Understanding Indigenous Land Rights",
        "Election 2025: Platform Comparison",
        "Immigration Policy Deep Dive",
        "Carbon Tax: Pros, Cons, and Myths",
        "Why Young Canadians Are Disengaged From Politics",
        "Free Speech Debate on Campus",
    ]

    civic_titles_fr = [
        "Budget fédéral 2025 : ce qu'il faut retenir",
        "La crise du logement à Montréal expliquée",
        "Droits linguistiques : où en est-on?",
        "Réforme de la santé : vrai ou faux?",
        "Élections 2025 : analyse des plateformes",
        "Comprendre la politique climatique canadienne",
        "Jeunesse et engagement politique",
        "La loi 101 et son avenir",
        "Décryptage du système électoral",
        "Souveraineté et fédéralisme en 2025",
    ]

    comment_templates_positive = [
        "This is such an important topic, thank you for covering it!",
        "Finally someone explaining this clearly. Subscribed!",
        "Great analysis, very informative and balanced.",
        "I learned so much from this video, keep it up!",
        "Exactly what I needed to understand the issue.",
        "Très bon contenu, merci pour l'analyse!",
        "Excellent travail, très équilibré.",
        "Merci de couvrir ces sujets importants.",
    ]

    comment_templates_negative = [
        "This is completely biased, I can't believe this.",
        "You clearly don't understand how policy works.",
        "This is propaganda, plain and simple.",
        "Terrible take, you missed the entire point.",
        "Stop spreading misinformation!",
        "Contenu très partial et inexact.",
        "C'est n'importe quoi, aucune rigueur.",
    ]

    comment_templates_neutral = [
        "Interesting perspective, but I'd like to see more data.",
        "Can you do a follow-up on the economic impact?",
        "What about the provincial angle?",
        "Good overview but you skipped the Indigenous perspective.",
        "I wonder what the polling numbers say about this.",
        "Bonne vidéo, mais manque de sources.",
        "Et le point de vue des provinces?",
        "À voir, j'attends la suite.",
    ]

    # Build videos
    video_records = []
    all_titles = civic_titles_en + civic_titles_fr
    for i in range(n_videos):
        channel_handle = rng.choice(list(channels.keys()))
        channel_id, channel_title = channels[channel_handle]
        title_pool = civic_titles_fr if "ivique" in channel_title else civic_titles_en
        title = rng.choice(title_pool) + f" [{i}]"
        published = now - timedelta(days=int(rng.integers(1, 365)))
        duration = int(rng.integers(30, 1800))
        views = int(rng.integers(500, 500_000))
        video_records.append(
            {
                "video_id": f"vid_{i:04d}",
                "channel_id": channel_id,
                "channel_title": channel_title,
                "platform": "youtube",
                "title": title,
                "description": f"In this video we discuss: {title.lower()}",
                "language": "fr" if "ivique" in channel_title else "en",
                "published_at": published,
                "view_count": views,
                "like_count": int(views * rng.uniform(0.01, 0.08)),
                "comment_count": int(views * rng.uniform(0.002, 0.015)),
                "duration_seconds": duration,
                "is_short": duration <= 60,
                "extracted_at": now,
            }
        )

    videos_df = pd.DataFrame(video_records)

    # Build comments
    comment_records = []
    sentiment_weights = [0.40, 0.35, 0.25]  # pos / neu / neg
    for j in range(n_comments):
        video = videos_df.iloc[rng.integers(0, len(videos_df))]
        sentiment_bucket = rng.choice(["positive", "neutral", "negative"], p=sentiment_weights)
        templates = {
            "positive": comment_templates_positive,
            "neutral": comment_templates_neutral,
            "negative": comment_templates_negative,
        }[sentiment_bucket]
        comment_records.append(
            {
                "comment_id": f"cmt_{j:05d}",
                "video_id": video["video_id"],
                "channel_title": video["channel_title"],
                "platform": "youtube",
                "text": rng.choice(templates),
                "like_count": int(rng.integers(0, 150)),
                "reply_count": int(rng.integers(0, 20)),
                "published_at": video["published_at"] + timedelta(hours=int(rng.integers(0, 72))),
                "extracted_at": now,
            }
        )

    comments_df = pd.DataFrame(comment_records)
    logger.info(f"Mock data: {len(videos_df)} videos, {len(comments_df)} comments generated.")
    return videos_df, comments_df


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------
def run_pipeline(
    videos_df: pd.DataFrame,
    comments_df: pd.DataFrame,
    output_dir: str = "outputs",
    use_transformer: bool = False,
) -> dict:
    """
    Execute cleaning → sentiment → visualisation on pre-loaded DataFrames.

    Parameters
    ----------
    use_transformer : bool
        Set True if transformers/torch are installed for higher-accuracy scoring.
    """
    os.makedirs(output_dir, exist_ok=True)
    results = {}

    # ── Step 1: Clean ────────────────────────────────────────────────────
    logger.info("=== STEP 1: Data Cleaning ===")
    video_cleaner = VideoMetadataCleaner()
    comment_cleaner = CommentCleaner(min_chars=5, dedup=True)
    videos_clean = video_cleaner.clean(videos_df)
    comments_clean = comment_cleaner.clean(comments_df)
    videos_clean = add_engagement_metrics(videos_clean)

    # Save cleaned data
    videos_clean.to_parquet(f"{output_dir}/videos_clean.parquet", index=False)
    comments_clean.to_parquet(f"{output_dir}/comments_clean.parquet", index=False)
    logger.info("Cleaned data saved.")

    # ── Step 2: Sentiment ────────────────────────────────────────────────
    logger.info("=== STEP 2: Sentiment Analysis ===")
    pipe = SentimentPipeline(use_transformer=use_transformer)
    comments_scored = pipe.run(comments_clean, text_col="text_clean")
    comments_scored.to_parquet(f"{output_dir}/comments_scored.parquet", index=False)

    # Merge avg sentiment back to videos
    vid_sentiment = (
        comments_scored.groupby("video_id")["vader_compound"]
        .mean()
        .reset_index()
        .rename(columns={"vader_compound": "avg_sentiment"})
    )
    videos_enriched = videos_clean.merge(vid_sentiment, on="video_id", how="left")
    videos_enriched.to_parquet(f"{output_dir}/videos_enriched.parquet", index=False)

    # Summary stats
    summary = sentiment_summary(comments_scored, group_by=["channel_title"])
    summary.to_csv(f"{output_dir}/sentiment_summary.csv", index=False)
    logger.info(f"\nSentiment Summary:\n{summary.to_string(index=False)}")
    results["sentiment_summary"] = summary

    # ── Step 3: Visualise ────────────────────────────────────────────────
    logger.info("=== STEP 3: Visualisation ===")
    figures = render_all(videos_enriched, comments_scored, output_dir=output_dir)
    results["figures"] = figures

    logger.info(f"\nPipeline complete. All outputs written to: {output_dir}/")
    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Canadian Civic YouTube Audit Pipeline"
    )
    parser.add_argument(
        "--channels",
        nargs="+",
        metavar="HANDLE",
        help="YouTube channel handles to audit (e.g. @PolicyPulse)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with synthetic mock data (no API key required)",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=100,
        help="Max videos to pull per channel (default: 100)",
    )
    parser.add_argument(
        "--max-comments",
        type=int,
        default=200,
        help="Max comments per video (default: 200)",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory to save all outputs (default: outputs/)",
    )
    parser.add_argument(
        "--transformer",
        action="store_true",
        help="Enable transformer-based sentiment (requires transformers + torch)",
    )
    args = parser.parse_args()

    if args.demo:
        logger.info("Running in DEMO mode with synthetic data.")
        videos_df, comments_df = generate_mock_data()
    elif args.channels:
        from etl.youtube_client import YouTubeClient

        client = YouTubeClient()
        all_videos, all_comments = [], []
        for handle in args.channels:
            v, c = client.audit_channel(
                handle,
                max_videos=args.max_videos,
                max_comments_per_video=args.max_comments,
                output_dir="data/raw",
            )
            all_videos.append(v)
            all_comments.append(c)
        videos_df = pd.concat(all_videos, ignore_index=True)
        comments_df = pd.concat(all_comments, ignore_index=True)
    else:
        parser.print_help()
        sys.exit(1)

    run_pipeline(
        videos_df,
        comments_df,
        output_dir=args.output_dir,
        use_transformer=args.transformer,
    )


if __name__ == "__main__":
    main()
