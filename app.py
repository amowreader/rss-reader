"""
Bare-bones multi-user RSS aggregator.

Core loop, same as the single-user version, with one addition: feeds and
stories are shared across everyone (so the same URL is only ever fetched
once), and what's per-user is the *subscription* and the *read state*.

  1. Sign up / log in
  2. Add a feed URL -> subscribes you to it, fetching + creating the feed
     row if nobody's added it yet
  3. Refresh -> re-fetches feeds you're subscribed to, stores new stories
     (deduped by guid), shared with anyone else subscribed to that feed
  4. List your stories, mark read (per-user), click through to the original

No CSS, no JS framework, no background scheduler.
"""

import datetime
import os
import sqlite3
from dateutil import parser as date_parser

from flask import Flask, g, redirect, render_template, request, session, url_for

import auth
import feeds

DATABASE = "rss.db"

app = Flask(__name__)
# In production, set a fixed SECRET_KEY env var -- otherwise every restart
# invalidates existing sessions (everyone gets logged out).
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")


# --- filters ---------------------------------------------------------

@app.template_filter("format_date")
def format_date(date_string):
    """Format ISO date string as 'MMM D, YYYY HH:MM (timezone)'"""
    if not date_string:
        return ""
    try:
        dt = date_parser.isoparse(date_string)
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
                (feed_id, guid, title, link, published, summary, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feed_id,
                feeds.entry_guid(entry),
                entry.get("title", "(untitled)"),
                entry.get("link", ""),
                feeds.entry_published(entry),
                feeds.entry_summary(entry),
                now,
            ),
        )
    db.commit()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
