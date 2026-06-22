"""Tables. Indexed columns make search fast even at 20 lakh rows."""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.sql import func
from .db import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, default="")
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")        # "admin" or "user"
    permissions = Column(Text, default="")        # comma list, e.g. "creators.view,finance.view"
    approved = Column(Boolean, default=False)     # admin must approve before login
    created_at = Column(DateTime, server_default=func.now())


class Creator(Base):
    __tablename__ = "creators"
    id = Column(Integer, primary_key=True)
    mhs_id = Column(String, index=True, default="")
    name = Column(String, index=True, nullable=False)
    handle = Column(String, index=True, default="")
    link = Column(String, default="")
    followers = Column(Integer, index=True, default=0)
    niche = Column(String, index=True, default="")
    tier = Column(String, index=True, default="")
    language = Column(String, default="")
    location = Column(String, index=True, default="")
    gender = Column(String, default="")
    platform = Column(String, default="Instagram")
    added_by = Column(String, index=True, default="")
    reel_cost = Column(Integer, default=0)
    video_cost = Column(Integer, default=0)
    story_cost = Column(Integer, default=0)
    engagement = Column(Float, default=0)
    avg_likes = Column(Integer, default=0)
    avg_comments = Column(Integer, default=0)
    price_bucket = Column(String, index=True, default="open")  # paid/barter/open
    reel_links = Column(Text, default="")          # newline-separated
    ig_updated = Column(String, default="")
    source_sheet = Column(String, default="")


# composite index helps the common "search + sort by followers" query
Index("ix_creator_search", Creator.niche, Creator.tier, Creator.price_bucket)


class Execution(Base):
    __tablename__ = "executions"
    id = Column(Integer, primary_key=True)
    creator_id = Column(Integer, ForeignKey("creators.id"), index=True, nullable=True)
    creator_name = Column(String, default="")
    brand = Column(String, index=True, default="")
    brand_category = Column(String, default="")
    campaign = Column(String, default="")
    stage = Column(String, default="Shortlisted")
    month = Column(String, default="")
    reels = Column(Integer, default=0)
    stories = Column(Integer, default=0)
    budget = Column(Integer, default=0)
    deliv = Column(Integer, default=0)
    status = Column(String, default="Active")     # Active/Completed/Cancelled
    brief = Column(Boolean, default=False)
    content = Column(Boolean, default=False)
    posted = Column(Boolean, default=False)
    invoice = Column(Boolean, default=False)
    paid = Column(Boolean, default=False)
    notes = Column(String, default="")
    created_at = Column(DateTime, server_default=func.now())


class FinanceEntry(Base):
    __tablename__ = "finance"
    id = Column(Integer, primary_key=True)
    date = Column(String, index=True, default="")
    kind = Column(String, index=True, default="income")   # income/expense
    category = Column(String, default="")                 # e.g. Brand payment, Creator payout, Bank fee
    brand = Column(String, default="")
    creator_name = Column(String, default="")
    amount = Column(Integer, default=0)
    account = Column(String, default="")                  # bank account label
    status = Column(String, default="pending")            # pending/cleared
    ref = Column(String, default="")                      # invoice / UTR
    notes = Column(String, default="")
    created_at = Column(DateTime, server_default=func.now())


class SheetSource(Base):
    """A Google Sheet connected ONCE here. Add it, then sync it (or auto-sync).
    Solves 'every time I have to add the sheet' — it is stored and reused."""
    __tablename__ = "sheet_sources"
    id = Column(Integer, primary_key=True)
    name = Column(String, default="")
    csv_url = Column(Text, nullable=False)                # published-to-web CSV link
    price_default = Column(String, default="open")        # paid/barter/open
    active = Column(Boolean, default=True)
    last_synced = Column(String, default="")
    row_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class Setting(Base):
    """Key/value store for credentials & config (e.g. Instagram token)."""
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(Text, default="")
