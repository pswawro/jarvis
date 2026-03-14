"""Role-based insight filtering."""

# Domain mapping: which data_domain values map to which scope categories
_DOMAIN_TO_SCOPE = {
    "revenue": "revenue",
    "expenses": "expenses",
    "market": "market",
}


def filter_by_role_scope(insights: list[dict], scope: dict) -> list[dict]:
    """Filter insights by role scope configuration.

    scope format: {"revenue": ["total", "ta"], "expenses": ["unit"], "market": ["brand_market"]}
    An insight is visible if its entity.type is in the scope list for its data_domain.
    """
    result = []
    for ins in insights:
        domain = ins.get("data_domain", "")
        scope_key = _DOMAIN_TO_SCOPE.get(domain)
        if scope_key is None:
            continue

        allowed_types = scope.get(scope_key, [])
        entity_type = ins.get("entity", {}).get("type", "")
        if entity_type in allowed_types:
            result.append(ins)

    return result
