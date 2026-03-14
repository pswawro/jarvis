"""Load sensitivity profiles from data/insights_config.json."""

import json
import os
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "insights_config.json"


def load_sensitivity_profile(profile_name: str | None = None) -> dict:
    """Load a sensitivity profile by name.

    Priority: profile_name arg > INSIGHT_SENSITIVITY env var > JSON active_profile.
    Falls back to JSON active_profile if the requested profile doesn't exist.
    """
    raw = json.loads(_CONFIG_PATH.read_text())
    profiles = raw["profiles"]

    name = profile_name or os.getenv("INSIGHT_SENSITIVITY", "") or raw["active_profile"]
    if name not in profiles:
        name = raw["active_profile"]

    return profiles[name]
