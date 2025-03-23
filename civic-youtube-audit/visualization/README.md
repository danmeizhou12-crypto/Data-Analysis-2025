# Visualization Module (`visualization/dashboard.py`)

## Overview

The visualization module transforms processed data into interactive Plotly dashboards. Purpose: **Make data insights accessible to stakeholders.**

All figures are static HTML files (no server required), enabling easy sharing and archival.

---

## Design Philosophy

**Interactive > Static**
- Hover tooltips reveal exact values
- Zoom and pan for detail
- Export to PNG/SVG if needed

**Stakeholder-focused**
- Clear titles and axis labels
- Intuitive colour schemes (green=good, red=bad)
- Multiple perspectives on the same data (time, space, distribution)

**Production-ready**
- Publication-quality fonts (Inter, sans-serif)
- Consistent styling across all figures
- Optimised layout (margins, spacing)

---

## Core Styling

All figures use consistent design:

```python
PALETTE = {
    "positive": "#2ecc71",       # green
    "neutral": "#95a5a6",        # grey
    "negative": "#e74c3c",       # red
    "accent": "#2c3e50",         # dark blue
    "bg": "#f8f9fa",             # light grey background
}

LAYOUT_BASE = dict(
    font=dict(family="Inter, Arial, sans-serif", size=13, color="#2c3e50"),
    paper_bgcolor="white",
    plot_bgcolor=PALETTE["bg"],
    margin=dict(l=60, r=40, t=70, b=60),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
```

---

## The 8 Figures

### 1. Sentiment Over Time

**File:** `sentiment_over_time.html`

**Purpose:** Track how audience sentiment changes over time. Useful for detecting shifts around major events.

```python
from visualization.dashboard import plot_sentiment_over_time

fig = plot_sentiment_over_time(
    comments_scored,
    channel_col="channel_title",
    window=7,  # 7-day rolling average
)
```

**What to look for:**
- Downward trend: audience opinion worsening
- Upward trend: audience opinion improving
- Spikes/dips: potential event-driven shifts

**Example interpretation:**
```
PolicyPulse sentiment timeline:
Mar 1:  +0.15 (baseline)
Mar 15: +0.05 (budget announcement)
Mar 25: -0.10 (policy criticism)
→ Budget announcement correlated with -0.10 shift
```

---

### 2. Label Distribution

**File:** `label_distribution.html`

**Purpose:** Show the overall breakdown of positive vs. negative sentiment per channel.

```python
fig = plot_label_distribution(comments_scored, channel_col="channel_title")
```

**What to look for:**
- Channels with >50% positive = strong audience approval
- Channels with >30% negative = controversial content
- Neutral % high = ambiguous/mixed messaging

**Example:**
```
PolicyPulse:        38% pos, 45% neu, 17% neg ← balanced
CiviqueMontréal:    52% pos, 32% neu, 16% neg ← more positive
```

---

### 3. Engagement vs. Sentiment

**File:** `engagement_vs_sentiment.html`

**Purpose:** Does higher engagement correlate with more positive or negative sentiment?

```python
fig = plot_engagement_vs_sentiment(videos_enriched)
```

**Axes:**
- X: mean sentiment per video (compound score)
- Y: engagement rate (likes per 1k views)
- Bubble size: view count

**Insights:**
- **Bottom-right cluster** (low sentiment, high engagement) = provocative content drives reach
- **Top-left cluster** (high sentiment, low engagement) = positive but low-reach content
- **Top-right cluster** (high sentiment, high engagement) = ideal (positive + popular)

**Example interpretation:**
```
Budget video:
  sentiment: -0.05
  engagement: 48 likes/1k views
  → Controversial but highly engaging

Reform video:
  sentiment: +0.25
  engagement: 32 likes/1k views
  → Positive but lower reach
```

---

### 4. Comment Volume Heatmap

**File:** `comment_volume_heatmap.html`

**Purpose:** When do audiences comment most? (identifies peak engagement times)

```python
fig = plot_comment_volume_heatmap(
    comments_scored,
    channel_col="channel_title"
)
```

**Axes:**
- X: Hour of day (0–23 UTC)
- Y: Day of week (Monday–Sunday)
- Colour intensity: number of comments

**What to look for:**
- Peak times (hot cells) = when to publish for max engagement
- Off-peak times (cool cells) = when to avoid publishing

**Example:**
```
High activity: Wed 18:00 UTC, Thu 19:00 UTC
→ Post important updates then for max comments
Low activity: Sun 03:00 UTC
→ Comments disabled then (users sleeping)
```

---

### 5. Top Terms by Sentiment

**File:** `top_terms.html`

**Purpose:** What words characterise each sentiment? Reveals framing vocabulary.

```python
fig = plot_top_terms(comments_scored, n_terms=15)
```

**Layout:** 3-panel figure (positive | neutral | negative)

**What to look for:**
- Positive panel: aspirational language ("hope", "growth")
- Negative panel: critical language ("corrupt", "unfair")
- Neutral panel: factual language ("policy", "implementation")

**Example interpretation:**
```
Positive: "inspiring", "proud", "hope", "growth"
→ Audience values forward-looking, aspirational messaging

Negative: "corrupt", "misleading", "disaster", "betrayal"
→ Audience concerned with integrity, transparency

Neutral: "budget", "policy", "implementation", "federal"
→ Technical discussion of governance
```

---

### 6. Language Breakdown

**File:** `language_breakdown.html`

**Purpose:** English vs. French comment split per channel.

```python
fig = plot_language_breakdown(comments_scored, channel_col="channel_title")
```

**Why it matters (Canada):**
- 30% of audience is Francophone (Quebec + bilingual Canadians)
- EN-heavy = missed Francophone outreach
- Balanced = reaching both communities

**Example:**
```
PolicyPulse:    75% EN, 25% FR ← Anglophone-focused
CiviqueMontréal: 40% EN, 60% FR ← Francophone-focused
```

---

### 7. Civic Keyword Sentiment Heatmap

**File:** `keyword_sentiment_heatmap.html`

**Purpose:** Do different civic framing strategies evoke different sentiment?

```python
fig = plot_keyword_sentiment_heatmap(comments_tagged)
```

**Heatmap:** RdYlGn (red=negative, yellow=neutral, green=positive)

**What to look for:**
- Policy framing: audience sentiment on budget, tax, healthcare, etc.
- Identity framing: audience sentiment on rights, diversity, inclusion, etc.
- Sentiment signal: when audience uses emotional language

**Example interpretation:**
```
          PolicyPulse  CiviqueMontréal
Policy         +0.10      +0.08         ← balanced policy sentiment
Identity       -0.05      +0.15         ← identity framing polarised
Sentiment      -0.08      +0.10         ← CiviqueMtl uses more optimism
```

---

### 8. Sentiment Drift Timeline

**File:** `sentiment_drift.html`

**Purpose:** Show rolling sentiment with flagged drift events.

```python
fig = plot_sentiment_drift(drift_df, channel_col="channel_title")
```

**What to look for:**
- Red diamonds = flagged drift events (shift > threshold)
- Line trajectory = overall sentiment trend
- Multiple dips on one day = potential event trigger

**Example:**
```
Mar 21: Red diamond (shift = +0.25)
→ Positive drift on that date
→ What happened? Election announcement? Good news cycle?

Hypothesis testing:
- Check external events calendar
- Read actual comments from that date
- Validate causation vs. correlation
```

---

## Creating Custom Figures

### Template

```python
def plot_my_analysis(
    df: pd.DataFrame,
    output_path: str = "outputs/my_figure.html",
) -> go.Figure:
    """
    Descriptive title.

    Parameters
    ----------
    df : pd.DataFrame
        Input data with sentiment scores.
    output_path : str
        Output HTML file path.

    Returns
    -------
    go.Figure
        Plotly figure object.
    """
    # Prepare data
    grouped = df.groupby("column1")["column2"].mean()

    # Create figure
    fig = px.bar(
        grouped,
        x=grouped.index,
        y=grouped.values,
        title="My Analysis Title",
    )

    # Apply styling
    fig.update_layout(**LAYOUT_BASE)

    # Save
    _save(fig, output_path)
    return fig
```

### Add to `render_all()`

```python
def render_all(videos_df, comments_df, output_dir="outputs"):
    figures = {}
    
    # ... existing figures ...
    
    figures["my_analysis"] = plot_my_analysis(
        comments_df,
        output_path=f"{output_dir}/my_analysis.html"
    )
    
    return figures
```

---

## Customisation

### Change Colour Scheme

```python
PALETTE = {
    "positive": "#0066cc",   # blue instead of green
    "neutral": "#cccccc",
    "negative": "#ff3333",   # bright red instead of dark
    "accent": "#333333",
    "bg": "#f0f0f0",
}
```

### Export to PNG

```python
fig = figures["sentiment_over_time"]
fig.write_image("sentiment_over_time.png", width=1200, height=600)

# Requires: pip install kaleido
```

### Export to PDF

```python
fig.write_image("sentiment_over_time.pdf")
```

### Embed in Report

```python
# Save to string (for embedding in HTML report)
html_string = fig.to_html(include_plotlyjs='cdn')

# Or use in Jupyter
fig.show()
```

---

## Performance

### Figure Sizing

File sizes:
- Simple (bar, scatter): ~200KB
- Complex (heatmap, multi-panel): ~500KB
- 8 figures total: ~3MB

**Web optimization:**
- Use `include_plotlyjs='cdn'` to avoid embedding Plotly library in each file
- Reduce marker density for scatter plots with 10k+ points

### Rendering Time

For 1,214 comments across 2 channels:

| Figure | Time |
|---|---|
| sentiment_over_time | ~500ms |
| label_distribution | ~200ms |
| engagement_vs_sentiment | ~300ms |
| comment_volume_heatmap | ~400ms |
| top_terms | ~600ms |
| language_breakdown | ~200ms |
| keyword_sentiment_heatmap | ~300ms |
| sentiment_drift | ~400ms |
| **Total** | **~3 seconds** |

---

## Sharing & Archival

### For Stakeholders

```bash
# Email the HTML files directly (self-contained, no server needed)
zip outputs.zip outputs/*.html
# Send outputs.zip
```

Recipients can open HTML files in any browser.

### For Documentation

```bash
# Export to PNG for reports
fig.write_image("sentiment_over_time.png")

# Embed in PDF report
# (external tools like pandoc, wkhtmltopdf)
```

### For Version Control

```bash
# Save to git (small enough)
git add outputs/*.html

# Or use .gitignore to exclude HTML (large number)
echo "outputs/*.html" >> .gitignore
```

---

## Troubleshooting

### Figure is blank

**Cause:** Missing columns in DataFrame

**Fix:** Check that sentiment pipeline has run:
```python
print(comments_scored.columns)
# Should include: vader_compound, ensemble_label, etc.
```

### Figure is very slow

**Cause:** Too many points (10k+ on scatter plot)

**Fix:** Subsample data:
```python
comments_sample = comments_scored.sample(frac=0.1)
fig = plot_sentiment_over_time(comments_sample)
```

### Colours don't match PALETTE

**Cause:** Using default Plotly colours

**Fix:** Explicitly set colours in figure:
```python
fig = px.bar(..., color_discrete_map=PALETTE)
```

---

## Future Enhancements

- [ ] Interactive filters (date range, channel, language)
- [ ] Comparison view (two channels side-by-side)
- [ ] Animated timeline (play through dates)
- [ ] 3D visualisations (sentiment × engagement × time)
- [ ] Real-time dashboard (WebSocket updates)
- [ ] Export templates (PDF reports with branding)

---

For more examples, see:
- `API_REFERENCE.md` — code examples
- `COMPREHENSIVE_GUIDE.md` — use cases
