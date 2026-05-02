"""
Tests del rate limiter custom (services/rate_limiter.py).

Cubre:
- Parser de strings 'N/unidad' → (max, window).
- Bloqueo después del N-ésimo hit.
- Aislamiento entre keys distintas.
- Purga de hits viejos (sliding window).
"""
import time
from collections import deque
import pytest
from services.rate_limiter import SlidingWindowRateLimiter, parse_rate


class TestParseRate:
    def test_minute(self):
        assert parse_rate("60/minute") == (60, 60.0)

    def test_second(self):
        assert parse_rate("5/second") == (5, 1.0)

    def test_hour(self):
        assert parse_rate("1000/hour") == (1000, 3600.0)

    def test_day(self):
        assert parse_rate("10000/day") == (10000, 86400.0)

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            parse_rate("60-minute")

    def test_invalid_unit_raises(self):
        with pytest.raises(ValueError):
            parse_rate("60/century")


class TestSlidingWindowRateLimiter:
    def test_under_limit_allows(self):
        rl = SlidingWindowRateLimiter()
        for _ in range(3):
            assert rl.hit("k", max_requests=5, window_seconds=60) is True

    def test_blocks_after_limit_reached(self):
        rl = SlidingWindowRateLimiter()
        for _ in range(3):
            rl.hit("k", max_requests=3, window_seconds=60)
        # El 4º debe ser rechazado.
        assert rl.hit("k", max_requests=3, window_seconds=60) is False

    def test_keys_are_independent(self):
        rl = SlidingWindowRateLimiter()
        rl.hit("key-A", 2, 60)
        rl.hit("key-A", 2, 60)
        # key-A en límite, key-B debería estar libre.
        assert rl.hit("key-A", 2, 60) is False
        assert rl.hit("key-B", 2, 60) is True

    def test_old_hits_are_purged(self):
        """Hits fuera de la ventana no cuentan al chequear."""
        rl = SlidingWindowRateLimiter()
        # Inyecto manualmente 3 hits "viejos" (hace 100s, fuera de ventana de 60s).
        old_ts = time.monotonic() - 100
        with rl._lock:
            rl._buckets["k"] = deque([old_ts, old_ts, old_ts])
        # Aunque hay 3 hits en el bucket, todos están fuera de la ventana.
        # El nuevo hit debería pasar.
        assert rl.hit("k", max_requests=3, window_seconds=60) is True

    def test_window_resets_per_call(self):
        """
        Los hits cuentan dentro de la ventana actual, no acumulan globalmente.
        """
        rl = SlidingWindowRateLimiter()
        # Inyecto 2 hits viejos (afuera) y 1 reciente (adentro).
        now = time.monotonic()
        with rl._lock:
            rl._buckets["k"] = deque([now - 100, now - 100, now - 5])
        # Con max=3 y window=60, solo cuenta el reciente → debería aceptar 2 más.
        assert rl.hit("k", max_requests=3, window_seconds=60) is True
        assert rl.hit("k", max_requests=3, window_seconds=60) is True
        # Y el siguiente debería bloquearse.
        assert rl.hit("k", max_requests=3, window_seconds=60) is False
