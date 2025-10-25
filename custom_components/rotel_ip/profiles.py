from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import re

@dataclass(frozen=True)
class CommandProfile:
    key: str
    name: str
    port: int
    terminator_tx: str
    terminator_rx: str
    volume_range: Tuple[int, int]
    volume_set_template: str  # e.g., 'vol_{value:02d}!'
    commands: Dict[str, str]
    sources: Dict[str, str]


# Default Rotel ASCII profile (A12/A14 family)
PROFILES: Dict[str, CommandProfile] = {
    "rotel_ascii_v1": CommandProfile(
        key="rotel_ascii_v1",
        name="Rotel ASCII v1 (A12/A14 family)",
        port=9590,
        terminator_tx="!",
        terminator_rx="$",
        volume_range=(0, 96),
        volume_set_template="vol_{value:02d}!",
        commands={
            "power_on": "power_on!",
            "power_off": "power_off!",
            "power_query": "power?",
            "volume_query": "volume?",
            "mute_on": "mute_on!",
            "mute_off": "mute_off!",
            "mute_query": "mute?",
            "source_query": "source?",
            "push_on": "rs232_update_on!",
            "push_off": "rs232_update_off!",
            "model_query": "model?",
            "version_query": "version?",
        },
        sources={
            "cd": "cd!",
            "phono": "phono!",
            "tuner": "tuner!",
            "aux1": "aux1!",
            "aux2": "aux2!",
            "pcusb": "pcusb!",
            "coax1": "coax1!",
            "coax2": "coax2!",
            "opt1": "opt1!",
            "opt2": "opt2!",
            "bluetooth": "bluetooth!",
        },
    ),
}

# Map model strings to profile keys (case-insensitive regex)
MODEL_PATTERNS = [
    (r"(a12|a14)", "rotel_ascii_v1"),
    (r"(ra-?1572|ra-?1592)", "rotel_ascii_v1"),
]

DEFAULT_PROFILE_KEY = "rotel_ascii_v1"


def select_profile(model: Optional[str]) -> str:
    if not model:
        return DEFAULT_PROFILE_KEY
    m = model.lower()
    for pattern, key in MODEL_PATTERNS:
        if re.search(pattern, m):
            return key
    return DEFAULT_PROFILE_KEY

