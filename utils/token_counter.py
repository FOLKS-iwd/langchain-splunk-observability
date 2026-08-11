from typing import Optional

import tiktoken


PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "gpt-4-turbo": {"prompt": 10.00, "completion": 30.00},
    "gpt-3.5-turbo": {"prompt": 0.50, "completion": 1.50},
}


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Estime le nombre de tokens sans appeler l'API."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str = "gpt-3.5-turbo",
) -> float:
    """Calcule le cout estime en USD (par million de tokens)."""
    prices = PRICING.get(model)
    if prices is None:
        return 0.0
    prompt_cost = (prompt_tokens / 1_000_000) * prices["prompt"]
    completion_cost = (completion_tokens / 1_000_000) * prices["completion"]
    return round(prompt_cost + completion_cost, 8)
