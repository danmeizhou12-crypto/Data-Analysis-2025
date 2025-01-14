"""
etl/youtube_client.py
---------------------
YouTube Data API v3 client for extracting video metadata and comments.
Supports both long-form videos and Shorts. Outputs unified JSON/Parquet schema.

Author: Kody
Project: Canadian Civic Influence Project — Algorithm Audit Pipeline
"""

import os
import time
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
YOUTUBE_API_SERVICE = "youtube"
YOUTUBE_API_VERSION = "v3"
MAX_RESULTS_PER_PAGE = 100
COMMENT_MAX_RESULTS = 100
QUOTA_SLEEP_SECONDS = 2  # courtesy sleep between paginated requests


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class YouTubeClient:
    """
    Thin wrapper around the YouTube Data API v3.

    Parameters
    ----------
    api_key : str
        YouTube Data API key. Falls back to env var ``YOUTUBE_API_KEY``.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "YouTube API key required. Set YOUTUBE_API_KEY env var or pass api_key=."
            )
        self.youtube = build(
            YOUTUBE_API_SERVICE,
            YOUTUBE_API_VERSION,
            developerKey=self.api_key,
        )
        logger.info("YouTube API client initialised.")

    # ------------------------------------------------------------------
    # Channel helpers
    # ------------------------------------------------------------------
    def get_channel_id(self, handle: str) -> str:
        """Resolve a @handle or username to a channel ID."""
        resp = (
            self.youtube.search()
            .list(q=handle, type="channel", part="id", maxResults=1)
            .execute()
        )
        items = resp.get("items", [])
        if not items:
            raise ValueError(f"No channel found for handle: {handle}")
        return items[0]["id"]["channelId"]

    def get_uploads_playlist_id(self, channel_id: str) -> str:
        """Return the hidden 'uploads' playlist ID for a channel."""
        resp = (
            self.youtube.channels()
            .list(id=channel_id, part="contentDetails")
            .execute()
        )
        return resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # ------------------------------------------------------------------
    # Video metadata
    # ------------------------------------------------------------------
    def get_video_ids(self, playlist_id: str, max_videos: int = 200) -> list[str]:
        """Paginate through an uploads playlist and collect video IDs."""
        video_ids, page_token = [], None
        while len(video_ids) < max_videos:
            resp = (
                self.youtube.playlistItems()
                .list(
                    playlistId=playlist_id,
                    part="contentDetails",
                    maxResults=min(MAX_RESULTS_PER_PAGE, max_videos - len(video_ids)),
                    pageToken=page_token,
                )
                .execute()
            )
            video_ids.extend(
                item["contentDetails"]["videoId"] for item in resp.get("items", [])
            )
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
            time.sleep(QUOTA_SLEEP_SECONDS)
        return video_ids

    def get_video_metadata(self, video_ids: list[str]) -> pd.DataFrame:
        """
        Batch-fetch metadata for up to 50 video IDs per request.

        Returns a DataFrame with a unified schema (see ``_parse_video``).
        """
        records = []
        for chunk_start in range(0, len(video_ids), 50):
            chunk = video_ids[chunk_start : chunk_start + 50]
            resp = (
                self.youtube.videos()
                .list(
                    id=",".join(chunk),
                    part="snippet,statistics,contentDetails",
                )
                .execute()
            )
            records.extend(self._parse_video(item) for item in resp.get("items", []))
            time.sleep(QUOTA_SLEEP_SECONDS)

        df = pd.DataFrame(records)
        df["is_short"] = df["duration_seconds"] <= 60
        df["published_at"] = pd.to_datetime(df["published_at"], utc=True)
        return df

    @staticmethod
    def _parse_video(item: dict) -> dict:
        snip = item["snippet"]
        stats = item.get("statistics", {})
        details = item.get("contentDetails", {})
        return {
            "video_id": item["id"],
            "title": snip.get("title"),
            "channel_id": snip.get("channelId"),
            "channel_title": snip.get("channelTitle"),
            "published_at": snip.get("publishedAt"),
            "description": snip.get("description", "")[:500],  # truncate
            "tags": "|".join(snip.get("tags", [])),
            "category_id": snip.get("categoryId"),
            "language": snip.get("defaultAudioLanguage"),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "duration_iso": details.get("duration"),
            "duration_seconds": YouTubeClient._iso8601_to_seconds(
                details.get("duration", "PT0S")
            ),
            "platform": "youtube",
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _iso8601_to_seconds(iso: str) -> int:
        """Convert ISO 8601 duration (e.g. PT4M13S) to total seconds."""
        import re
        pattern = re.compile(
            r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", re.IGNORECASE
        )
        match = pattern.match(iso)
        if not match:
            return 0
        h, m, s = (int(x or 0) for x in match.groups())
        return h * 3600 + m * 60 + s

    # ------------------------------------------------------------------
    # Comment extraction
    # ------------------------------------------------------------------
    def get_comments(
        self,
        video_id: str,
        max_comments: int = 500,
        order: str = "relevance",
    ) -> pd.DataFrame:
        """
        Extract top-level comments for a video with pagination.

        Parameters
        ----------
        video_id : str
        max_comments : int
            Hard cap on comment records returned.
        order : str
            ``'relevance'`` or ``'time'``.
        """
        records, page_token = [], None
        try:
            while len(records) < max_comments:
                resp = (
                    self.youtube.commentThreads()
                    .list(
                        videoId=video_id,
                        part="snippet",
                        maxResults=min(COMMENT_MAX_RESULTS, max_comments - len(records)),
                        order=order,
                        pageToken=page_token,
                        textFormat="plainText",
                    )
                    .execute()
                )
                for thread in resp.get("items", []):
                    top = thread["snippet"]["topLevelComment"]["snippet"]
                    records.append(
                        {
                            "comment_id": thread["id"],
                            "video_id": video_id,
                            "author": top.get("authorDisplayName"),
                            "text": top.get("textDisplay", ""),
                            "like_count": top.get("likeCount", 0),
                            "reply_count": thread["snippet"].get("totalReplyCount", 0),
                            "published_at": top.get("publishedAt"),
                            "updated_at": top.get("updatedAt"),
                            "platform": "youtube",
                            "extracted_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
                time.sleep(QUOTA_SLEEP_SECONDS)

        except HttpError as exc:
            if exc.resp.status == 403:
                logger.warning(f"Comments disabled for video {video_id}. Skipping.")
            else:
                raise

        df = pd.DataFrame(records)
        if not df.empty:
            df["published_at"] = pd.to_datetime(df["published_at"], utc=True)
        return df

    # ------------------------------------------------------------------
    # High-level audit runner
    # ------------------------------------------------------------------
    def audit_channel(
        self,
        handle: str,
        max_videos: int = 100,
        max_comments_per_video: int = 200,
        output_dir: str = "data/raw",
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Full channel audit: metadata + comments → Parquet files.

        Returns
        -------
        videos_df, comments_df
        """
        logger.info(f"Starting audit for channel: {handle}")
        os.makedirs(output_dir, exist_ok=True)

        channel_id = self.get_channel_id(handle)
        playlist_id = self.get_uploads_playlist_id(channel_id)
        video_ids = self.get_video_ids(playlist_id, max_videos=max_videos)
        logger.info(f"Found {len(video_ids)} videos for {handle}.")

        videos_df = self.get_video_metadata(video_ids)

        all_comments = []
        for vid in video_ids:
            comments_df = self.get_comments(vid, max_comments=max_comments_per_video)
            all_comments.append(comments_df)
            logger.info(f"  {vid}: {len(comments_df)} comments extracted.")

        comments_df = pd.concat(all_comments, ignore_index=True) if all_comments else pd.DataFrame()

        # Save to Parquet (efficient columnar format)
        slug = handle.lstrip("@").replace(" ", "_").lower()
        videos_path = os.path.join(output_dir, f"{slug}_videos.parquet")
        comments_path = os.path.join(output_dir, f"{slug}_comments.parquet")
        videos_df.to_parquet(videos_path, index=False)
        comments_df.to_parquet(comments_path, index=False)
        logger.info(f"Saved → {videos_path}, {comments_path}")

        return videos_df, comments_df
