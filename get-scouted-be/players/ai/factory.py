"""Provider-agnostic NLQueryParser factory (AI-05).

Calling code (the search view/service) imports ONLY get_nl_query_parser --
never a concrete class. Swapping the LLM provider is a two-step change:
add a branch here + set LLM_PROVIDER, zero caller edits required.
"""

from django.conf import settings

from players.ai.base import NLQueryParser


def get_nl_query_parser() -> NLQueryParser:
    """Provider-agnostic factory (AI-05). Calling code imports ONLY this;
    swapping providers = add a branch + set LLM_PROVIDER, no caller changes."""
    if settings.LLM_PROVIDER == "anthropic":
        from players.ai.anthropic_parser import AnthropicNLQueryParser

        return AnthropicNLQueryParser()
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}")
