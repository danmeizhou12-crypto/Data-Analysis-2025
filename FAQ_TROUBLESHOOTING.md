# FAQ & Troubleshooting

## Common Questions

### Installation & Setup

**Q: I get `ModuleNotFoundError: No module named 'googleapiclient'`**

A: You haven't installed dependencies. Run:
```bash
pip install -r requirements.txt
```

**Q: How do I get a YouTube API key?**

A: 
1. Go to **console.cloud.google.com**
2. Create a new project
3. Enable **YouTube Data API v3**
4. Create an **API key** credential (not OAuth 2.0)
5. Copy the key and set:
```bash
export YOUTUBE_API_KEY="AIzaSyD..."
```

**Q: Can I use OAuth 2.0 instead of an API key?**

A: The current code only supports API keys. OAuth 2.0 would be needed for accessing private/restricted data (e.g., channel analytics). For public comment data, API key is sufficient.

**Q: Is there a Windows/Mac/Linux difference?**

A: No. Code is pure Python. Only difference is shell commands:
- **Mac/Linux:** `export YOUTUBE_API_KEY="..."` in bash
- **Windows:** `set YOUTUBE_API_KEY=...` in cmd, or add to System Environment Variables

---

### Running the Pipeline

**Q: What does `--demo` mode do? Why would I use it?**

A: Demo mode generates synthetic data without hitting the YouTube API. Use it to:
- Test the pipeline before using your API key
- Understand output formats without quota cost
- Share examples with others (no API key needed)
- Debug cleaning/sentiment logic

**Q: How much quota does a full audit use?**

A: A 100-video × 200-comment audit uses ~300–400 quota units (out of 10,000/day limit). You could run **25+ audits per day** without hitting the quota.

**Q: My audit is taking forever. Why?**

A: The bottleneck is comment extraction (~3–5 min for 100 videos). The client sleeps 2 seconds between paginated requests (quota courtesy). This is unavoidable due to API limits.

To speed up testing:
```bash
python pipeline.py --channels @PolicyPulse --max-videos 10 --max-comments 50
```

**Q: Can I run multiple audits in parallel?**

A: No. The API key has a single quota bucket (10,000 units/day). Parallel requests would exhaust quota faster. Run sequentially or split by day.

**Q: Why are some videos missing comments?**

A: YouTube allows creators to disable comments. The client logs a warning and skips those videos. This is normal.

**Q: How many comments should I extract per video?**

A: Depends on your use case:
- **Quick analysis:** 50–100 per video (faster, noisier)
- **Balanced:** 200–300 per video (recommended)
- **Deep analysis:** 500+ per video (slower, comprehensive)

Default: 200.

---

### Data & Cleaning

**Q: What's the difference between raw and processed data?**

A:
- **Raw** = direct YouTube API output (data/raw/)
- **Processed** = cleaned, deduplicated, scored (data/processed/)

Raw is immutable (audit trail). Processed is what you analyse.

**Q: How much data do I lose in cleaning?**

A: Roughly 35–40% of raw comments are dropped:
- Duplicates: ~20% (exact copy-paste)
- Short comments: ~10% (< 5 chars after cleaning)
- Empty comments: ~5%

This is expected and healthy. You're removing noise.

**Q: Why deduplicate? Don't duplicate comments matter?**

A: Duplicates are almost always spam or copy-paste from top comments. Removing them reduces noise in sentiment analysis. If you want to preserve duplicates:
```python
cleaner = CommentCleaner(dedup=False)
```

**Q: How do I change the minimum comment length?**

A:
```python
cleaner = CommentCleaner(min_chars=10)  # require 10+ chars instead of 5
```

**Q: Is language detection accurate?**

A: The current method is a heuristic (checks for French function words). It works ~90% for pure EN/FR but struggles with:
- Code-switching (mixed EN/FR)
- Rare languages
- Slang/abbreviations

For production, use `langdetect` or `lingua-py`:
```bash
pip install langdetect
```

Then replace the function in `cleaner.py`.

---

### Sentiment Analysis

**Q: What's the difference between VADER and the transformer model?**

A:
- **VADER:** Fast (~1ms per text), lexicon-based, interpretable, no GPU needed. Good for exploration.
- **Transformer:** Slower (~100ms per text, needs GPU), neural network, more accurate on social media text.

For 1,000 comments:
- VADER: ~1 second
- Transformer: ~100 seconds (or ~10 seconds with GPU)

**Q: How do I use only VADER (faster)?**

A:
```bash
python pipeline.py --demo  # doesn't use --transformer flag
```

Or in code:
```python
from sentiment.analyzer import SentimentPipeline
pipe = SentimentPipeline(use_transformer=False)
```

**Q: How do I enable the transformer model?**

A:
```bash
pip install transformers torch
python pipeline.py --demo --transformer
```

Warning: First load downloads the model (~500MB). Requires ~2GB GPU VRAM for inference.

**Q: What does the ensemble label mean?**

A: It's the final sentiment label after combining VADER + transformer:
- If both agree → use that label
- If they disagree → trust transformer if confident (score ≥ 0.70), otherwise VADER

This reduces false positives from either model.

**Q: Why is a comment marked as "neutral" when it's clearly positive?**

A: Possible reasons:
1. Comment has mixed sentiment ("good policy but bad timing")
2. Language is sarcastic ("fantastic, just what we needed" = negative)
3. Model disagrees with you (not always right)

**Read the raw text:** Check `text_raw` column to validate scores manually.

**Q: Can I threshold sentiment confidence?**

A: Yes. The `sentiment_confidence` column is a proxy (transformer score or |compound|):

```python
# Only high-confidence positive comments
high_conf_positive = comments_scored[
    (comments_scored["ensemble_label"] == "positive") &
    (comments_scored["sentiment_confidence"] > 0.70)
]
```

---

### Visualisation

**Q: Why are the figures saved as HTML instead of PNG?**

A: HTML figures are interactive (zoom, hover, export). PNG is static. HTML is better for exploration and stakeholder demos.

To export to PNG:
```python
fig = figures["sentiment_over_time"]
fig.write_image("sentiment_over_time.png", width=1200, height=600)
```

Requires: `pip install kaleido`

**Q: Can I customise the colour scheme?**

A: Yes. Edit the `PALETTE` dict in `visualization/dashboard.py`:

```python
PALETTE = {
    "positive": "#2ecc71",    # change to your colour
    "neutral": "#95a5a6",
    "negative": "#e74c3c",
    "accent": "#2c3e50",
    "bg": "#f8f9fa",
}
```

**Q: How do I add a new figure?**

A: See the existing figures in `dashboard.py` as a template. Basic structure:

```python
def plot_my_figure(df: pd.DataFrame, output_path: str = "outputs/my_figure.html") -> go.Figure:
    """Short description."""
    fig = px.bar(df, x="col1", y="col2")
    fig.update_layout(**LAYOUT_BASE)
    _save(fig, output_path)
    return fig
```

Then add to `render_all()`:
```python
figures["my_figure"] = plot_my_figure(comments_df)
```

---

### Performance & Scaling

**Q: How much data can this pipeline handle?**

A:
- **Tested:** 100 videos, ~20k comments (memory: <100MB)
- **Expected limit:** 10k videos, ~500k comments (memory: ~2GB)
- **Beyond:** Use dask for out-of-core processing (future enhancement)

**Q: Is Parquet faster than CSV?**

A: Yes, ~4× faster on reads:
- **CSV:** read 20k comments in ~500ms
- **Parquet:** read 20k comments in ~100ms

Parquet also uses ~4× less disk space.

**Q: Should I keep both CSV and Parquet?**

A: In production:
- Keep **Parquet** (efficient)
- Generate **CSV** on-demand for sharing with non-Python users

To disable CSV output, edit `pipeline.py` and remove the `.to_csv()` calls.

---

### Extending the Pipeline

**Q: How do I add support for TikTok?**

A: Create `etl/tiktok_client.py` with the same interface as `YouTubeClient`:

```python
class TikTokClient:
    def audit_creator(self, handle, max_videos=100) -> tuple[pd.DataFrame, pd.DataFrame]:
        # Extract videos and comments
        # Normalise to unified schema (video_id, title, platform, etc.)
        # Save to data/raw/
        return videos_df, comments_df
```

The rest of the pipeline (cleaning, sentiment, viz) works unchanged because of the unified schema.

**Q: Can I add custom sentiment models?**

A: Yes. Subclass `SentimentAnalyzer` in `sentiment/analyzer.py`:

```python
class MyCustomModel:
    def score_batch(self, texts: list[str]) -> list[dict]:
        # Your model logic
        return [{"label": "positive", "score": 0.9}, ...]
```

Then integrate into `SentimentPipeline.run()`.

**Q: How do I add more visualisations?**

A: Add a new function to `visualization/dashboard.py` (see template above) and call it from `render_all()`.

---

## Troubleshooting

### "YOUTUBE_API_KEY not set"

**Error:**
```
ValueError: YouTube API key required. Set YOUTUBE_API_KEY env var or pass api_key=.
```

**Fix:**
```bash
export YOUTUBE_API_KEY="AIzaSyD..."
python pipeline.py --demo  # or --channels @Handle
```

Or in code:
```python
from etl.youtube_client import YouTubeClient
client = YouTubeClient(api_key="AIzaSyD...")
```

---

### "No channel found for handle"

**Error:**
```
ValueError: No channel found for handle: @InvalidHandle
```

**Fix:** Verify the channel handle exists on YouTube. Try:
1. Search the channel name on YouTube
2. Copy the exact @handle from the channel URL
3. Try without @ symbol

---

### "Comments disabled for video"

**Warning:**
```
WARNING: Comments disabled for video vid_0001. Skipping.
```

This is normal. Some creators disable comments. The pipeline continues; that video just contributes 0 comments.

---

### "Out of memory" / "Memory error"

**Error:**
```
MemoryError: Unable to allocate X GB for array
```

**Fix:** 
- Reduce `--max-videos` and `--max-comments`
- Use Parquet instead of CSV (smaller in memory)
- On large datasets, use dask (future enhancement)

Example:
```bash
python pipeline.py --demo --max-videos 50 --max-comments 100
```

---

### "transformers not found"

**Error:**
```
ImportError: No module named 'transformers'
```

**Fix:**
```bash
pip install transformers torch
```

First download takes ~500MB. Subsequent loads use cache (~5 seconds).

---

### "sentiment analysis is very slow"

**Cause:** Using transformer model on CPU (without GPU).

**Fix:**
- Use VADER only: don't pass `--transformer`
- Or install CUDA and GPU torch for 10× speedup

```bash
# Check if GPU available
python -c "import torch; print(torch.cuda.is_available())"
```

---

### "Duplicate check_sum vs text check not working"

**Issue:** Deduplication uses `(video_id, text_clean)` as key, not raw text. If cleaning changes the text, duplicates might not be detected.

**Example:**
```
Raw:
  "Check this out! https://t.co/abc"
  "Check this out! https://t.co/xyz"  ← different URL
  
After cleaning (URLs stripped):
  "check this out"
  "check this out"  ← NOW they're duplicates
```

This is intentional — deduplicate after cleaning to catch semantic duplicates.

---

## Getting Help

1. **Check the docs:**
   - `API_REFERENCE.md` — detailed function signatures
   - `COMPREHENSIVE_GUIDE.md` — high-level overview
   - Module READMEs (etl/, cleaning/, sentiment/)

2. **Run demo:**
   ```bash
   python pipeline.py --demo
   ```
   All outputs are in `outputs/` — examine them for clues.

3. **Enable debug logging:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

4. **Check the code:** Source is well-commented. Read the docstrings!

---

## Bug Reports

If you find a bug:
1. Reproduce with `--demo` mode (no API key needed)
2. Note Python version, OS, and pip list
3. Include the full error traceback
4. Open an issue on GitHub with reproduction steps
