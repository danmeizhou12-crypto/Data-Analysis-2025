# ETL Module (`etl/youtube_client.py`)

## Overview

The ETL (Extract, Transform, Load) module handles all interaction with the YouTube Data API v3. It abstracts away authentication, pagination, quota management, and error handling so the rest of the pipeline can work with clean Parquet files.

---

## Architecture

```
┌────────────────────────────────────────────┐
│ YouTube Data API v3                        │
│ (public.youtube.com endpoints)             │
└────────────────────┬───────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ YouTubeClient        │ ← auth, pagination, quota handling
          │ (this module)        │
          └──────────────────────┘
               │           │
               ▼           ▼
        ┌────────────┐  ┌──────────────────┐
        │ Videos     │  │ Comments         │
        │ Metadata   │  │ (top-level only) │
        └────────────┘  └──────────────────┘
             │                  │
             └──────────┬───────┘
                        ▼
            ┌───────────────────────┐
            │ data/raw/             │
            │ (Parquet + CSV)       │
            └───────────────────────┘
```

---

## Key Classes

### `YouTubeClient`

**Purpose:** Authenticated wrapper around YouTube API v3.

**Initialization:**

```python
from etl.youtube_client import YouTubeClient

# Option 1: Pass API key directly
client = YouTubeClient(api_key="AIzaSyD...")

# Option 2: Via environment variable (preferred)
import os
os.environ["YOUTUBE_API_KEY"] = "AIzaSyD..."
client = YouTubeClient()  # auto-loads from env
```

**Quota Management:**

The YouTube Data API has a default quota of **10,000 units per day**. Each operation costs:

| Operation | Units | Calls for 100-video audit |
|---|---|---|
| `search.list` (resolve @handle) | 100 | 1 |
| `channels.list` (get playlist) | 1 | 1 |
| `playlistItems.list` (paginate videos) | 1 | 2–3 |
| `videos.list` (50 IDs/call) | 1 | 2 |
| `commentThreads.list` (per video) | 1 | 100–200 |
| **Total** | — | **300–400 units** |

**Throttling:** The client sleeps 2 seconds between paginated requests as a courtesy, preventing rate-limit errors.

---

### `RecommendationCrawler`

**Purpose:** Implement algorithmic bias detection by following recommendation chains.

**Use case:** YouTube's "Up Next" recommendations can vary based on simulated user persona. A policy-focused anglophone might get different recommendations than a general-interest francophone from the same seed video.

**Limitation:** Uses `search.list` with `relatedToVideoId`, which is a proxy for recommendations but not identical to the "Up Next" algorithm.

---

## Workflow

### Complete Audit Flow

```python
from etl.youtube_client import YouTubeClient

client = YouTubeClient(api_key="YOUR_KEY")

# Step 1: Resolve channel handle → channel ID
channel_id = client.get_channel_id("@PolicyPulse")

# Step 2: Get the uploads playlist (hidden, contains all videos)
uploads_id = client.get_uploads_playlist_id(channel_id)

# Step 3: Paginate playlist → get all video IDs
video_ids = client.get_video_ids(uploads_id, max_videos=100)
# Returns: ['vid_0001', 'vid_0002', ..., 'vid_0100']

# Step 4: Batch-fetch metadata for videos (50 per request)
videos_df = client.get_video_metadata(video_ids)
# DataFrame: 100 rows × 13 columns

# Step 5: For each video, extract comments (paginated)
all_comments = []
for vid in video_ids:
    comments = client.get_comments(vid, max_comments=200)
    all_comments.append(comments)

comments_df = pd.concat(all_comments, ignore_index=True)
# DataFrame: 18,243 rows × 8 columns
```

**Or use the shortcut:**

```python
videos_df, comments_df = client.audit_channel(
    "@PolicyPulse",
    max_videos=100,
    max_comments_per_video=200,
    output_dir="data/raw"
)
# Automatically saves to:
# - data/raw/policypulse_videos.parquet
# - data/raw/policypulse_comments.parquet
```

---

## Data Extraction Details

### Video Metadata Schema

**Source:** `videos().list(part="snippet,statistics,contentDetails")`

```python
# Raw API response (simplified)
{
    "id": "dQw4w9WgXcQ",
    "snippet": {
        "title": "Breaking Down the Federal Budget 2025",
        "channelId": "UC_policy_001",
        "channelTitle": "PolicyPulse",
        "publishedAt": "2025-02-14T09:23:00Z",
        "description": "In this video we explore the key provisions of...",
        "tags": ["policy", "budget", "canada"],
        "categoryId": "25",
        "defaultAudioLanguage": "en"
    },
    "statistics": {
        "viewCount": "45302",
        "likeCount": "2156",
        "commentCount": "387"
    },
    "contentDetails": {
        "duration": "PT14M13S"
    }
}
```

**Parsed output:**

```
video_id:           dQw4w9WgXcQ
title:              Breaking Down the Federal Budget 2025
channel_id:         UC_policy_001
channel_title:      PolicyPulse
published_at:       2025-02-14 09:23:00 (UTC)
view_count:         45302
like_count:         2156
comment_count:      387
duration_seconds:   853
is_short:           False
platform:           youtube
extracted_at:       2025-03-22 14:23:15 (UTC)
```

---

### Comment Extraction Schema

**Source:** `commentThreads().list(part="snippet")`

```python
# Raw API response (top-level comment only)
{
    "id": "UgyX1a2b3c4d5e6",
    "snippet": {
        "videoId": "dQw4w9WgXcQ",
        "topLevelComment": {
            "snippet": {
                "textDisplay": "Great analysis, thanks for covering this!",
                "authorDisplayName": "Jane Doe",
                "likeCount": 23,
                "publishedAt": "2025-02-14T14:37:00Z",
                "updatedAt": "2025-02-14T14:37:00Z"
            }
        },
        "totalReplyCount": 3
    }
}
```

**Parsed output:**

```
comment_id:     UgyX1a2b3c4d5e6
video_id:       dQw4w9WgXcQ
author:         Jane Doe
text:           Great analysis, thanks for covering this!
like_count:     23
reply_count:    3
published_at:   2025-02-14 14:37:00 (UTC)
platform:       youtube
extracted_at:   2025-03-22 14:23:15 (UTC)
```

---

## Error Handling

### Disabled Comments

Some videos have comments disabled. The API returns HTTP 403.

```python
comments_df = client.get_comments("dQw4w9WgXcQ")
# Logs: "WARNING: Comments disabled for video dQw4w9WgXcQ. Skipping."
# Returns: empty DataFrame
```

**Handling:** Videos with disabled comments contribute 0 rows to the comments DataFrame; the audit continues.

---

### Quota Exhaustion

If you exceed 10,000 units/day, the API returns a 403 with quota exceeded message.

```python
# If this happens, wait 24 hours or request increased quota
# https://console.cloud.google.com/apis/dashboard
```

---

## Performance Notes

### Request Timing

For a 100-video × 200-comment audit:

| Step | Quota | Time |
|---|---|---|
| Resolve handle | 100 | ~1s |
| Get playlist | 1 | ~1s |
| Get video IDs (paginated) | 1–3 | ~5s |
| Get metadata (batched 50/call) | 1–2 | ~3s |
| Extract comments (200 per video) | 100–200 | ~3–5 minutes |
| **Total** | **300–400** | **~5 minutes** |

**Bottleneck:** Comment extraction is I/O-bound (pagination + sleep throttling). Unavoidable due to API limits.

---

## Extending to Other Platforms

The module is designed for YouTube, but the output (raw Parquet files) can be augmented by other ETL modules.

**Future:** Add `TikTokClient` and `InstagramClient` with similar interfaces:

```python
# Hypothetical future code
from etl.tiktok_client import TikTokClient

tiktok_client = TikTokClient(api_key="...")
videos_tiktok, comments_tiktok = tiktok_client.audit_creator("@PolicyPulse")

# Both outputs fit the same schema (via normalisation in cleaning/)
all_videos = pd.concat([videos_youtube, videos_tiktok])
all_comments = pd.concat([comments_youtube, comments_tiktok])
```

---

## Configuration

### Environment Variables

```bash
# Required
export YOUTUBE_API_KEY="AIzaSyD..."

# Optional (for debugging)
export LOG_LEVEL="DEBUG"  # default: INFO
```

### API Key Setup

1. Go to **Google Cloud Console** (console.cloud.google.com)
2. Create a new project
3. Enable **YouTube Data API v3**
4. Create an **API key** (not OAuth 2.0)
5. Copy the key to your environment

**Security:** Never commit API keys to git. Use `.env` file (excluded by `.gitignore`):

```bash
# .env (not in repo)
YOUTUBE_API_KEY=AIzaSyD...
```

Load in code:

```python
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.environ["YOUTUBE_API_KEY"]
```

---

## Testing

Demo mode requires no API key:

```python
python pipeline.py --demo
```

To test with real API (requires key):

```bash
export YOUTUBE_API_KEY="YOUR_KEY"
python pipeline.py --channels @PolicyPulse --max-videos 5 --max-comments 10
```

The `--max-videos` and `--max-comments` flags let you test on small samples before running full audits.

---

## Limitations & Future Work

### Current Limitations

1. **Replies not extracted** — only top-level comments
2. **Recommendation crawling is a proxy** — uses `relatedToVideoId`, not identical to "Up Next" algorithm
3. **No channel statistics** — subscriber count, growth rate, etc. not included
4. **No live comments** — only published comments
5. **Language detection is heuristic** — EN/FR only, no multi-language support

### Future Improvements

- [ ] Extract reply threads (requires additional API calls)
- [ ] Integrate YouTube Analytics API (requires channel owner auth)
- [ ] Add captions/transcript extraction
- [ ] Implement proper recommendation chain crawling with simulated user agents
- [ ] Add channel growth metrics
- [ ] Support for Shorts (already detected but separately from long-form)

---

## References

- **YouTube Data API v3 Docs:** https://developers.google.com/youtube/v3
- **Quota Calculator:** https://developers.google.com/youtube/v3/determine_quota_cost
- **API Keys vs. OAuth:** https://developers.google.com/youtube/v3/guides/auth/api-keys
