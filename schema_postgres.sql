-- Postgres schema equivalent for rss reader
-- Use identity/serial primary keys and appropriate types

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE IF NOT EXISTS feeds (
    id BIGSERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    added_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feed_id BIGINT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
    subscribed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(user_id, feed_id)
);

CREATE TABLE IF NOT EXISTS stories (
    id BIGSERIAL PRIMARY KEY,
    feed_id BIGINT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
    guid TEXT NOT NULL,
    title TEXT,
    link TEXT,
    published TIMESTAMP WITH TIME ZONE,
    summary TEXT,
    author TEXT,
    image_url TEXT,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(feed_id, guid)
);

CREATE INDEX IF NOT EXISTS stories_published_idx ON stories (published DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS stories_fetched_at_idx ON stories (fetched_at DESC);

CREATE TABLE IF NOT EXISTS read_states (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    story_id BIGINT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    read_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(user_id, story_id)
);

CREATE TABLE IF NOT EXISTS waitlist_signups (
    id BIGSERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    interest TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
