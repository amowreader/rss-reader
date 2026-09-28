CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Feeds are shared: if two users both add nytimes.com/rss, it's one row,
-- fetched once. What's per-user is the subscription, not the feed itself.
CREATE TABLE IF NOT EXISTS feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
    subscribed_at TEXT NOT NULL,
    UNIQUE(user_id, feed_id)
);

-- Stories are shared per feed, same reasoning as feeds above.
CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
    guid TEXT NOT NULL,
    title TEXT,
    link TEXT,
    published TEXT,
    summary TEXT,
    fetched_at TEXT NOT NULL,
    UNIQUE(feed_id, guid)
);

-- Read/unread is per user, since the same story can be read by many users.
CREATE TABLE IF NOT EXISTS read_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    read_at TEXT NOT NULL,
    UNIQUE(user_id, story_id)
);
