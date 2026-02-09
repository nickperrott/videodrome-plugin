# ADR 0002: guessit + TMDb for Media Identification

## Status
Accepted

## Context
When media files arrive with arbitrary filenames (e.g., `The.Matrix.1999.1080p.BluRay.x264.mkv`), we need to identify the content and construct Plex-compliant names.

Options considered:
1. guessit (filename parsing) + TMDb (verification/metadata)
2. Manual regex patterns
3. Plex's own scanner/agent

## Decision
Use guessit for initial filename parsing and TMDb for verification and canonical metadata. guessit handles the messy world of media file naming conventions (release groups, quality tags, codecs) and extracts structured data. TMDb provides the authoritative title, year, and IDs.

## Consequences
- guessit handles most filename patterns out of the box
- TMDb provides authoritative metadata and IDs for Plex enhanced matching
- Requires a TMDb API key (free for non-commercial use)
- Need a confidence scoring system to handle ambiguous matches
- Should cache TMDb results to avoid rate limiting
