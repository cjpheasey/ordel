"""Subgroups inside Ordel's groups, a plugin's character within them, and guessing both from its name."""
import json
import re
from functools import cache

from .categories import resolve_category
from .paths import resource


def _subs(*pairs: tuple[str, str]) -> list[dict]:
    return [{"key": k, "label": l, "characters": []} for k, l in (*pairs, ("other", "Other"))]


SUBGROUPS = {
    "dynamics": _subs(("compressors", "Compressors"), ("limiters", "Limiters"), ("deessers", "De-essers"),
                      ("gates", "Gates & expanders"), ("multiband", "Multiband"), ("transient", "Transient shapers")),
    "eq": _subs(("parametric", "Parametric"), ("dynamic", "Dynamic EQ"), ("pultec", "Pultec-style"),
                ("console", "Console-style"), ("graphic", "Graphic")),
    "reverb": _subs(("plate", "Plate"), ("room", "Room"), ("hall", "Hall"), ("chamber", "Chamber"),
                    ("spring", "Spring"), ("shimmer", "Shimmer & ambient"), ("convolution", "Convolution")),
    "delay": _subs(("tape", "Tape"), ("analog", "Analog"), ("digital", "Digital")),
    "modulation": _subs(("chorus", "Chorus"), ("flanger", "Flanger"), ("phaser", "Phaser"),
                        ("tremolo", "Tremolo & vibrato")),
    "saturation": _subs(("tape", "Tape"), ("tube", "Tube"), ("console", "Console & transformer"),
                        ("distortion", "Distortion & fuzz"), ("lofi", "Lo-fi")),
    "instruments": _subs(("synths", "Synths"), ("samplers", "Samplers"), ("drums", "Drums"), ("keys", "Keys"),
                         ("orchestral", "Orchestral")),
}
SUBGROUPS["dynamics"][0]["characters"] = [
    {"key": k, "label": l} for k, l in (("vca", "VCA"), ("fet", "FET"), ("optical", "Optical"), ("tube", "Tube"),
                                        ("diode", "Diode bridge"), ("digital", "Digital"))]

# Checked in this order, most specific first (a "multiband compressor" is Multiband, not Compressors).
_CLUES = {
    "dynamics": [
        ("deessers", r"de-?ess|esser|pro-ds\b|\bsibil"),
        ("multiband", r"multi-?band|pro-mb\b|\bc[46]\b"),
        ("limiters", r"limit|pro-l\b|maximi[sz]|\bl[123]\b|clipper"),
        ("gates", r"gate|expander|pro-g\b"),
        ("transient", r"transient|trans-?x|envelope|\bsmack"),
        ("compressors", r"comp|1176|la-?[23]\w?\b|fairchild|\b6[67]0\b|2254|\b254|\bvca\b|\bopto|\bfet\b|\bdbx|"
                        r"\b160\b|33609|distressor|leveling"),
    ],
    "eq": [
        ("dynamic", r"dynamic eq|dyn-?eq"),
        ("pultec", r"pultec|eqp-?1|meq-?5|\bpec\b"),
        ("graphic", r"graphic|\bgeq\b"),
        ("console", r"\bssl\b|neve|1073|1081|\bapi\b|5[56]0|e-?channel|g-?eq|88rs"),
        ("parametric", r"parametric|pro-q|\bpeq\b"),
    ],
    "reverb": [
        ("convolution", r"convol|\bir\b|impulse|altiverb|space designer"),
        ("shimmer", r"shimmer|ambien|cloud|supermassive|blackhole"),
        ("plate", r"plate|\bemt\b"),
        ("spring", r"spring"),
        ("chamber", r"chamber"),
        ("hall", r"(?<!val)hall"),
        ("room", r"room"),
    ],
    "delay": [
        ("tape", r"tape|echoplex|space echo|re-?201|galaxy"),
        ("analog", r"analog|bucket|\bbbd\b|memory man|dm-?2\b"),
        ("digital", r"digital|\bpcm|\bddl"),
    ],
    "modulation": [
        ("chorus", r"chorus|dimension|\bjuno|\bce-?1\b"),
        ("flanger", r"flang"),
        ("phaser", r"phas|small stone"),
        ("tremolo", r"tremol|vibrato|\bvibe"),
    ],
    "saturation": [
        ("lofi", r"lo-?fi|bitcrush|\bbit\b|vinyl|cassette|rc-20|degrad"),
        ("tape", r"tape|\batr\b|studer|ampex|oxide|\bj37\b"),
        ("tube", r"tube|valve|triode"),
        ("console", r"console|transformer|neve|\bssl\b|\bapi\b|\bvcc\b"),
        ("distortion", r"distort|fuzz|overdrive|drive|crush|decapitator|clip"),
    ],
    "instruments": [
        ("drums", r"drum|\bkit\b|808|909|\bbeat|\bperc"),
        ("keys", r"piano|keys|organ|rhodes|wurli|\bclav"),
        ("orchestral", r"orchestr|string|brass|woodwind|choir|spitfire|\bbbc\b"),
        ("samplers", r"sampl|kontakt|sforzando|decent"),
        ("synths", r"synth|serum|vital|diva|pigments|prophet|moog|sylenth|massive|omnisphere|surge|phase plant"),
    ],
}
_TAGS = {
    "compressor": "compressors", "limiter": "limiters", "gate": "gates", "expander": "gates",
    "de-esser": "deessers", "deesser": "deessers", "multiband": "multiband", "transient": "transient",
    "chorus": "chorus", "flanger": "flanger", "phaser": "phaser", "distortion": "distortion",
    "synth": "synths", "sampler": "samplers", "drum": "drums",
}
_CHARACTER = [
    ("diode", r"2254|\b254|diode|33609"),
    ("optical", r"la-?[23]|opto|optical|cl ?1b|teletronix"),
    ("tube", r"fairchild|\b6[67]0\b|vari-?mu|tube|valve"),
    ("fet", r"1176|\bfet\b|distressor"),
    ("vca", r"\bssl\b|\bvca\b|dbx|\b160\b|2500|bus+ ?comp|g-?master|glue"),
]


def keys_of(group: str) -> set[str]:
    return {s["key"] for s in SUBGROUPS.get(group, [])}


def subgroup_from_name(group: str, name: str, reaper_tags: list[str]) -> str | None:
    if group not in SUBGROUPS:
        return None
    for key, pattern in _CLUES.get(group, []):
        if re.search(pattern, name, re.IGNORECASE):
            return key
    for tag in reaper_tags:
        if (key := _TAGS.get(tag.strip().lower())) in keys_of(group):
            return key
    return "other"


def character_from_name(name: str) -> str | None:
    return next((k for k, p in _CHARACTER if re.search(p, name, re.IGNORECASE)), None)


@cache
def _shipped() -> tuple[dict, ...]:
    return tuple(json.loads(resource("data/known_plugins.json").read_text(encoding="utf-8")))


def known_plugins() -> list[dict]:
    return list(_shipped())


@cache
def _word_start(text: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(text), re.IGNORECASE)


def _known(name: str, vendor: str, known) -> dict | None:
    vendor = vendor.lower()
    hits = [e for e in known
            if (not e["developer"] or e["developer"].lower() in vendor) and _word_start(e["name"]).search(name)]
    return max(hits, key=lambda e: len(e["name"]), default=None)


def detect(name: str, vendor: str, reaper_tags: list[str], instrument: bool, known=None) -> dict:
    """Where Ordel would put a plugin: built-in list first, then REAPER's tags and name clues."""
    if e := _known(name, vendor, _shipped() if known is None else known):
        return {"group": e["group"], "subgroup": e["subgroup"], "character": e["character"]}
    group = resolve_category(reaper_tags, name, instrument)
    sub = subgroup_from_name(group, name, reaper_tags)
    return {"group": group, "subgroup": sub, "character": character_from_name(name) if sub == "compressors" else None}
