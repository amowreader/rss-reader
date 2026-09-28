"""
Fetching and parsing RSS/Atom feeds.

This is the one piece of logic worth keeping isolated: everything else
(routes, templates) can change shape, but "go get a feed URL and turn it
into rows" stays the same regardless of how the UI evolves.
"""

import datetime
import feedparser


def fetch_and_parse(url: str) -> feedparser.FeedParserDict:
    """Download and parse a single feed URL. Raises on network/parse failure."""
    parsed = feedparser.parse(url)
    if parsed.bozo and not parsed.entries:
        # bozo=1 just means "not strictly well-formed"; feedparser is lenient
        # and usually still extracts entries. Only treat it as fatal if we
        # got nothing at all.
        raise ValueError(f"Could not parse feed: {parsed.bozo_exception}")
    return parsed


def feed_title(parsed: feedparser.FeedParserDict, fallback_url: str) -> str:
    return parsed.feed.get("title", fallback_url)


def entry_guid(entry) -> str:
    """Best-effort stable identifier for de-duping stories."""
    return entry.get("id") or entry.get("link") or entry.get("title", "")


def entry_published(entry) -> str:
    for key in ("published", "updated"):
        if entry.get(key):
            return entry[key]
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def entry_summary(entry) -> str:
    return entry.get("summary", "") or entry.get("description", "")


def entry_image(entry):
    """Best-effort image URL from common RSS/Atom metadata."""
    candidates = []

    for key in ("media_content", "media_thumbnail"):
        value = entry.get(key)
        if isinstance(value, list):
            candidates.extend(value)
        elif value is not None:
            candidates.append(value)

    for item in candidates:
        if isinstance(item, dict):
            url = item.get("url") or item.get("href")
            if url:
                return url

    enclosures = entry.get("enclosures") or []
    for item in enclosures:
        if isinstance(item, dict):
            url = item.get("href") or item.get("url")
            if url:
                return url

    image = entry.get("image")
    if isinstance(image, dict):
        url = image.get("url") or image.get("href")
        if url:
            return url

    thumbnail = entry.get("thumbnail")
    if isinstance(thumbnail, dict):
        url = thumbnail.get("url") or thumbnail.get("href")
        if url:
            return url

    if isinstance(thumbnail, str):
        return thumbnail

    return None
