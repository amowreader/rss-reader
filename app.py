"""
Bare-bones multi-user RSS aggregator.

Core loop, same as the single-user version, with one addition: feeds and stories are shared across everyone (so the same URL is only ever fetched once), and what's per-user is the *subscription* and the *read state*.

  1. Sign up / log in
  2. Add a feed URL -> subscribes you to it, fetching + creating the feed row if nobody's added it yet
  3. Refresh -> re-fetches feeds you're subscribed to, stores new stories  (deduped by guid), shared with anyone else subscribed to that feed
  4. List your stories, mark read (per-user), click through to the original
"""

import datetime
import os
import re
import sqlite3
from zoneinfo import ZoneInfo
from dateutil import parser as date_parser

from flask import Flask, g, redirect, render_template, request, session, url_for

import auth
import feeds

DATABASE = "rss.db"

app = Flask(__name__)
# In production, set a fixed SECRET_KEY env var -- otherwise every restart
# invalidates existing sessions (everyone gets logged out).
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DISPLAY_TZ = ZoneInfo("America/New_York")


# --- filters ---------------------------------------------------------

@app.template_filter("format_date")
def format_date(date_string):
    """Format date string in Eastern Time as 'MMM D, YYYY HH:MM (timezone)'"""
    if not date_string:
        return ""
    try:
        dt = date_parser.isoparse(date_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        dt = dt.astimezone(DISPLAY_TZ)
        tz_name = dt.strftime("%Z") or "UTC"
        return dt.strftime("%b %-d, %Y %H:%M") + f" ({tz_name})"
    except (ValueError, TypeError):
        return date_string


# --- db helpers ---------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        with open("schema.sql") as f:
            db.executescript(f.read())
        _run_schema_migrations(db)
        db.commit()


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


# --- auth routes ---------------------------------------------------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html", error=None)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    db = get_db()

    if not username or not password:
        return render_template("signup.html", error="Username and password are required.")

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        cur = db.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, auth.hash_password(password), now),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return render_template("signup.html", error="That username is taken.")

    auth.log_in_user(cur.lastrowid)
    return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    db = get_db()

    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if user is None or not auth.verify_password(password, user["password_hash"]):
        return render_template("login.html", error="Wrong username or password.")

    auth.log_in_user(user["id"])
    return redirect(url_for("index"))


@app.route("/logout", methods=["POST"])
def logout():
    auth.log_out_user()
    return redirect(url_for("login"))


# --- story routes ----------------------------------------------------------

@app.route("/")
def landing():
    return render_template(
        "landing.html",
        signup_count=_waitlist_signup_count(get_db()),
        form_error=None,
        form_success=None,
        email_value="",
        interest_value="",
    )


@app.route("/getting-started")
def getting_started():
    return render_template("getting_started.html")


@app.route("/sample")
def sample():
    """Public sample view used for static builds — renders the main index template
    with example feeds and stories so the frozen site shows content.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sample_feeds = [
        {"id": 1, "title": "Example Feed"},
        {"id": 2, "title": "Another Feed"},
    ]

    sample_stories = [
        {
            "id": 101,
            "image_url": "",
            "title": "Announcing the Sample Feed",
            "link": "https://example.com/sample-1",
            "feed_title": "Example Feed",
            "author": "Alice",
            "published": now,
            "is_read": False,
            "summary": "This is a short example story provided for the frozen site preview.",
        },
        {
            "id": 102,
            "image_url": "",
            "title": "More from the Example Feed",
            "link": "https://example.com/sample-2",
            "feed_title": "Another Feed",
            "author": "Bob",
            "published": now,
            "is_read": True,
            "summary": "Another sample story to show read vs unread state in the UI.",
        },
    ]

    return render_template(
        "index.html",
        stories=sample_stories,
        feeds=sample_feeds,
        show_read=True,
        selected_feed_id=None,
    )


@app.route("/waitlist", methods=["POST"])
def waitlist_signup():
    db = get_db()
    email = request.form.get("email", "").strip().lower()
    interest = request.form.get("interest", "").strip()

    if not email or not EMAIL_RE.match(email):
        return render_template(
            "landing.html",
            signup_count=_waitlist_signup_count(db),
            form_error="Please enter a valid email address.",
            form_success=None,
            email_value=email,
            interest_value=interest,
        )

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        db.execute(
            "INSERT INTO waitlist_signups (email, interest, created_at) VALUES (?, ?, ?)",
            (email, interest, now),
        )
        db.commit()
        success_message = "Thanks — you're on the list. We'll reach out soon."
    except sqlite3.IntegrityError:
        success_message = "You're already on the list. Thanks for the interest!"

    return render_template(
        "landing.html",
        signup_count=_waitlist_signup_count(db),
        form_error=None,
        form_success=success_message,
        email_value="",
        interest_value="",
    )


@app.route("/app")
@auth.require_login
def index():
    db = get_db()
    show_read = request.args.get("show_read") == "1"
    feed_id = request.args.get("feed_id", type=int)

    query = """
        SELECT stories.*, feeds.title AS feed_title,
               (read_states.id IS NOT NULL) AS is_read
        FROM stories
        JOIN feeds ON feeds.id = stories.feed_id
        JOIN subscriptions ON subscriptions.feed_id = feeds.id
            AND subscriptions.user_id = ?
        LEFT JOIN read_states ON read_states.story_id = stories.id
            AND read_states.user_id = ?
    """
    params = [g.user["id"], g.user["id"]]
    conditions = []
    if not show_read:
        conditions.append("read_states.id IS NULL")
    if feed_id:
        conditions.append("stories.feed_id = ?")
        params.append(feed_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY stories.fetched_at DESC LIMIT 200"

    stories = db.execute(query, params).fetchall()
    subscribed_feeds = _subscribed_feeds(db, g.user["id"])

    return render_template(
        "index.html",
        stories=stories,
        feeds=subscribed_feeds,
        show_read=show_read,
        selected_feed_id=feed_id,
    )


@app.route("/story/<int:story_id>/read", methods=["POST"])
@auth.require_login
def mark_read(story_id):
    db = get_db()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT OR IGNORE INTO read_states (user_id, story_id, read_at) VALUES (?, ?, ?)",
        (g.user["id"], story_id, now),
    )
    db.commit()
    return redirect(request.referrer or url_for("index"))


# --- feed routes -----------------------------------------------------------

@app.route("/feeds")
@auth.require_login
def list_feeds():
    db = get_db()
    return render_template("feeds.html", feeds=_subscribed_feeds(db, g.user["id"]), error=None)


@app.route("/feeds/add", methods=["POST"])
@auth.require_login
def add_feed():
    url = request.form.get("url", "").strip()
    db = get_db()

    if not url:
        return render_template("feeds.html", feeds=_subscribed_feeds(db, g.user["id"]), error="Enter a URL.")

    existing = db.execute("SELECT * FROM feeds WHERE url = ?", (url,)).fetchone()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if existing:
        feed_id = existing["id"]
    else:
        try:
            parsed = feeds.fetch_and_parse(url)
        except Exception as exc:
            return render_template(
                "feeds.html", feeds=_subscribed_feeds(db, g.user["id"]),
                error=f"Couldn't add feed: {exc}",
            )
        title = feeds.feed_title(parsed, url)
        cur = db.execute(
            "INSERT INTO feeds (url, title, added_at) VALUES (?, ?, ?)",
            (url, title, now),
        )
        feed_id = cur.lastrowid
        _store_entries(db, feed_id, parsed.entries)

    try:
        db.execute(
            "INSERT INTO subscriptions (user_id, feed_id, subscribed_at) VALUES (?, ?, ?)",
            (g.user["id"], feed_id, now),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return render_template(
            "feeds.html", feeds=_subscribed_feeds(db, g.user["id"]),
            error="You're already subscribed to that feed.",
        )

    return redirect(url_for("list_feeds"))


@app.route("/feeds/<int:feed_id>/unsubscribe", methods=["POST"])
@auth.require_login
def unsubscribe(feed_id):
    db = get_db()
    db.execute(
        "DELETE FROM subscriptions WHERE user_id = ? AND feed_id = ?",
        (g.user["id"], feed_id),
    )
    db.commit()
    # Note: the feed row itself is left alone -- other users may still be
    # subscribed to it. Nothing currently garbage-collects orphaned feeds
    # with zero subscribers; add that later if it matters to you.
    return redirect(url_for("list_feeds"))


@app.route("/refresh", methods=["POST"])
@auth.require_login
def refresh():
    db = get_db()
    subscribed = _subscribed_feeds(db, g.user["id"])
    for feed_row in subscribed:
        try:
            parsed = feeds.fetch_and_parse(feed_row["url"])
            _store_entries(db, feed_row["id"], parsed.entries)
        except Exception:
            # A single broken feed shouldn't block the rest from refreshing.
            continue
    return redirect(url_for("index"))


# --- shared helpers --------------------------------------------------------

def _subscribed_feeds(db, user_id):
    return db.execute(
        """
        SELECT feeds.* FROM feeds
        JOIN subscriptions ON subscriptions.feed_id = feeds.id
        WHERE subscriptions.user_id = ?
        ORDER BY feeds.title
        """,
        (user_id,),
    ).fetchall()


def _store_entries(db, feed_id, entries):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for entry in entries:
        db.execute(
            """
            INSERT OR IGNORE INTO stories
                (feed_id, guid, title, link, published, summary, author, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feed_id,
                feeds.entry_guid(entry),
                entry.get("title", "(untitled)"),
                entry.get("link", ""),
                feeds.entry_published(entry),
                feeds.entry_summary(entry),
                feeds.entry_author(entry),
                now,
            ),
        )
    db.commit()


def _waitlist_signup_count(db):
    row = db.execute("SELECT COUNT(*) AS count FROM waitlist_signups").fetchone()
    return row["count"] if row else 0


def _run_schema_migrations(db):
    story_columns = {
        row["name"]
        for row in db.execute("PRAGMA table_info(stories)").fetchall()
    }

    if "author" not in story_columns:
        db.execute("ALTER TABLE stories ADD COLUMN author TEXT")


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=int(os.environ.get("PORT", 8000)))
