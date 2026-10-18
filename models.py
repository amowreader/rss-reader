"""SQLAlchemy declarative models matching the Postgres schema.

Keep these in sync with `schema_postgres.sql`. They are intentionally
straightforward so Alembic can be added later to manage migrations.
"""
from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Text,
    TIMESTAMP,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    username = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)


class Feed(Base):
    __tablename__ = "feeds"
    id = Column(BigInteger, primary_key=True)
    url = Column(Text, unique=True, nullable=False)
    title = Column(Text)
    added_at = Column(TIMESTAMP(timezone=True), nullable=False)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    feed_id = Column(BigInteger, ForeignKey("feeds.id", ondelete="CASCADE"), nullable=False)
    subscribed_at = Column(TIMESTAMP(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "feed_id", name="uq_user_feed"),)


class Story(Base):
    __tablename__ = "stories"
    id = Column(BigInteger, primary_key=True)
    feed_id = Column(BigInteger, ForeignKey("feeds.id", ondelete="CASCADE"), nullable=False)
    guid = Column(Text, nullable=False)
    title = Column(Text)
    link = Column(Text)
    published = Column(TIMESTAMP(timezone=True), nullable=True)
    summary = Column(Text)
    author = Column(Text)
    image_url = Column(Text)
    fetched_at = Column(TIMESTAMP(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint("feed_id", "guid", name="uq_feed_guid"),)

Index("ix_stories_published_desc", Story.published)
Index("ix_stories_fetched_at_desc", Story.fetched_at)


class ReadState(Base):
    __tablename__ = "read_states"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    story_id = Column(BigInteger, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    read_at = Column(TIMESTAMP(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "story_id", name="uq_user_story"),)


class WaitlistSignup(Base):
    __tablename__ = "waitlist_signups"
    id = Column(BigInteger, primary_key=True)
    email = Column(Text, unique=True, nullable=False)
    interest = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
