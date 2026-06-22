"""Bring Google Sheet rows into the fast database.

Two ways, both need NO Google credentials:
  1) Publish your sheet:  File -> Share -> Publish to web -> CSV -> copy the link.
     Then call import_csv_url(that_link).
  2) Local CSV file path -> import_csv_path("data.csv").

Run this on a timer (cron / GitHub Action / Render cron) to keep the DB fresh
from your sheets. The app then reads the DB (fast), not the sheet (slow).
"""
import csv
import io
import re
import httpx
from sqlalchemy.orm import Session
from . import models

SYN = {
    "mhs_id": ["mhs_id", "mhs id", "id"],
    "name": ["name", "full_name", "full name", "creator", "influencer"],
    "link": ["profile link", "profile linnk", "instagram_url", "instagram url", "link", "url", "profile"],
    "followers": ["followers", "followers_count", "follower count"],
    "niche": ["category", "niche", "category_id"],
    "language": ["language", "languages"],
    "location": ["location", "city", "location_label"],
    "gender": ["gender"],
    "platform": ["platform"],
    "tier": ["tier"],
    "added_by": ["added by", "added_by", "kam"],
    "reel_cost": ["reel cost", "reel_cost", "price_per_video", "reel price"],
    "video_cost": ["1 separate video story cost", "video story cost"],
    "story_cost": ["story reshare cost", "story cost"],
    "engagement": ["engagement", "engagement %", "engagement_rate", "er"],
    "avg_likes": ["avg likes", "average likes", "avg_likes"],
    "avg_comments": ["avg comments", "average comments", "avg_comments"],
    "ig_updated": ["ig last updated", "ig_last_updated", "last updated"],
    "ig_followers": ["ig followers", "ig_followers"],
    "reel_links": ["best reels", "reel links", "reels"],
}


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _num(v):
    s = str(v or "").replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*([kKmMlL]?)", s)
    if not m:
        return 0
    n = float(m.group(1))
    u = m.group(2).lower()
    if u == "k":
        n *= 1e3
    elif u == "m":
        n *= 1e6
    elif u == "l":
        n *= 1e5
    return int(n)


def _tier(t, f):
    t = _norm(t)
    for k in ("mega", "macro", "mid", "micro", "nano"):
        if k in t:
            return k.capitalize()
    if f >= 1_000_000: return "Mega"
    if f >= 500_000: return "Macro"
    if f >= 100_000: return "Mid"
    if f >= 10_000: return "Micro"
    return "Nano"


def _handle(link):
    m = re.search(r"instagram\.com/([^/?#]+)", str(link or ""), re.I)
    if not m:
        return ""
    h = m.group(1)
    if h.lower() in ("reel", "reels", "p", "stories", "explore"):
        return ""
    return h.lstrip("@")


def _colmap(header):
    idx = {}
    for i, h in enumerate(header):
        k = _norm(h)
        if k and k not in idx:
            idx[k] = i
    out = {}
    for field, names in SYN.items():
        out[field] = next((idx[n] for n in names if n in idx), -1)
    return out


def _ingest(rows, db: Session, source="", price_default="open", replace_source=True):
    if not rows:
        return 0
    cmap = _colmap(rows[0])
    if replace_source and source:
        db.query(models.Creator).filter(models.Creator.source_sheet == source).delete()
    added = 0
    for r in rows[1:]:
        def g(field):
            c = cmap[field]
            return r[c] if 0 <= c < len(r) else ""
        name = str(g("name")).strip()
        link = str(g("link")).strip()
        if not name and not link:
            continue
        f = _num(g("followers")) or _num(g("ig_followers"))
        reel = _num(g("reel_cost"))
        bucket = "paid" if reel else price_default
        db.add(models.Creator(
            mhs_id=str(g("mhs_id")).strip(), name=name or _handle(link), link=link,
            handle=_handle(link), followers=f, niche=str(g("niche")).strip(),
            tier=_tier(g("tier"), f), language=str(g("language")).strip(),
            location=str(g("location")).strip(), gender=str(g("gender")).strip(),
            platform=str(g("platform")).strip() or "Instagram", added_by=str(g("added_by")).strip(),
            reel_cost=reel, video_cost=_num(g("video_cost")), story_cost=_num(g("story_cost")),
            engagement=float(re.sub(r"[^\d.]", "", str(g("engagement"))) or 0),
            avg_likes=_num(g("avg_likes")), avg_comments=_num(g("avg_comments")),
            ig_updated=str(g("ig_updated")).strip(),
            price_bucket=bucket, reel_links=str(g("reel_links")).strip(), source_sheet=source,
        ))
        added += 1
    db.commit()
    return added


def import_csv_text(text, db, source="", price_default="open"):
    rows = list(csv.reader(io.StringIO(text)))
    return _ingest(rows, db, source, price_default)


def import_csv_url(url, db, source="", price_default="open"):
    r = httpx.get(url, timeout=60, follow_redirects=True)
    r.raise_for_status()
    return import_csv_text(r.text, db, source or url, price_default)


def import_csv_path(path, db, source="", price_default="open"):
    with open(path, encoding="utf-8") as fh:
        return import_csv_text(fh.read(), db, source or path, price_default)
