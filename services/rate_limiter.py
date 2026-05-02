"""
Rate limiter in-memory simple con sliding window.

Por qué un counter custom en vez de slowapi: el límite por bot_id requiere
extraer el bot_id del body parseado, lo cual choca con la API de slowapi
(que extrae keys del Request crudo). Hacer un counter trivial nos saca del
problema y da control total.

Trade-off conocido: es por proceso, no compartido entre workers. Aceptable
en este stage (single-worker uvicorn). Si en el futuro corren multi-worker
o multi-instancia, migrar a Redis con un sliding window distribuido.
"""
import time
from collections import deque
from threading import Lock
from typing import Deque, Dict


class SlidingWindowRateLimiter:
    """
    Sliding window básico:
    - Cada bucket guarda los timestamps de los hits dentro de la ventana.
    - Al consultar, se purgan los hits viejos (fuera de la ventana) y se
      compara el count contra el límite.
    - Lock por instancia: thread-safe para el caso multi-thread de uvicorn.
    """

    def __init__(self) -> None:
        self._buckets: Dict[str, Deque[float]] = {}
        self._lock = Lock()

    def hit(self, key: str, max_requests: int, window_seconds: float) -> bool:
        """
        Registra un intento para `key`. Retorna True si está dentro del
        límite, False si lo superó (caller debe rechazar con 429).
        """
        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            # Purga timestamps fuera de la ventana — mantiene memoria acotada.
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= max_requests:
                return False
            bucket.append(now)
            return True


# Instancia singleton compartida por todos los routers.
rate_limiter = SlidingWindowRateLimiter()


def parse_rate(rate: str) -> tuple[int, float]:
    """
    Parsea formato 'N/unidad' → (max_requests, window_seconds).
    Unidades soportadas: second, minute, hour, day.

    Ejemplos:
      '60/minute' → (60, 60.0)
      '5/second'  → (5, 1.0)
    """
    try:
        n_str, unit = rate.split("/")
        n = int(n_str)
    except ValueError as e:
        raise ValueError(f"Rate format inválido: {rate!r}, esperaba 'N/unidad'") from e

    unit_map = {
        "second": 1.0,
        "seconds": 1.0,
        "minute": 60.0,
        "minutes": 60.0,
        "hour": 3600.0,
        "hours": 3600.0,
        "day": 86400.0,
        "days": 86400.0,
    }
    if unit not in unit_map:
        raise ValueError(f"Unidad inválida: {unit!r}, usá: {list(unit_map)}")
    return n, unit_map[unit]
