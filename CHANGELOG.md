# Changelog

## [Unreleased] — feature/sentiment-enhancements

### Added
- `sentiment/analyzer.py`: `top_comments()` helper to surface the most extreme positive/negative comments per video
- `sentiment/analyzer.py`: `sentiment_summary()` now accepts arbitrary `group_by` columns (e.g. `["channel_title", "language_detected"]`)
- `data/processed/sentiment_summary.csv`: aggregated sentiment stats by channel
- Language-stratified sentiment breakdown (EN vs. FR) in `sentiment_summary()`

### Changed
- `cleaning/cleaner.py`: `COMMENT_SCHEMA` now includes `channel_title` for group-by aggregations
- `visualization/dashboard.py`: `plot_top_terms()` stopword list expanded with French function words

### Fixed
- `pipeline.py`: `sentiment_summary()` `KeyError` on `channel_title` when called before schema normalisation

---

## [0.1.0] — Initial release

- YouTube Data API v3 ETL pipeline (`etl/youtube_client.py`)
- Cross-platform data cleaning and schema normalisation (`cleaning/cleaner.py`)
- Dual-model sentiment pipeline: VADER + HuggingFace transformer (`sentiment/analyzer.py`)
- Six Plotly dashboard figures (`visualization/dashboard.py`)
- End-to-end pipeline orchestrator with `--demo` mode (`pipeline.py`)
