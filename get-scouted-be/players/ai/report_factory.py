"""Provider-agnostic ReportGenerator factory (AI-05).

Calling code (the player-report / club-insights views/services) imports
ONLY get_report_generator -- never a concrete class. Swapping the LLM
provider is a two-step change: add a branch here + set LLM_PROVIDER, zero
caller edits required. Mirrors players/ai/factory.py's get_nl_query_parser()
shape exactly.
"""

from django.conf import settings

from players.ai.report_generator import ReportGenerator


def get_report_generator() -> ReportGenerator:
    """Provider-agnostic factory (AI-05). Calling code imports ONLY this;
    swapping providers = add a branch + set LLM_PROVIDER, no caller changes."""
    if settings.LLM_PROVIDER == "anthropic":
        from players.ai.anthropic_report_generator import AnthropicReportGenerator

        return AnthropicReportGenerator()
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}")
