# ADR 0004: Confidence Scoring for Media Matching

## Status
Accepted

## Context
When matching filenames to TMDb entries, we need to determine how confident we are in the match. This drives whether files are auto-processed or queued for human review.

## Decision
Use a weighted scoring system (0.0 to 1.0):
- Title similarity (SequenceMatcher ratio): 40% weight
- Year match (exact=1.0, +/-1=0.8, no year=0.5): 30% weight
- TMDb popularity (normalized to 0-1 range): 15% weight
- Type match (guessit type matches TMDb media_type): 15% weight

Default auto-process threshold: 0.85 (configurable via PLEX_CONFIDENCE_THRESHOLD).

## Consequences
- High-confidence matches (>=0.85) can be auto-processed safely
- Low-confidence matches get human review through Claude
- Threshold is configurable per user's risk tolerance
- Scoring weights may need tuning based on real-world usage
