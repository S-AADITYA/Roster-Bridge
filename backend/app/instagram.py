"""Instagram updates, straight into the database.

Uses the Instagram Graph API "Business Discovery". HONEST LIMITS:
  - Works ONLY for PUBLIC Business/Creator Instagram accounts.
  - Needs a long-lived token + your own Instagram Business account id
    (set them in Settings, or env IG_TOKEN / IG_BUSINESS_ID).
  - Returns followers + recent media likes/comments -> we compute engagement.
  - It does NOT return audience gender/location (Instagram never exposes that
    for other people) -> those stay manual.
"""
import os
import datetime as dt
import httpx
from . import models

GRAPH = "https://graph.facebook.com/v21.0"


def get_creds(db):
    def g(key, env):
        s = db.query(models.Setting).get(key)
        return (s.value if s and s.value else os.getenv(env, "")) or ""
    return g("ig_token", "IG_TOKEN"), g("ig_business_id", "IG_BUSINESS_ID")


def discover(handle, token, business_id):
    fields = (f"business_discovery.username({handle})"
              "{followers_count,media_count,media.limit(12){like_count,comments_count,timestamp}}")
    r = httpx.get(f"{GRAPH}/{business_id}", params={"fields": fields, "access_token": token}, timeout=30)
    r.raise_for_status()
    return r.json().get("business_discovery", {})


def sync_all(db, limit=200):
    token, business_id = get_creds(db)
    if not token or not business_id:
        return {"ok": False, "error": "Instagram not configured. Set token + business id in Settings."}
    creators = db.query(models.Creator).filter(models.Creator.handle != "").limit(limit).all()
    updated, errors = 0, []
    for c in creators:
        try:
            d = discover(c.handle, token, business_id)
            if not d:
                continue
            if d.get("followers_count"):
                c.followers = d["followers_count"]
            media = (d.get("media") or {}).get("data") or []
            if media:
                likes = [m.get("like_count", 0) or 0 for m in media]
                coms = [m.get("comments_count", 0) or 0 for m in media]
                c.avg_likes = int(sum(likes) / len(likes))
                c.avg_comments = int(sum(coms) / len(coms))
                if c.followers:
                    c.engagement = round((c.avg_likes + c.avg_comments) / c.followers * 100, 2)
            c.ig_updated = dt.datetime.utcnow().strftime("%Y-%m-%d")
            updated += 1
        except Exception as e:  # one bad handle should not stop the batch
            errors.append(f"{c.handle}: {str(e)[:80]}")
    db.commit()
    return {"ok": True, "checked": len(creators), "updated": updated, "errors": errors[:10]}
