import os
import sys
# Ensure project root is on sys.path for imports when pytest changes cwd
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import format_date, EMAIL_RE
import feeds


def test_format_date_basic():
    iso = "2026-09-24T01:18:47.667490+00:00"
    out = format_date(iso)
    assert "2026" in out


def test_email_re():
    assert EMAIL_RE.match("user@example.com")
    assert not EMAIL_RE.match("not-an-email")


def test_entry_published_parsing():
    entry = {"published": "Wed, 23 Sep 2026 22:47:09 +0000"}
    iso = feeds.entry_published(entry)
    assert iso is not None
    assert iso.startswith("2026-09-23")
