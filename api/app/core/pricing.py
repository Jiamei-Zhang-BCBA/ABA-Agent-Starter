"""Model pricing configuration. Prices in USD per 1M tokens."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    input_per_mtok: float   # USD per 1M input tokens
    output_per_mtok: float  # USD per 1M output tokens


# Anthropic pricing as of 2026-04
MODEL_PRICING: dict[str, ModelPricing] = {
    "sonnet": ModelPricing(input_per_mtok=3.0, output_per_mtok=15.0),
    "haiku": ModelPricing(input_per_mtok=0.80, output_per_mtok=4.0),
    "opus": ModelPricing(input_per_mtok=15.0, output_per_mtok=75.0),
}

_DEFAULT_PRICING = ModelPricing(input_per_mtok=3.0, output_per_mtok=15.0)


def get_model_pricing(model: str) -> ModelPricing:
    """Get pricing for a model. Strips 'cli:' prefix. Falls back to default."""
    clean = model.removeprefix("cli:").lower()
    return MODEL_PRICING.get(clean, _DEFAULT_PRICING)


def calculate_cost_cents(model: str, input_tokens: int, output_tokens: int) -> int:
    """Calculate cost in cents (1 cent = $0.01)."""
    pricing = get_model_pricing(model)
    cost_usd = (
        input_tokens * pricing.input_per_mtok / 1_000_000
        + output_tokens * pricing.output_per_mtok / 1_000_000
    )
    return max(1, round(cost_usd * 100))  # minimum 1 cent
