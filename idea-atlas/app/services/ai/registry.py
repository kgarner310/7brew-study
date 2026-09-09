"""Provider selection.

Concrete providers (Anthropic, OpenAI, Gemini, Ollama) are not implemented in
this phase -- the extraction *contract* and its safety rules are what matter
first. Adding one means writing a class satisfying :class:`AIProvider` and
registering it here; nothing else in the codebase changes.
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.ai.base import AIProvider
from app.services.ai.null import NullProvider

logger = get_logger(__name__)

ProviderFactory = Callable[[Settings], AIProvider]

_FACTORIES: dict[str, ProviderFactory] = {"null": lambda _settings: NullProvider()}


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Register a provider factory under ``name``."""
    _FACTORIES[name.lower()] = factory


def available_providers() -> tuple[str, ...]:
    """Names of every registered provider."""
    return tuple(sorted(_FACTORIES))


def get_provider(settings: Settings | None = None) -> AIProvider:
    """Return the configured provider, falling back to :class:`NullProvider`.

    An unknown or unconfigured provider degrades to null with a warning rather
    than raising: a misconfigured model must never block ingestion or the API.
    """
    settings = settings or get_settings()
    factory = _FACTORIES.get(settings.ai_provider.lower())
    if factory is None:
        logger.warning(
            "ai.provider_unknown",
            requested=settings.ai_provider,
            known=available_providers(),
            action="falling back to null provider",
        )
        return NullProvider()
    return factory(settings)
