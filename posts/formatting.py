"""Turning the operator's plain text into Telegram HTML, and measuring it.

The operator writes plain text with two markers: **bold** and ~~strike~~.
"""

import html
import re
from dataclasses import dataclass

TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024

_BOLD_RE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_STRIKE_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")


@dataclass(frozen=True)
class OutgoingMessage:
    html: str
    photo_path: str | None = None


def to_telegram_html(text):
    # Escape FIRST, so anything the operator typed ("<", "&", product names
    # like "M&M's") is shown literally; only then add our own tags. Doing it
    # the other way round would escape the tags we just inserted.
    escaped = html.escape(text, quote=False)
    escaped = _BOLD_RE.sub(r"<b>\1</b>", escaped)
    return _STRIKE_RE.sub(r"<s>\1</s>", escaped)


def visible_text(text):
    """What the reader actually sees: the text without formatting markers."""
    return _STRIKE_RE.sub(r"\1", _BOLD_RE.sub(r"\1", text))


def telegram_length(text):
    # Telegram counts UTF-16 code units: most emoji count as 2.
    return len(text.encode("utf-16-le")) // 2


def compose_message(text, hashtags):
    body = text.strip()
    if hashtags:
        body += "\n\n" + " ".join(hashtags)
    return body


def length_limit(has_photo):
    return CAPTION_LIMIT if has_photo else TEXT_LIMIT


def message_length(text, hashtags):
    return telegram_length(visible_text(compose_message(text, hashtags)))
