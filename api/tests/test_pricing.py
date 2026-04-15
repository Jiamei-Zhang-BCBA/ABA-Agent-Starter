# api/tests/test_pricing.py
from app.core.pricing import get_model_pricing, calculate_cost_cents


def test_get_known_model_pricing():
    pricing = get_model_pricing("sonnet")
    assert pricing is not None
    assert pricing.input_per_mtok > 0
    assert pricing.output_per_mtok > 0


def test_get_unknown_model_returns_default():
    pricing = get_model_pricing("nonexistent")
    assert pricing is not None  # returns default pricing


def test_calculate_cost_cents():
    # sonnet: $3/Mtok input, $15/Mtok output
    cost = calculate_cost_cents("sonnet", input_tokens=1000, output_tokens=500)
    assert isinstance(cost, int)
    assert cost > 0


def test_calculate_cost_cli_model():
    # CLI model names like "cli:sonnet" should resolve to "sonnet"
    cost = calculate_cost_cents("cli:sonnet", input_tokens=1000, output_tokens=500)
    assert cost > 0
