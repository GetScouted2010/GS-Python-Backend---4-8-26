"""DRF output-contract serializers for Phase 4's 5 scoring endpoints
(04-05-PLAN.md Task 3).

The `scoring/services/*.py` functions already return well-formed dicts
(scores + component breakdowns + the shared null+reason envelope) --
these serializers are thin pass-through/validation shapes for
browsable-API rendering and contract documentation. The service layer
remains the single source of truth for response SHAPE; these serializers
must not diverge from it.

Every score field is nullable (the shared null+reason envelope: a missing
score returns `{"<field>": null, "reason": "..."}` instead of a fabricated
value), so every serializer below exposes an optional `reason` field.
Breakdown blocks use `DictField`/`JSONField` rather than strict nested
serializers because component keys are data-dependent (e.g. RMM's
`components` keys are position-specific metric names, not a fixed set).
"""

from rest_framework import serializers


class RMMSerializer(serializers.Serializer):
    rmm = serializers.FloatField(allow_null=True)
    positive = serializers.FloatField(allow_null=True, required=False)
    negative = serializers.FloatField(allow_null=True, required=False)
    components = serializers.DictField(required=False)
    reliability = serializers.CharField(allow_null=True, required=False)
    reason = serializers.CharField(required=False)


class CompatibilitySerializer(serializers.Serializer):
    compatibility_score = serializers.FloatField(allow_null=True)
    components = serializers.DictField(required=False)
    reason = serializers.CharField(required=False)


class FinancialFitSerializer(serializers.Serializer):
    predicted_fee = serializers.FloatField(allow_null=True)
    market_value = serializers.FloatField(allow_null=True, required=False)
    value_comparison = serializers.DictField(required=False)
    value_verdict = serializers.CharField(allow_null=True, required=False)
    buying_club = serializers.CharField(allow_null=True, required=False)
    reason = serializers.CharField(required=False)


class TransferProbabilitySerializer(serializers.Serializer):
    transfer_probability = serializers.FloatField(allow_null=True)
    components = serializers.DictField(required=False)
    reason = serializers.CharField(required=False)


class SummarySerializer(serializers.Serializer):
    rmm = RMMSerializer()
    compatibility = CompatibilitySerializer()
    financial_fit = FinancialFitSerializer()
    transfer_probability = TransferProbabilitySerializer()
