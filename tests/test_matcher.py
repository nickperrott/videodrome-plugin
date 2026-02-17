"""Tests for MediaMatcher with guessit + TMDb pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from server.matcher import MediaMatcher


@pytest.mark.asyncio
class TestMediaMatcher:
    """Test MediaMatcher functionality."""

    async def test_parse_movie_filename(self, mock_guessit_movie):
        """Test parsing a movie filename with guessit."""
        matcher = MediaMatcher(tmdb_api_key="test-key")

        with patch("guessit.guessit") as mock_guessit:
            mock_guessit.return_value = mock_guessit_movie

            result = await matcher.parse_filename("Inception.2010.1080p.BluRay.x264.mkv")

            assert result["title"] == "Inception"
            assert result["year"] == 2010
            assert result["type"] == "movie"

    async def test_parse_tv_filename(self, mock_guessit_tv):
        """Test parsing a TV episode filename with guessit."""
        matcher = MediaMatcher(tmdb_api_key="test-key")

        with patch("guessit.guessit") as mock_guessit:
            mock_guessit.return_value = mock_guessit_tv

            result = await matcher.parse_filename("Breaking.Bad.S01E01.1080p.BluRay.x264.mkv")

            assert result["title"] == "Breaking Bad"
            assert result["season"] == 1
            assert result["episode"] == 1
            assert result["type"] == "episode"

    async def test_search_tmdb_movie(self, mock_tmdb_movie_result):
        """Test searching TMDb for a movie."""
        cache = AsyncMock()
        cache.get.return_value = None  # Cache miss
        cache.store = AsyncMock()

        matcher = MediaMatcher(tmdb_api_key="test-key", cache=cache)

        with patch("tmdbsimple.Search") as mock_search_class:
            mock_search = MagicMock()
            mock_search.movie.return_value = {"results": [mock_tmdb_movie_result]}
            mock_search_class.return_value = mock_search

            results = await matcher.search_tmdb(title="Inception", year=2010, media_type="movie")

            assert len(results) > 0
            assert results[0]["id"] == 27205
            assert results[0]["title"] == "Inception"
            # Verify cache was updated
            cache.store.assert_called_once()

    async def test_search_tmdb_tv(self, mock_tmdb_tv_result):
        """Test searching TMDb for a TV show."""
        cache = AsyncMock()
        cache.get.return_value = None  # Cache miss
        cache.store = AsyncMock()

        matcher = MediaMatcher(tmdb_api_key="test-key", cache=cache)

        with patch("tmdbsimple.Search") as mock_search_class:
            mock_search = MagicMock()
            mock_search.tv.return_value = {"results": [mock_tmdb_tv_result]}
            mock_search_class.return_value = mock_search

            results = await matcher.search_tmdb(title="Breaking Bad", year=2008, media_type="tv")

            assert len(results) > 0
            assert results[0]["id"] == 1396
            assert results[0]["name"] == "Breaking Bad"

    async def test_search_tmdb_uses_cache(self, mock_tmdb_movie_result):
        """Test that TMDb search uses cache when available."""
        cache = AsyncMock()
        cache.get.return_value = [mock_tmdb_movie_result]  # Cache hit

        matcher = MediaMatcher(tmdb_api_key="test-key", cache=cache)

        with patch("tmdbsimple.Search") as mock_search_class:
            mock_search = MagicMock()
            mock_search_class.return_value = mock_search

            results = await matcher.search_tmdb(title="Inception", year=2010, media_type="movie")

            # Should use cache, not call API
            assert len(results) > 0
            assert results[0]["id"] == 27205
            # Verify API was NOT called
            mock_search.movie.assert_not_called()

    async def test_search_tmdb_raises_after_retries(self):
        """search_tmdb should raise after exhausting retry attempts."""
        cache = AsyncMock()
        cache.get.return_value = None

        matcher = MediaMatcher(tmdb_api_key="test-key", cache=cache)

        with patch("tmdbsimple.Search") as mock_search_class, \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_search = MagicMock()
            mock_search.movie.side_effect = RuntimeError("temporary TMDb failure")
            mock_search_class.return_value = mock_search

            with pytest.raises(RuntimeError, match="TMDb search failed after 3 attempts"):
                await matcher.search_tmdb(title="Inception", year=2010, media_type="movie")

            assert mock_search.movie.call_count == 3
            assert mock_sleep.await_count == 2

    async def test_calculate_confidence_perfect_match(self, mock_tmdb_movie_result):
        """Test confidence scoring for a perfect match."""
        matcher = MediaMatcher(tmdb_api_key="test-key")

        parsed = {"title": "Inception", "year": 2010, "type": "movie"}
        confidence = await matcher.calculate_confidence(parsed, mock_tmdb_movie_result)

        # Perfect match should have high confidence (close to 1.0)
        assert confidence >= 0.95

    async def test_calculate_confidence_title_mismatch(self, mock_tmdb_movie_result):
        """Test confidence scoring with title mismatch."""
        matcher = MediaMatcher(tmdb_api_key="test-key")

        parsed = {"title": "Different Movie", "year": 2010, "type": "movie"}
        confidence = await matcher.calculate_confidence(parsed, mock_tmdb_movie_result)

        # Title mismatch should lower confidence
        assert confidence < 0.7

    async def test_calculate_confidence_year_mismatch(self, mock_tmdb_movie_result):
        """Test confidence scoring with year mismatch."""
        matcher = MediaMatcher(tmdb_api_key="test-key")

        parsed = {"title": "Inception", "year": 2015, "type": "movie"}
        confidence = await matcher.calculate_confidence(parsed, mock_tmdb_movie_result)

        # Year mismatch should lower confidence
        assert confidence < 0.85

    async def test_calculate_confidence_type_mismatch(self, mock_tmdb_movie_result):
        """Test confidence scoring with media type mismatch."""
        matcher = MediaMatcher(tmdb_api_key="test-key")

        parsed = {"title": "Inception", "year": 2010, "type": "episode"}
        confidence = await matcher.calculate_confidence(parsed, mock_tmdb_movie_result)

        # Type mismatch should lower confidence
        assert confidence < 0.90

    async def test_calculate_confidence_no_year_in_parsed(self, mock_tmdb_movie_result):
        """Test confidence scoring when parsed data has no year."""
        matcher = MediaMatcher(tmdb_api_key="test-key")

        parsed = {"title": "Inception", "type": "movie"}
        confidence = await matcher.calculate_confidence(parsed, mock_tmdb_movie_result)

        # Should still calculate confidence, just without year component
        assert 0.0 <= confidence <= 1.0

    async def test_construct_plex_path_movie(self, mock_tmdb_movie_result):
        """Test constructing Plex path for a movie."""
        matcher = MediaMatcher(tmdb_api_key="test-key", media_root="/data/media")

        parsed = {"title": "Inception", "year": 2010, "type": "movie"}
        path = await matcher.construct_plex_path(
            parsed=parsed,
            tmdb_result=mock_tmdb_movie_result,
            original_filename="Inception.2010.1080p.BluRay.x264.mkv"
        )

        # Movies/Movie Name (Year) {tmdb-ID}/Movie Name (Year) {tmdb-ID}.mkv
        assert "/Movies/Inception (2010) {tmdb-27205}/" in path
        assert path.endswith(".mkv")
        assert "Inception (2010) {tmdb-27205}.mkv" in path

    async def test_construct_plex_path_tv_episode(self, mock_tmdb_tv_result, mock_tmdb_episode_result):
        """Test constructing Plex path for a TV episode."""
        matcher = MediaMatcher(tmdb_api_key="test-key", media_root="/data/media")

        parsed = {
            "title": "Breaking Bad",
            "year": 2008,
            "season": 1,
            "episode": 1,
            "type": "episode"
        }

        with patch.object(matcher, "get_episode_title", return_value="Pilot"):
            path = await matcher.construct_plex_path(
                parsed=parsed,
                tmdb_result=mock_tmdb_tv_result,
                original_filename="Breaking.Bad.S01E01.mkv"
            )

            # /TV Shows/Show Name (Year)/Season 01/Show Name (Year) - s01e01 - Episode Title.mkv
            assert "/TV Shows/Breaking Bad (2008)/Season 01/" in path
            assert "Breaking Bad (2008) - s01e01 - Pilot.mkv" in path

    async def test_construct_plex_path_preserves_extension(self, mock_tmdb_movie_result):
        """Test that Plex path construction preserves file extension."""
        matcher = MediaMatcher(tmdb_api_key="test-key", media_root="/data/media")

        parsed = {"title": "Inception", "year": 2010, "type": "movie"}

        # Test with .mp4
        path_mp4 = await matcher.construct_plex_path(
            parsed=parsed,
            tmdb_result=mock_tmdb_movie_result,
            original_filename="Inception.2010.mp4"
        )
        assert path_mp4.endswith(".mp4")

        # Test with .mkv
        path_mkv = await matcher.construct_plex_path(
            parsed=parsed,
            tmdb_result=mock_tmdb_movie_result,
            original_filename="Inception.2010.mkv"
        )
        assert path_mkv.endswith(".mkv")

    async def test_match_media_full_pipeline(self, mock_guessit_movie, mock_tmdb_movie_result):
        """Test full matching pipeline from filename to Plex path."""
        cache = AsyncMock()
        cache.get.return_value = None
        cache.store = AsyncMock()

        matcher = MediaMatcher(tmdb_api_key="test-key", cache=cache, media_root="/data/media")

        with patch("guessit.guessit") as mock_guessit, \
             patch("tmdbsimple.Search") as mock_search_class:
            mock_guessit.return_value = mock_guessit_movie
            mock_search = MagicMock()
            mock_search.movie.return_value = {"results": [mock_tmdb_movie_result]}
            mock_search_class.return_value = mock_search

            result = await matcher.match_media("Inception.2010.1080p.BluRay.x264.mkv")

            assert result is not None
            assert result["parsed"]["title"] == "Inception"
            assert result["tmdb_id"] == 27205
            assert result["confidence"] >= 0.8
            assert "/Movies/Inception (2010) {tmdb-27205}/" in result["plex_path"]

    async def test_match_media_no_results(self, mock_guessit_movie):
        """Test matching when TMDb returns no results."""
        cache = AsyncMock()
        cache.get.return_value = None

        matcher = MediaMatcher(tmdb_api_key="test-key", cache=cache)

        with patch("guessit.guessit") as mock_guessit, \
             patch("tmdbsimple.Search") as mock_search_class:
            mock_guessit.return_value = mock_guessit_movie
            mock_search = MagicMock()
            mock_search.movie.return_value = {"results": []}
            mock_search_class.return_value = mock_search

            result = await matcher.match_media("Unknown.Movie.2000.mkv")

            assert result is None

    async def test_batch_match(self, mock_guessit_movie, mock_tmdb_movie_result):
        """Test batch matching multiple files."""
        cache = AsyncMock()
        cache.get.return_value = None
        cache.store = AsyncMock()

        matcher = MediaMatcher(tmdb_api_key="test-key", cache=cache, media_root="/data/media")

        filenames = [
            "Inception.2010.1080p.mkv",
            "The.Matrix.1999.720p.mkv"
        ]

        with patch("guessit.guessit") as mock_guessit, \
             patch("tmdbsimple.Search") as mock_search_class:
            mock_guessit.return_value = mock_guessit_movie
            mock_search = MagicMock()
            mock_search.movie.return_value = {"results": [mock_tmdb_movie_result]}
            mock_search_class.return_value = mock_search

            results = await matcher.batch_match(filenames)

            assert len(results) == 2
            assert all(r is not None for r in results)

    async def test_sanitize_filename(self):
        """Test filename sanitization for filesystem safety."""
        matcher = MediaMatcher(tmdb_api_key="test-key")

        # Test removing invalid characters
        result = await matcher.sanitize_filename("Movie: The Beginning/End?")
        assert ":" not in result
        assert "/" not in result
        assert "?" not in result

    async def test_title_similarity_calculation(self):
        """Test title similarity scoring."""
        matcher = MediaMatcher(tmdb_api_key="test-key")

        # Exact match
        score1 = await matcher.calculate_title_similarity("Inception", "Inception")
        assert score1 == 1.0

        # Similar titles
        score2 = await matcher.calculate_title_similarity("The Matrix", "Matrix")
        assert score2 > 0.5

        # Very different titles
        score3 = await matcher.calculate_title_similarity("Inception", "Avatar")
        assert score3 < 0.5

    async def test_get_episode_title_from_tmdb(self, mock_tmdb_episode_result):
        """Test fetching episode title from TMDb."""
        matcher = MediaMatcher(tmdb_api_key="test-key")

        with patch("tmdbsimple.TV") as mock_tv_class:
            mock_tv = MagicMock()
            mock_season = MagicMock()
            mock_episode = MagicMock()
            mock_episode.info.return_value = mock_tmdb_episode_result
            mock_season.episode.return_value = mock_episode
            mock_tv.season.return_value = mock_season
            mock_tv_class.return_value = mock_tv

            title = await matcher.get_episode_title(tv_id=1396, season=1, episode=1)

            assert title == "Pilot"

    async def test_get_episode_title_fallback(self):
        """Test episode title fallback when TMDb fails."""
        matcher = MediaMatcher(tmdb_api_key="test-key")

        with patch("tmdbsimple.TV") as mock_tv_class:
            mock_tv_class.side_effect = Exception("API Error")

            title = await matcher.get_episode_title(tv_id=1396, season=1, episode=1)

            # Should return generic title
            assert title == "Episode 1"
