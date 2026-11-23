"""Indicator registry.

Indicators are plain functions ``fn(df, **params) -> Series | DataFrame`` that take a
DataFrame sorted ascending by date with lower-case columns. Registering an indicator by
name lets callers (scanner, chart payload builder) look it up at runtime so a new indicator
needs no caller changes (ARCHITECTURE §4.5).
"""

from __future__ import annotations

from collections.abc import Callable

_REGISTRY: dict[str, Callable] = {}
_LOADED = False


def _ensure_loaded() -> None:
    """Import every indicator module once so its @register decorators run."""
    global _LOADED
    if _LOADED:
        return
    import apps.indicators.bollinger  # noqa: F401  (import triggers @register)
    import apps.indicators.ema  # noqa: F401
    import apps.indicators.macd  # noqa: F401
    import apps.indicators.rsi  # noqa: F401
    import apps.indicators.sma  # noqa: F401
    import apps.indicators.volume_sma  # noqa: F401

    _LOADED = True


def register(name: str) -> Callable[[Callable], Callable]:
    """Decorator that registers an indicator function under *name*."""

    def decorator(func: Callable) -> Callable:
        _REGISTRY[name] = func
        return func

    return decorator


def get_indicator(name: str) -> Callable:
    """Return the indicator callable registered under *name*.

    Built-in indicators are imported lazily so registration happens without an import
    cycle between the registry and the indicator modules.
    """
    _ensure_loaded()
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown indicator: {name!r}") from exc


def available() -> list[str]:
    """Return the sorted list of registered indicator names."""
    _ensure_loaded()
    return sorted(_REGISTRY)
