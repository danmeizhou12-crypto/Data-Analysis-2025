# data/raw

Raw extracts directly from the YouTube Data API v3. These files are **never modified** — all transformations happen downstream in `data/processed/`.

## Files

| File | Format | Description |
|---|---|---|
| `videos_raw.csv` | CSV | Raw video metadata: 80 videos across 2 channels |
| `videos_raw.parquet` | Parquet | Same as above, columnar format for efficient reads |
| `comments_raw.csv` | CSV | Raw top-level comments: 2,000 records pre-cleaning |
| `comments_raw.parquet` | Parquet | Same as above |

## Schema — Videos

| Column | Type | Description |
|---|---|---|
| `video_id` | str | YouTube video ID |
| `channel_id` | str | YouTube channel ID |
| `channel_title` | str | Channel display name |
| `platform` | str | Source platform (`youtube`) |
| `title` | str | Video title |
| `description` | str | First 500 chars of description |
| `language` | str | Default audio language |
| `published_at` | datetime (UTC) | Video publish timestamp |
| `view_count` | int | Total views at extraction time |
| `like_count` | int | Total likes |
| `comment_count` | int | Total comments (API-reported) |
| `duration_seconds` | int | Video duration in seconds |
| `is_short` | bool | True if duration ≤ 60s |
| `extracted_at` | datetime (UTC) | Pipeline extraction timestamp |

## Schema — Comments

| Column | Type | Description |
|---|---|---|
| `comment_id` | str | Unique thread ID |
| `video_id` | str | Parent video ID |
| `channel_title` | str | Channel the comment belongs to |
| `platform` | str | Source platform |
| `text` | str | Raw comment text |
| `like_count` | int | Comment likes |
| `reply_count` | int | Number of replies |
| `published_at` | datetime (UTC) | Comment timestamp |
| `extracted_at` | datetime (UTC) | Extraction timestamp |

## Notes

- Data in this folder is **synthetic** (generated via `pipeline.py --demo`) and does not represent real individuals.
- In a live deployment, raw files are extracted by `etl/youtube_client.py` and written here automatically.
- Parquet is preferred for downstream processing; CSV is included for human readability.
