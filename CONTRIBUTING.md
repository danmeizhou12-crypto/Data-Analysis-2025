# Contributing Guidelines

Thank you for your interest in improving this project! This document explains how to contribute.

---

## Code of Conduct

- Be respectful and inclusive
- Focus on the code, not the person
- Help others learn and grow
- Questions are always welcome

---

## How to Contribute

### Reporting Bugs

Found a bug? Please report it!

**Before filing:** Check if it's already reported in the issue tracker.

**When filing, include:**
- Python version and OS
- Steps to reproduce
- Expected vs. actual behavior
- Full error traceback
- Current workaround (if any)

**Example:**

```
Title: sentiment pipeline crashes on empty comments

Environment:
- Python 3.11.2
- Mac OS 13.2
- pandas 2.1.0

Steps to reproduce:
1. Run: python pipeline.py --demo
2. In sentiment/analyzer.py, manually call SentimentPipeline.run() on empty DataFrame

Expected: Return empty DataFrame with sentiment columns
Actual: KeyError on 'text_clean'

Traceback:
...
KeyError: 'text_clean'
...

Workaround: Filter out empty comments before calling pipeline
```

---

### Suggesting Enhancements

Have an idea for a new feature? Open a discussion!

**Describe:**
- What problem it solves
- How you'd use it
- Alternative approaches you've considered
- Any tradeoffs

**Example:**

```
Title: Add support for reply threads (nested comments)

Use case: Current implementation only extracts top-level comments.
For deeply engaged discussions, we're missing reply context.

Proposed solution: Modify YouTubeClient.get_comments() to optionally
extract reply threads, flattening them into the main comments DataFrame
with a "parent_comment_id" column.

Tradeoff: More API quota cost (1 unit per reply thread).
Impact: Would add ~20% to comment count but provide richer signal.

Questions: Should replies be deduplicated separately from top-level?
```

---

### Contributing Code

#### Step 1: Fork & Branch

```bash
git clone https://github.com/YOUR_USERNAME/Data-Analysis-2025.git
cd Data-Analysis-2025
git checkout -b feature/your-feature-name
```

Branch naming:
- `feature/` — new feature
- `fix/` — bug fix
- `docs/` — documentation
- `refactor/` — code cleanup

#### Step 2: Make Changes

Write clear, well-commented code:

```python
def detect_sentiment_drift(
    df: pd.DataFrame,
    window_days: int = 14,
    threshold: float = 0.15,
    date_col: str = "published_at",
    score_col: str = "vader_compound",
    group_col: str = "channel_title",
) -> pd.DataFrame:
    """
    Detect significant shifts in rolling mean sentiment over time.

    Parameters
    ----------
    df : pd.DataFrame
        Comments DataFrame with timestamps and sentiment scores.
    window_days : int
        Rolling window size in days (default: 14).
    threshold : float
        Min absolute shift in compound score to flag (default: 0.15).
    date_col : str
        Column name for comment timestamp (default: "published_at").
    score_col : str
        Column name for sentiment score (default: "vader_compound").
    group_col : str
        Column to stratify by (default: "channel_title").

    Returns
    -------
    pd.DataFrame
        With columns: date, rolling_mean, prior_mean, delta, drift_flagged.

    Raises
    ------
    ValueError
        If required columns not in DataFrame.

    Examples
    --------
    >>> drift_df = detect_sentiment_drift(
    ...     comments_scored,
    ...     window_days=7,
    ...     threshold=0.10
    ... )
    >>> drift_events = drift_df[drift_df["drift_flagged"]]
    """
    # Implementation...
```

**Standards:**
- Type hints on all function signatures
- Docstrings (Google style) for all public functions
- Comments for non-obvious logic
- Variable names that explain intent (`compound_score` not `cs`)

#### Step 3: Test

```bash
# Run demo to verify nothing broke
python pipeline.py --demo

# Check output visually
head -5 outputs/comments_clean.csv

# For code changes, add unit tests if possible
# (future: pytest suite will be added)
```

#### Step 4: Commit

```bash
git add .
git commit -m "feat(sentiment): add drift detection

Implement rolling-window anomaly detection to flag periods where
audience sentiment shifts significantly. Useful for hypothesis testing
around political events or viral moments.

Adds: detect_sentiment_drift() and plot_sentiment_drift()
Tests: Verified on synthetic data (80 videos, 1.2k comments)
Closes #123"
```

**Commit message format:**
- **Type:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- **Scope:** Module or component (sentiment, viz, etl, etc.)
- **Subject:** Imperative mood, no period, max 50 chars
- **Body:** Explain what and why (not how), max 72 chars/line
- **Footer:** Reference issues (`Closes #123`)

#### Step 5: Push & Open PR

```bash
git push origin feature/your-feature-name
```

Go to GitHub and open a pull request. Fill in:
- **Title:** Same as commit message subject
- **Description:** Explain the change and why it matters
- **Screenshots:** If visual changes (plots, etc.)
- **Checklist:**
  - [ ] Code follows project style
  - [ ] Tests added/updated
  - [ ] Documentation updated
  - [ ] Demo still works
  - [ ] No new warnings in output

**Example PR:**

```
Title: feat(sentiment): language-stratified sentiment summary

## Description
Adds sentiment_by_language() — convenience wrapper that groups
sentiment stats by both channel and detected language. Enables
comparison of how Anglophone vs. Francophone audiences respond
to civic content.

## Motivation
The Canadian Civic Influence Project requires bilingual analysis.
This function is a one-liner for EN vs. FR comparison.

## Changes
- sentiment/analyzer.py: sentiment_by_language()
- Updated docstring to include language column requirements

## Testing
Verified on demo data:
- 80 videos, 1,214 comments
- Correct grouping on both channels
- Correct grouping on both languages
- No breaking changes to existing functions

## Checklist
- [x] Code style consistent
- [x] Docstrings added
- [x] Demo still passes
- [x] No new errors/warnings
```

#### Step 6: Respond to Review

Maintainers may request changes. This is normal and collaborative:

```bash
# Make requested changes
git add .
git commit -m "Address review feedback"

# Update the PR (no need to force-push unless restructuring)
git push origin feature/your-feature-name

# The PR automatically updates
```

#### Step 7: Merge

Once approved:
- Use **squash merge** to keep main history clean
- Delete the feature branch
- Celebrate! 🎉

---

## Code Style

### Python

Follow **PEP 8** with these additions:

**Line length:** 100 characters (not 79)

```python
# Good
very_long_variable = some_function(arg1, arg2, arg3, arg4, arg5)

# Bad
very_long_variable=some_function(arg1,arg2,arg3,arg4,arg5)  # no spaces
```

**Type hints:**

```python
# Always include
def score_batch(texts: list[str]) -> list[dict]:
    pass

# Not
def score_batch(texts):
    pass
```

**Docstrings:**

```python
# Google style
def clean_text(
    text: str,
    lowercase: bool = True,
) -> str:
    """
    Apply text cleaning pipeline.

    Parameters
    ----------
    text : str
        Raw text to clean.
    lowercase : bool
        Whether to lowercase (default: True).

    Returns
    -------
    str
        Cleaned text.

    Examples
    --------
    >>> clean_text("HELLO WORLD!")
    'hello world'
    """
```

**Naming:**

```python
# Good
sentiment_compound = 0.75
comments_per_1k_views = 10.5
is_short = True

# Bad
sc = 0.75
cpm = 10.5  # ambiguous (cost per mille?)
short = True  # less explicit
```

### Comments

Comment **why**, not **what**:

```python
# Good
# Use deduplication on cleaned text, not raw, to catch semantic duplicates
df = df.drop_duplicates(subset=["video_id", "text_clean"])

# Bad
# Drop duplicates
df = df.drop_duplicates(subset=["video_id", "text_clean"])
```

---

## File Organization

**Modules:**
```
etl/           — extraction (YouTube API, future: TikTok, Instagram)
cleaning/      — text preprocessing, schema normalisation
sentiment/     — sentiment scoring (VADER, transformer, ensemble)
visualization/ — interactive Plotly figures
```

**When adding a new module:**
1. Create folder: `mkdir my_feature`
2. Add `__init__.py`: `touch my_feature/__init__.py`
3. Implement logic: `my_feature/my_module.py`
4. Add docs: `my_feature/README.md`
5. Update parent `README.md`

---

## Documentation

### Inline Comments

```python
# Explain non-obvious decisions
# (Use sparingly — code should be self-explanatory)

# Unicode normalization handles accented characters (é, ñ)
# so "Québec" == "Quebec" after normalisation
text = unicodedata.normalize("NFKC", text)
```

### Docstrings

Every public function needs one:

```python
def my_function(x: int, y: str) -> bool:
    """One-line summary.

    Longer description if needed.

    Parameters
    ----------
    x : int
        Description of x.
    y : str
        Description of y.

    Returns
    -------
    bool
        Description of return value.

    Raises
    ------
    ValueError
        When X happens.

    Examples
    --------
    >>> my_function(42, "hello")
    True
    """
```

### Module README

Every module has a `README.md`:

```markdown
# Module Name (module_name.py)

## Overview
Brief description of what this module does.

## Key Classes
- ClassName — what it does

## Key Functions
- function_name() — what it does

## Usage Example
```python
from module_name import ClassName
obj = ClassName()
result = obj.method()
```

## Performance Notes
- Typical timing
- Memory usage
- Bottlenecks

## Future Work
- [ ] Enhancement 1
- [ ] Enhancement 2
```

### Update CHANGELOG

Every PR should update `CHANGELOG.md`:

```markdown
## [Unreleased]

### Added
- sentiment_by_language() convenience function
- Language column in sentiment_summary output

### Changed
- Updated COMMENT_SCHEMA to include channel_title

### Fixed
- sentiment_summary() KeyError on empty groupby
```

---

## Testing (Future)

Once a test suite is added:

```bash
pytest tests/
```

For now, verify with:

```bash
python pipeline.py --demo
# Check outputs/ for expected files
```

---

## Performance Considerations

When contributing:

**Consider quota cost (YouTube API):**
- Each operation has a cost
- Batch requests where possible (50 videos per call)
- Sleep between paginated requests

**Consider memory usage:**
- Test with `--demo --max-videos 10 --max-comments 50` first
- Use Parquet (not CSV) for large datasets
- Avoid loading entire dataset into memory if possible (future: dask)

**Consider speed:**
- Use VADER for fast iteration (transformer is slow)
- Profile bottlenecks (`import cProfile`)
- Document timing expectations in docstrings

---

## Questions?

- **Documentation:** Check READMEs in each folder
- **Examples:** See `API_REFERENCE.md`
- **Configuration:** See `CONFIGURATION.md`
- **Troubleshooting:** See `FAQ_TROUBLESHOOTING.md`

---

## Recognition

All contributors are recognized in:
- PR merge commit message
- GitHub Contributors page
- (Future: CONTRIBUTORS.md file)

Thank you for making this project better! 🙌
