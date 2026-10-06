"""Hashtag normalisation and building, kept free of Django so it is easy to test."""

import re

APOSTROPHES = "'`ʻʼ‘’"
_APOSTROPHE_RE = re.compile(f"[{APOSTROPHES}]")
_SEPARATOR_RE = re.compile(r"[\s\-]+")
_NON_WORD_RE = re.compile(r"[^\w]", re.UNICODE)


def normalize_hashtag(raw):
    """Turn operator input such as "#Qo'qon" or "Yangi do'kon" into "qoqon" / "yangi_dokon".

    Raises ValueError for tags Telegram would not treat as hashtags
    (empty after cleaning, or digits only).
    """
    tag = raw.strip().lower().lstrip("#")
    tag = _APOSTROPHE_RE.sub("", tag)
    tag = _SEPARATOR_RE.sub("_", tag)
    tag = _NON_WORD_RE.sub("", tag)
    tag = re.sub(r"_+", "_", tag).strip("_")
    if not tag or tag.isdigit():
        raise ValueError(f"Invalid hashtag: {raw!r}")
    return tag


def split_hashtags(text):
    """Split the operator's free-form "extra hashtags" field on commas and whitespace."""
    return [part for part in re.split(r"[\s,]+", text or "") if part.strip("#")]


def build_hashtags(rubric_tag, city_tags, extra_tags):
    """Return ["#rubric", "#city", ..., "#extra", ...] without duplicates, order preserved."""
    result = []
    for raw in [rubric_tag, *city_tags, *extra_tags]:
        if not raw:
            continue
        tag = "#" + normalize_hashtag(raw)
        if tag not in result:
            result.append(tag)
    return result
