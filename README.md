# RSS Reader

A small Flask-based RSS reader with user accounts, shared feeds, and per-user read state. The flow is: add a feed URL, fetch and store stories once, show them to subscribed users, mark items read, and click through to the original site.

## What it does

- Sign up, log in, and log out
- Subscribe to RSS/Atom feeds by URL
- Share feeds and stories across users so the same feed is only fetched once
- Refresh all feeds you subscribe to
- Mark stories read per user
- Unsubscribe without deleting the shared feed for everyone else

## Run it

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Start the app:

   ```bash
   python3 app.py
   ```

   Optional: pick a different port for this run:

   ```bash
   PORT=9000 python3 app.py
   ```

3. Open http://127.0.0.1:8000 in your browser.

The app creates `rss.db` automatically on first run.

## Project files

- `app.py` — Flask routes, authentication flow, and SQLite queries
- `auth.py` — login helpers, password hashing, and route protection
- `feeds.py` — feed parsing helpers built around `feedparser`
- `schema.sql` — database tables for users, feeds, subscriptions, stories, and read states
- `templates/` — Jinja templates for login, signup, feeds, and story views
- `static/` — CSS and front-end assets

## Data model

- `feeds` are shared across all users
- `subscriptions` connect a user to a feed
- `stories` are deduped by feed and GUID so refreshes are idempotent
- `read_states` track whether a story has been read by a specific user

## Notes

- `app.py` runs with `debug=True` for local development only
- Set `SECRET_KEY` in production so sessions survive restarts
- Refreshing is synchronous, so a slow feed can slow down that request

## Good places to extend

- `_store_entries()` in `app.py` for tagging, filtering, or dedupe changes
- `feeds.py` for parsing tweaks or feed normalization
- `templates/` and `static/` for UI improvements

## Recent changes (automated edits)

The following concise summary lists edits made to this repository during recent maintenance and deployment preparation.

- Removed unneeded development artifacts: `node_modules/`, `package.json`, `package-lock.json`, `__pycache__/`, `.venv-1/`, `docs/`, `static/style.css.map`, and `shared.js` to shrink the repo.
- Added a lightweight health/readiness endpoint (`/health`) and template (`templates/health.html`) plus supporting styles in `static/style.css` for deployment checks.
- Dockerized the app: added `Dockerfile` and `.dockerignore`, and updated `requirements.txt` to include `gunicorn` for production WSGI.
- Added a Fly.io scaffold `fly.toml` and a GitHub Actions workflow `.github/workflows/fly-deploy.yml` for remote builds and deploys (requires `secrets.FLY_API_TOKEN`).
- Made DB handling explicit: `app.py` now reads `DATABASE_URL` and supports `REQUIRE_DATABASE_URL=1` to fail-fast in production; fallback to local `rss.db` remains for development.
- Fixed story ordering so the reading list orders by publication time (falling back to fetch time): updated SQL in `app.py`.
- Improved feed timestamp logic: `feeds.entry_published` now prefers the latest of `published` and `updated`, and returns `NULL` when unavailable so entries without timestamps don't appear as newest.

If you want these changes committed to Git with a dedicated commit message, I can create that commit for you, or run the Docker build and test the container locally next.
