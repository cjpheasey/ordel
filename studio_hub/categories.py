"""Standard plugin categories, their colours, and how REAPER's tags map onto them."""
import re

CATEGORIES = [
    {"key": "eq", "label": "EQ", "color": "#30D158"},
    {"key": "dynamics", "label": "Dynamics", "color": "#FF9F0A"},
    {"key": "reverb", "label": "Reverb", "color": "#64D2FF"},
    {"key": "delay", "label": "Delay", "color": "#BF5AF2"},
    {"key": "modulation", "label": "Modulation", "color": "#FF375F"},
    {"key": "saturation", "label": "Saturation", "color": "#FF453A"},
    {"key": "filter", "label": "Filter", "color": "#40C8E0"},
    {"key": "pitch", "label": "Pitch & Tuning", "color": "#FFD60A"},
    {"key": "spatial", "label": "Spatial", "color": "#5E5CE6"},
    {"key": "strip", "label": "Channel Strip", "color": "#AC8E68"},
    {"key": "mastering", "label": "Mastering", "color": "#E5C07B"},
    {"key": "restoration", "label": "Restoration", "color": "#63E6BE"},
    {"key": "utility", "label": "Utility & Analysis", "color": "#8E8E93"},
    {"key": "instruments", "label": "Instruments", "color": "#0A84FF"},
    {"key": "amp", "label": "Amp & Guitar", "color": "#FF6B3D"},
    {"key": "uncategorised", "label": "Uncategorised", "color": "#636366"},
]
KEYS = {c["key"] for c in CATEGORIES}

_TAGS = {
    "eq": "eq", "dynamics": "dynamics", "gate": "dynamics", "compressor": "dynamics", "limiter": "dynamics",
    "reverb": "reverb", "delay": "delay",
    "modulation": "modulation", "chorus": "modulation", "flanger": "modulation", "phaser": "modulation",
    "distortion": "saturation", "saturation": "saturation", "filter": "filter",
    "pitch correction": "pitch", "pitch shift": "pitch", "tuner": "pitch",
    "surround": "spatial", "spatial": "spatial", "room": "spatial", "ambisonics": "spatial",
    "channel strip": "strip", "mastering": "mastering", "restoration": "restoration",
    "analyzer": "utility", "analysis": "utility", "tools": "utility", "external": "utility",
    "midi": "utility", "network": "utility",
    "synth": "instruments", "sampler": "instruments", "drum": "instruments",
    "guitar": "amp", "bass": "amp", "amp": "amp",
}
_NAME_RULES = [
    ("eq", r"\beq\b|equali[sz]"),
    ("dynamics", r"\bcomp|\blimit|\bgate\b|\bexpander"),
    ("reverb", r"verb\b|\breverb"),
    ("delay", r"\bdelay|\becho"),
    ("modulation", r"\bchorus|\bflang|\bphas"),
    ("saturation", r"\bsat(urat)?|\bdrive|\bdist|\btape\b"),
    ("pitch", r"\btune|\bpitch"),
    ("amp", r"\bamp\b|\bcab\b"),
]


def _from_tag(tag: str) -> str | None:
    tag = tag.strip().lower()
    if tag.startswith("instrument"):
        return "instruments"
    return _TAGS.get(tag)


def resolve_category(reaper_tags: list[str], name: str, instrument: bool) -> str:
    for tag in reaper_tags:
        if key := _from_tag(tag):
            return key
    if instrument:
        return "instruments"
    for key, pattern in _NAME_RULES:
        if re.search(pattern, name, re.IGNORECASE):
            return key
    return "uncategorised"
