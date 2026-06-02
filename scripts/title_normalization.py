#!/usr/bin/env python3
"""Shared title cleanup and matching rules for the retro catalog."""

from __future__ import annotations

import html
import re


LANGUAGE_SUFFIXES = (
    "de",
    "ger",
    "german",
    "deutsch",
    "fr",
    "fre",
    "french",
    "francais",
    "it",
    "ita",
    "italian",
    "es",
    "spa",
    "spanish",
)

EDITION_TOKENS = (
    "aga",
    "ocs",
    "ecs",
    "ntsc",
    "pal",
    "cd32",
    "cdtv",
    "rtg",
    "whdload",
)

CHAR_REPLACEMENTS = {
    "æ": "ae",
    "Æ": "Ae",
    "œ": "oe",
    "Œ": "Oe",
    "ß": "ss",
    "ø": "o",
    "Ø": "O",
}

ROMAN_KEY_REPLACEMENTS = {
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
}

KEY_ALIASES = {
    "crystalsofzong": "krystalsofzong",
    "hyperaggressive": "hyperagressive",
    "ikplus": "internationalkarateplus",
    "jackthenipper2coconutcapers": "jackthenipper2incoconutcapers",
    "logcal": "logical",
    "misadventuresofflink": "flink",
    "siedlerdie": "siedler",
    "themisadventuresofflink": "flink",
    "turrican2": "turrican2thefinalfight",
    "ultima2therevengeoftheenchantress": "ultima2revengeoftheenchantress",
    "wizardryiprovinggroundsofthemadoverlord": "wizardryprovinggroundsofthemadoverlord",
    "wizardry1provinggroundsofthemadoverlord": "wizardryprovinggroundsofthemadoverlord",
}


def ascii_fold(value: str) -> str:
    for source, target in CHAR_REPLACEMENTS.items():
        value = value.replace(source, target)
    return value


def clean_title(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("+", " plus ")
    value = re.sub(r"[_]+", " ", value)
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    value = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", value)
    value = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _normalize_trailing_article(value: str) -> str:
    article_match = re.match(r"^(.+),\s+(The|A|An)$", value, flags=re.I)
    if article_match:
        return f"{article_match.group(2)} {article_match.group(1)}"
    return value


def _strip_bracketed(value: str) -> str:
    return re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", value)


def _strip_media_markers(value: str) -> str:
    media = r"(?:disk|disc|side)"
    value = re.sub(rf"\b{media}\s*[a-z0-9]+\b", " ", value, flags=re.I)
    value = re.sub(rf"\b[a-z0-9]+\s*{media}\b", " ", value, flags=re.I)
    value = re.sub(r"\bcd\s*\d+\b", " ", value, flags=re.I)
    value = re.sub(r"\bv(?:ersion)?\s*\d+(?:\.\d+)?\b", " ", value, flags=re.I)
    value = re.sub(r"\b\d+\s*mb\b", " ", value, flags=re.I)
    value = re.sub(r"(?:&|\b)(?:en|de|fr)\s*util$", " ", value, flags=re.I)
    return value


def _strip_edition_tokens(value: str) -> str:
    tokens = "|".join(map(re.escape, EDITION_TOKENS))
    return re.sub(rf"\b(?:{tokens})\b", " ", value, flags=re.I)


def _strip_language_suffix(value: str) -> str:
    suffixes = "|".join(map(re.escape, LANGUAGE_SUFFIXES))
    return re.sub(rf"\s+(?:{suffixes})$", "", value, flags=re.I).strip()


def display_title(title: str) -> str:
    value = _normalize_trailing_article(clean_title(title))
    value = _strip_bracketed(value)
    value = _strip_media_markers(value)
    value = _strip_edition_tokens(value)
    value = _strip_language_suffix(value)
    return re.sub(r"\s+", " ", value).strip()


def _drop_leading_article(value: str) -> str:
    return re.sub(r"^(the|a|an|die|der|das)\s+", "", value, flags=re.I)


def _normalize_roman_tokens(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return ROMAN_KEY_REPLACEMENTS.get(match.group(1).lower(), match.group(1))

    return re.sub(r"\b(ii|iii|iv|v|vi)\b", replace, value, flags=re.I)


def title_key(title: str, *, apply_aliases: bool = True) -> str:
    value = ascii_fold(display_title(title)).lower()
    value = _drop_leading_article(value)
    value = _normalize_roman_tokens(value)
    key = re.sub(r"[^a-z0-9]+", "", value)
    return KEY_ALIASES.get(key, key) if apply_aliases else key


def is_non_game(title: str, path: str | None = None) -> bool:
    haystack = " ".join([title or "", path or ""]).lower()
    return "zzz(notgame)" in haystack or "zzz notgame" in haystack
