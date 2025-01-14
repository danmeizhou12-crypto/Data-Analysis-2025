# notebooks

Exploratory analysis notebooks. These are complementary to the production pipeline — used for prototyping and result interpretation, not as the primary data processing layer.

## Planned notebooks

| Notebook | Status | Description |
|---|---|---|
| `01_eda_videos.ipynb` | Planned | EDA on video metadata: distribution of views, duration, engagement rates |
| `02_eda_comments.ipynb` | Planned | Comment text EDA: length distribution, language split, top terms |
| `03_sentiment_deep_dive.ipynb` | Planned | VADER vs. transformer comparison, score distribution analysis |
| `04_algorithmic_reach.ipynb` | Planned | Engagement vs. sentiment scatter, framing pattern analysis |

## Running notebooks

```bash
pip install jupyter
jupyter notebook
```

All notebooks expect the processed data files to exist at `../civic-youtube-audit/data/processed/`. Run `pipeline.py --demo` first to generate them.
