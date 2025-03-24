#!/usr/bin/env bash
# push_to_github.sh
# Run this once from inside the Data-Analysis-2025 folder.
# It handles remote setup, main push, feature branch push,
# and opens the PR — all in one shot.
#
# Prerequisites:
#   1. GitHub CLI installed:  https://cli.github.com/
#   2. Authenticated:         gh auth login
#      (choose HTTPS + paste a Personal Access Token with 'repo' scope)
# ─────────────────────────────────────────────────────────────────────

set -e  # stop on any error

REMOTE="https://github.com/danmeizhou12-crypto/Data-Analysis-2025.git"

echo "── Adding remote origin ──"
git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE"

echo "── Pushing main ──"
git push -u origin main

echo "── Pushing feature branch ──"
git push -u origin feature/sentiment-enhancements

echo "── Opening Pull Request ──"
gh pr create \
  --base main \
  --head feature/sentiment-enhancements \
  --title "feat: sentiment drift detection + bilingual summary" \
  --body "## Summary

Adds two new analysis features to the sentiment pipeline:

### 1. \`detect_sentiment_drift()\`
Rolling-window algorithm that flags periods where audience sentiment shifts by more than a configurable threshold. Useful for detecting when a news event or viral moment causes a measurable change in how audiences respond to civic content.

### 2. \`plot_sentiment_drift()\`
Companion visualisation — plots the per-channel rolling mean compound score with red diamond markers at flagged drift events.

### 3. \`sentiment_by_language()\`
Convenience wrapper for EN vs. FR sentiment stratification — one-liner for the bilingual audience comparison central to this project.

## Changes
- \`sentiment/analyzer.py\`: \`detect_sentiment_drift()\`, \`sentiment_by_language()\`
- \`visualization/dashboard.py\`: \`plot_sentiment_drift()\`

## Testing
Verified on synthetic demo data (80 videos, 1,214 comments). Drift detection correctly identifies injected sentiment shifts. No breaking changes to existing pipeline functions.

Closes #1"

echo ""
echo "✅ Done. Check your repo at:"
echo "   https://github.com/danmeizhou12-crypto/Data-Analysis-2025"
echo "   https://github.com/danmeizhou12-crypto/Data-Analysis-2025/pulls"
