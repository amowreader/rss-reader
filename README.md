# Bare-bones RSS reader

The whole app in one loop: add feed URLs → fetch/parse them → store new stories (deduped) → list them → mark read → click through to the original site.

## Run it

    pip install -r requirements.txt
    python app.py

Then open http://localhost:5000. It creates `rss.db` (SQLite) on first run.

## Files

- `app.py` — Flask routes and the SQLite queries. This is the whole
  "server."
- `feeds.py` — the only file that talks to feedparser. Keep parsing logic here so routes stay dumb.
- `schema.sql` — two tables: `feeds` and `stories`. `stories` is unique on
  `(feed_id, guid)`, which is what makes re-fetching a feed idempotent.
- `templates/` — plain Jinja templates, no `<style>`, no classes. Add your own CSS file and `<link>` it from `base.html` whenever you're ready.

## Things it deliberately doesn't do (yet)

- No automatic background refresh — there's a "Refresh all feeds" button
  that fetches synchronously. Wire up `APScheduler` or a cron hitting
  `/refresh` when you want it automatic.
- No folders/categories for feeds — `feeds` is a flat list.
- No full-text search — SQLite's `LIKE` on `stories.title`/`summary` gets
  you 80% of the way; `sqlite3`'s FTS5 extension gets you the rest.
- No auth — single-user, local use. Add a login if you're deploying this somewhere shared.
- No original-content extraction for truncated feeds — `summary` is
  whatever the feed provides.

## Where to extend

- `_store_entries()` in `app.py` is where every new story lands — a good hook point for tagging, filtering, or "train to hide" logic later.
- `feeds.py` functions are pure and easy to unit test independent of Flask.
