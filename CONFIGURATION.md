# Configuration Guide

## Environment Setup

### 1. Python & Virtual Environment

**Create a virtual environment (recommended):**

```bash
# macOS / Linux
python3.11 -m venv venv
source venv/bin/activate

# Windows (cmd)
python -m venv venv
venv\Scripts\activate

# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Why:** Isolates project dependencies from system Python. Prevents version conflicts.

---

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**What gets installed:**
- `pandas`, `numpy` — data manipulation
- `pyarrow` — Parquet read/write
- `google-api-python-client` — YouTube API
- `vaderSentiment` — sentiment analysis
- `plotly` — interactive visualizations
- `python-dotenv` — environment variable loading
- `tqdm` — progress bars

**Optional (for transformer sentiment):**
```bash
pip install transformers torch
```

First install downloads the model (~500MB, then cached).

---

### 3. YouTube API Key

**Get a key:**

1. Go to **console.cloud.google.com**
2. Create or select a project
3. **Enable APIs:** Search "YouTube Data API v3" → Enable
4. **Create credentials:** API Key (not OAuth 2.0)
5. Copy the key

**Configure in code:**

```bash
# Option 1: Environment variable (preferred)
export YOUTUBE_API_KEY="AIzaSyD_xxxxxxxxxxxxxxxxxxxxxxxxxx"

# Option 2: .env file (local testing only)
echo 'YOUTUBE_API_KEY="AIzaSyD_xxxxxxxxxxxxxxxxxxxxxxxxxx"' > .env

# Option 3: Pass directly in code
from etl.youtube_client import YouTubeClient
client = YouTubeClient(api_key="AIzaSyD_...")
```

**.env file (never commit this):**

```bash
# .env (excluded by .gitignore)
YOUTUBE_API_KEY=AIzaSyD_xxxx
LOG_LEVEL=INFO
```

Load in code:
```python
from dotenv import load_dotenv
import os
load_dotenv()
api_key = os.environ["YOUTUBE_API_KEY"]
```

---

### 4. Optional: GPU Setup (for Transformer Sentiment)

**Check if GPU available:**

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

If False, you're on CPU.

**Install GPU-accelerated PyTorch:**

```bash
# NVIDIA CUDA (requires NVIDIA GPU)
pip install torch --index-url https://download.pytorch.org/whl/cu118

# Apple Metal (M1/M2 Macs)
pip install torch --index-url https://download.pytorch.org/whl/nightly/cpu
```

GPU provides ~10× speedup on transformer sentiment (100→10 seconds for 1k comments).

---

## Configuration Options

### Command-line Arguments

Run the pipeline with:

```bash
python pipeline.py [OPTIONS]
```

**Available options:**

```
--channels HANDLE [HANDLE ...]    YouTube channel @handles to audit
                                  Example: @PolicyPulse @CiviqueMontréal
                                  (optional if --demo)

--demo                            Use synthetic demo data (no API key needed)
                                  Default: False

--max-videos N                    Max videos per channel to extract
                                  Default: 100

--max-comments N                  Max comments per video to extract
                                  Default: 200

--output-dir PATH                 Directory to save outputs
                                  Default: outputs/

--transformer                     Enable transformer-based sentiment
                                  (requires transformers + torch)
                                  Default: False (VADER only)

--help                            Show this message and exit
```

**Examples:**

```bash
# Demo mode (no API key)
python pipeline.py --demo

# Real audit, single channel
python pipeline.py --channels @PolicyPulse

# Real audit, multiple channels, small sample
python pipeline.py --channels @PolicyPulse @CiviqueMontréal --max-videos 10 --max-comments 50

# Full audit with transformer sentiment
python pipeline.py --channels @PolicyPulse --max-videos 100 --max-comments 300 --transformer

# Custom output directory
python pipeline.py --demo --output-dir /tmp/my_outputs
```

---

### Python Configuration

**In code:**

```python
from etl.youtube_client import YouTubeClient
from cleaning.cleaner import CommentCleaner, VideoMetadataCleaner
from sentiment.analyzer import SentimentPipeline
from visualization.dashboard import render_all

# Custom YouTube client config
client = YouTubeClient(api_key="YOUR_KEY")

# Custom comment cleaner
comment_cleaner = CommentCleaner(min_chars=3, dedup=True)

# Custom sentiment pipeline (VADER + transformer)
sentiment_pipe = SentimentPipeline(use_transformer=True)

# Or VADER only (fast)
sentiment_pipe = SentimentPipeline(use_transformer=False)

# Run with custom config
videos_df, comments_df = client.audit_channel(
    "@PolicyPulse",
    max_videos=50,
    max_comments_per_video=100,
    output_dir="data/raw"
)

videos_clean = VideoMetadataCleaner().clean(videos_df)
comments_clean = comment_cleaner.clean(comments_df)
comments_scored = sentiment_pipe.run(comments_clean)

render_all(videos_clean, comments_scored, output_dir="outputs")
```

---

## Project Structure

Default directory layout:

```
Data-Analysis-2025/
├── civic-youtube-audit/
│   ├── pipeline.py              ← main entry point
│   ├── requirements.txt
│   ├── etl/
│   │   ├── __init__.py
│   │   ├── youtube_client.py    ← YouTube API client
│   │   └── README.md            ← module docs
│   ├── cleaning/
│   │   ├── __init__.py
│   │   ├── cleaner.py           ← data cleaning
│   │   └── README.md
│   ├── sentiment/
│   │   ├── __init__.py
│   │   ├── analyzer.py          ← sentiment scoring
│   │   └── README.md
│   ├── visualization/
│   │   ├── __init__.py
│   │   ├── dashboard.py         ← plotly figures
│   │   └── README.md
│   └── data/
│       ├── raw/                 ← YouTube API extracts
│       │   ├── README.md
│       │   ├── videos_raw.csv
│       │   ├── videos_raw.parquet
│       │   ├── comments_raw.csv
│       │   └── comments_raw.parquet
│       └── processed/           ← cleaned + scored data
│           ├── README.md
│           ├── videos_enriched.csv
│           ├── videos_enriched.parquet
│           ├── comments_scored.csv
│           ├── comments_scored.parquet
│           └── sentiment_summary.csv
├── docs/
│   ├── pipeline_design.md       ← architecture docs
│   └── README.md
├── notebooks/
│   └── README.md                ← exploratory analysis (planned)
├── .gitignore
├── README.md                    ← project overview
├── COMPREHENSIVE_GUIDE.md       ← detailed guide
├── API_REFERENCE.md             ← code examples
├── FAQ_TROUBLESHOOTING.md       ← Q&A + fixes
├── CONFIGURATION.md             ← this file
└── CHANGELOG.md                 ← version history
```

**Custom output directory:**

If you run `python pipeline.py --output-dir my_outputs`, outputs are saved to `my_outputs/` instead of `outputs/`.

---

## Logging Configuration

**Default log level:** INFO (progress, warnings, errors)

**Enable debug logging:**

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now all functions log detailed debug info
```

**In command line:**

```bash
# Not yet supported, but can modify pipeline.py to add:
# python pipeline.py --log-level DEBUG
```

**Log levels:**

```
DEBUG   (10) — detailed tracing (every API call, etc.)
INFO    (20) — progress updates (default)
WARNING (30) — warnings (disabled comments, etc.)
ERROR   (40) — errors (stops execution)
```

---

## Data Storage

### Parquet vs. CSV

**Parquet:**
- Pros: 4× smaller, 4× faster read, typed columns
- Cons: requires pyarrow library
- Use: analysis, efficient storage

**CSV:**
- Pros: human-readable, universal
- Cons: large files, slow to read
- Use: sharing with non-Python users, quick inspection

**Configuration:**

In `pipeline.py`, comment out CSV write if you only want Parquet:

```python
# Save to Parquet only
videos_clean.to_parquet(f"{output_dir}/videos_clean.parquet", index=False)
# comments_clean.to_csv(f"{output_dir}/comments_clean.csv", index=False)  ← disabled
```

---

## Database (Future)

For large-scale production deployment, consider a database:

```python
# Future: PostgreSQL backend
# import sqlalchemy
# engine = sqlalchemy.create_engine("postgresql://user:pass@localhost/civic_youtube")
# videos_clean.to_sql("videos", engine, if_exists="append")
# comments_scored.to_sql("comments", engine, if_exists="append")
```

Currently, everything is file-based (Parquet/CSV).

---

## Performance Tuning

### For Faster Execution

1. **Reduce data:**
   ```bash
   python pipeline.py --demo --max-videos 10 --max-comments 50
   ```

2. **Skip transformer sentiment:**
   ```bash
   python pipeline.py --demo  # don't use --transformer
   ```

3. **Use Parquet only:**
   Edit `pipeline.py` to remove `.to_csv()` calls

4. **Enable GPU:**
   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cu118
   python pipeline.py --demo --transformer
   ```

### For Lower Memory Usage

1. **Process channels one at a time:**
   ```bash
   python pipeline.py --channels @PolicyPulse
   # ... then ...
   python pipeline.py --channels @CiviqueMontréal
   ```

2. **Reduce sample:**
   ```bash
   python pipeline.py --max-comments 100
   ```

3. **Use dask for out-of-core processing** (future enhancement)

---

## Security & API Key Best Practices

**DO:**
- ✅ Use environment variables for keys
- ✅ Add `.env` to `.gitignore` (already done)
- ✅ Regenerate keys if compromised
- ✅ Use minimal quota permissions

**DON'T:**
- ❌ Commit API keys to git
- ❌ Share keys in chat/emails
- ❌ Use the same key for multiple projects
- ❌ Check code with hardcoded keys

**Rotate keys periodically:**

1. Generate new API key in Google Cloud Console
2. Update environment variable
3. Delete old key
4. Commit code (no key exposed)

---

## Verification Checklist

Before running a full audit:

```bash
# 1. Python version OK?
python --version  # should be 3.11+

# 2. Dependencies installed?
pip list | grep pandas numpy pyarrow

# 3. API key set?
echo $YOUTUBE_API_KEY  # should show your key (Linux/Mac)

# 4. Demo works?
python pipeline.py --demo  # should complete in <1 minute

# 5. Output directory writable?
ls -la outputs/  # should have HTML files

# 6. Ready for real audit?
python pipeline.py --channels @PolicyPulse --max-videos 5 --max-comments 50
```

If all pass, you're ready for a full audit!

---

## Troubleshooting Configuration

**"YOUTUBE_API_KEY not found"**

```bash
# Verify it's set
printenv YOUTUBE_API_KEY  # Linux/Mac
echo %YOUTUBE_API_KEY%    # Windows

# If empty, set it
export YOUTUBE_API_KEY="AIzaSyD_..."

# Or use .env file
echo 'YOUTUBE_API_KEY="AIzaSyD_..."' > .env
python pipeline.py --demo  # auto-loads .env
```

**"transformers not found"**

```bash
pip install transformers torch
```

**"Permission denied: data/processed"**

```bash
# Create directory with write permissions
mkdir -p data/processed
chmod 755 data/processed

# Or specify a different output directory
python pipeline.py --demo --output-dir /tmp/outputs
```

---

## Configuration Summary

| Setting | Where | Default | Why |
|---|---|---|---|
| API Key | `$YOUTUBE_API_KEY` env | Required | Authenticate to YouTube API |
| Max videos | `--max-videos` CLI | 100 | Balance quota vs. coverage |
| Max comments | `--max-comments` CLI | 200 | Balance signal vs. noise |
| Output dir | `--output-dir` CLI | `outputs/` | Organize outputs |
| Transformer | `--transformer` flag | False | VADER is fast, transformer is accurate |
| Data format | Code (pipeline.py) | CSV + Parquet | Parquet efficient, CSV portable |
| Min comment length | Code (cleaner.py) | 5 chars | Drop noise (single-char comments) |
| Language detection | Code (cleaner.py) | Heuristic EN/FR | Bilingual analysis (Canadian context) |

---

For more details, see:
- `README.md` — project overview
- `COMPREHENSIVE_GUIDE.md` — detailed walkthrough
- `API_REFERENCE.md` — code examples
- `FAQ_TROUBLESHOOTING.md` — common issues
