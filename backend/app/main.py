"""MyHaulStore API — real backend with per-user permissions, sheet connector, Instagram sync.

Security:
  - First registered user = ADMIN (all permissions), auto-approved.
  - Everyone else = unapproved, no permissions, until an admin approves + grants them.
  - Every data route checks a specific permission. Admin bypasses all checks.
"""
import os
import threading
import time
import datetime as dt
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from .db import Base, engine, get_db, SessionLocal
from . import models, schemas, security, importer, instagram

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MyHaulStore API", version="2.0")

origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ---------------- serve the frontend (so the whole app is ONE link) ----------------
from fastapi.responses import FileResponse
_WEB_DIR = os.path.join(os.path.dirname(__file__), "web")


@app.get("/")
def _home():
    return FileResponse(os.path.join(_WEB_DIR, "index.html"))


# ---------------- helpers ----------------
def get_setting(db, key, default=""):
    s = db.query(models.Setting).get(key)
    return s.value if s else default


def set_setting(db, key, value):
    s = db.query(models.Setting).get(key)
    if s:
        s.value = value
    else:
        db.add(models.Setting(key=key, value=value))
    db.commit()


def sync_one(src: "models.SheetSource", db) -> int:
    n = importer.import_csv_url(src.csv_url, db, source=f"sheet:{src.id}", price_default=src.price_default)
    src.last_synced = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M") + " UTC"
    src.row_count = n
    db.commit()
    return n


def sync_all_sheets(db) -> int:
    total = 0
    for s in db.query(models.SheetSource).filter(models.SheetSource.active == True).all():  # noqa: E712
        try:
            total += sync_one(s, db)
        except Exception:
            pass
    return total


# ---------------- health / meta ----------------
@app.get("/api/health")
def health():
    return {"ok": True, "service": "myhaulstore", "version": "2.0"}


@app.get("/api/permissions")
def permissions_list(user: models.User = Depends(security.current_user)):
    return {"permissions": security.PERMISSIONS}


# ---------------- AUTH ----------------
@app.post("/api/auth/register", response_model=schemas.UserOut)
def register(body: schemas.RegisterIn, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(400, "Email already registered")
    first = db.query(models.User).count() == 0
    user = models.User(
        email=body.email, name=body.name,
        password_hash=security.hash_pw(body.password),
        role="admin" if first else "user",
        approved=True if first else False,
        permissions="",
    )
    db.add(user); db.commit(); db.refresh(user)
    return security.user_dict(user)


@app.post("/api/auth/login", response_model=schemas.TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form.username).first()
    if not user or not security.verify_pw(form.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    if not user.approved:
        raise HTTPException(403, "Your account is awaiting admin approval")
    return {"access_token": security.make_token(user), "token_type": "bearer", "user": security.user_dict(user)}


@app.get("/api/auth/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(security.current_user)):
    return security.user_dict(user)


# ---------------- ADMIN: users + permissions ----------------
@app.get("/api/admin/users", response_model=list[schemas.UserOut])
def list_users(admin: models.User = Depends(security.require_perm("users.manage")), db: Session = Depends(get_db)):
    return [security.user_dict(u) for u in db.query(models.User).order_by(models.User.created_at.desc()).all()]


@app.post("/api/admin/users/{uid}/approve", response_model=schemas.UserOut)
def approve_user(uid: int, admin: models.User = Depends(security.require_perm("users.manage")), db: Session = Depends(get_db)):
    u = db.query(models.User).get(uid)
    if not u:
        raise HTTPException(404, "User not found")
    u.approved = True; db.commit(); db.refresh(u)
    return security.user_dict(u)


@app.post("/api/admin/users/{uid}/role/{role}", response_model=schemas.UserOut)
def set_role(uid: int, role: str, admin: models.User = Depends(security.require_perm("users.manage")), db: Session = Depends(get_db)):
    if role not in ("admin", "user"):
        raise HTTPException(400, "role must be admin or user")
    u = db.query(models.User).get(uid)
    if not u:
        raise HTTPException(404, "User not found")
    u.role = role; db.commit(); db.refresh(u)
    return security.user_dict(u)


@app.post("/api/admin/users/{uid}/permissions", response_model=schemas.UserOut)
def set_permissions(uid: int, body: schemas.PermissionsIn,
                    admin: models.User = Depends(security.require_perm("users.manage")), db: Session = Depends(get_db)):
    u = db.query(models.User).get(uid)
    if not u:
        raise HTTPException(404, "User not found")
    valid = [p for p in body.permissions if p in security.PERMISSIONS]
    u.permissions = ",".join(sorted(set(valid)))
    db.commit(); db.refresh(u)
    return security.user_dict(u)


# ---------------- CREATORS ----------------
@app.get("/api/creators")
def creators(
    page: int = 1, page_size: int = Query(60, le=200),
    q: str = "", niche: str = "", tier: str = "", price: str = "", added_by: str = "",
    sort: str = "followers",
    user: models.User = Depends(security.require_perm("creators.view")), db: Session = Depends(get_db),
):
    qry = db.query(models.Creator)
    if q:
        like = f"%{q}%"
        qry = qry.filter(or_(models.Creator.name.ilike(like), models.Creator.niche.ilike(like),
                             models.Creator.location.ilike(like), models.Creator.handle.ilike(like)))
    if niche:    qry = qry.filter(models.Creator.niche.ilike(f"%{niche}%"))
    if tier:     qry = qry.filter(models.Creator.tier == tier)
    if price:    qry = qry.filter(models.Creator.price_bucket == price)
    if added_by: qry = qry.filter(models.Creator.added_by == added_by)
    total = qry.count()
    order = {"name": models.Creator.name.asc(), "reel_cost": models.Creator.reel_cost.desc(),
             "engagement": models.Creator.engagement.desc()}.get(sort, models.Creator.followers.desc())
    rows = qry.order_by(order).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size,
            "rows": [schemas.CreatorOut.model_validate(r).model_dump() for r in rows]}


@app.post("/api/creators", response_model=schemas.CreatorOut)
def add_creator(body: schemas.CreatorIn, user: models.User = Depends(security.require_perm("creators.edit")), db: Session = Depends(get_db)):
    c = models.Creator(**body.model_dump(), handle=_handle(body.link))
    db.add(c); db.commit(); db.refresh(c)
    return c


@app.put("/api/creators/{cid}", response_model=schemas.CreatorOut)
def edit_creator(cid: int, body: schemas.CreatorIn, user: models.User = Depends(security.require_perm("creators.edit")), db: Session = Depends(get_db)):
    c = db.query(models.Creator).get(cid)
    if not c:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    c.handle = _handle(body.link)
    db.commit(); db.refresh(c)
    return c


def _handle(link):
    import re
    m = re.search(r"instagram\.com/([^/?#]+)", str(link or ""), re.I)
    return "" if not m or m.group(1).lower() in ("reel", "reels", "p") else m.group(1).lstrip("@")


@app.get("/api/stats")
def stats(user: models.User = Depends(security.require_perm("creators.view")), db: Session = Depends(get_db)):
    C = models.Creator
    total = db.query(func.count(C.id)).scalar() or 0
    reach = db.query(func.coalesce(func.sum(C.followers), 0)).scalar() or 0
    avg_reel = db.query(func.coalesce(func.avg(C.reel_cost), 0)).filter(C.reel_cost > 0).scalar() or 0
    by_price = dict(db.query(C.price_bucket, func.count(C.id)).group_by(C.price_bucket).all())
    by_tier = dict(db.query(C.tier, func.count(C.id)).group_by(C.tier).all())
    top_niche = db.query(C.niche, func.count(C.id)).filter(C.niche != "").group_by(C.niche).order_by(func.count(C.id).desc()).limit(8).all()
    top_loc = db.query(C.location, func.count(C.id)).filter(C.location != "").group_by(C.location).order_by(func.count(C.id).desc()).limit(8).all()
    return {
        "total": total, "reach": int(reach), "avg_reel": int(avg_reel),
        "by_price": {"paid": by_price.get("paid", 0), "barter": by_price.get("barter", 0), "open": by_price.get("open", 0)},
        "by_tier": {t: by_tier.get(t, 0) for t in ["Nano", "Micro", "Mid", "Macro", "Mega"]},
        "top_niches": [[n, c] for n, c in top_niche],
        "top_locs": [[n, c] for n, c in top_loc],
    }


# ---------------- EXECUTIONS ----------------
@app.get("/api/executions", response_model=list[schemas.ExecutionOut])
def executions(user: models.User = Depends(security.require_perm("executions.view")), db: Session = Depends(get_db)):
    return db.query(models.Execution).order_by(models.Execution.created_at.desc()).all()


@app.post("/api/executions", response_model=schemas.ExecutionOut)
def add_exec(body: schemas.ExecutionIn, user: models.User = Depends(security.require_perm("executions.edit")), db: Session = Depends(get_db)):
    e = models.Execution(**body.model_dump()); db.add(e); db.commit(); db.refresh(e)
    return e


@app.put("/api/executions/{eid}", response_model=schemas.ExecutionOut)
def edit_exec(eid: int, body: schemas.ExecutionIn, user: models.User = Depends(security.require_perm("executions.edit")), db: Session = Depends(get_db)):
    e = db.query(models.Execution).get(eid)
    if not e:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump().items():
        setattr(e, k, v)
    db.commit(); db.refresh(e)
    return e


@app.delete("/api/executions/{eid}")
def del_exec(eid: int, user: models.User = Depends(security.require_perm("executions.edit")), db: Session = Depends(get_db)):
    e = db.query(models.Execution).get(eid)
    if e:
        db.delete(e); db.commit()
    return {"ok": True}


# ---------------- BRANDS ----------------
@app.get("/api/brands")
def brands(user: models.User = Depends(security.require_perm("brands.view")), db: Session = Depends(get_db)):
    out = {}
    for e in db.query(models.Execution).all():
        b = out.setdefault(e.brand or "—", {"brand": e.brand or "—", "category": e.brand_category or "",
                                            "creators": set(), "campaigns": 0, "reels": 0, "budget": 0, "comp": 0, "items": []})
        b["campaigns"] += 1; b["reels"] += e.reels or 0; b["budget"] += e.budget or 0
        if e.creator_id: b["creators"].add(e.creator_id)
        done = sum(1 for f in (e.brief, e.content, e.posted, e.invoice, e.paid) if f)
        b["comp"] += 100 if e.status == "Completed" else round(done / 5 * 100)
        if e.brand_category and not b["category"]:
            b["category"] = e.brand_category
        b["items"].append(schemas.ExecutionOut.model_validate(e).model_dump())
    res = []
    for b in out.values():
        n = b["campaigns"] or 1
        res.append({"brand": b["brand"], "category": b["category"], "creators": len(b["creators"]),
                    "campaigns": b["campaigns"], "reels": b["reels"], "budget": b["budget"],
                    "completion": round(b["comp"] / n), "items": b["items"]})
    res.sort(key=lambda x: -x["campaigns"])
    return {"brands": res}


# ---------------- REPORTS ----------------
@app.get("/api/reports/summary")
def report_summary(user: models.User = Depends(security.require_perm("reports.view")), db: Session = Depends(get_db)):
    E = models.Execution
    total_budget = db.query(func.coalesce(func.sum(E.budget), 0)).scalar() or 0
    total_deliv = db.query(func.coalesce(func.sum(E.deliv), 0)).scalar() or 0
    completed = db.query(func.count(E.id)).filter(E.status == "Completed").scalar() or 0
    active = db.query(func.count(E.id)).filter(E.status == "Active").scalar() or 0
    paid = db.query(func.count(E.id)).filter(E.paid == True).scalar() or 0  # noqa: E712
    by_brand = db.query(E.brand, func.sum(E.budget)).group_by(E.brand).order_by(func.sum(E.budget).desc()).limit(10).all()
    by_month = db.query(E.month, func.sum(E.budget)).filter(E.month != "").group_by(E.month).all()
    return {
        "total_budget": int(total_budget), "total_deliv": int(total_deliv),
        "margin": int(total_budget - total_deliv), "completed": completed, "active": active, "paid_campaigns": paid,
        "top_brands": [[b, int(v or 0)] for b, v in by_brand],
        "by_month": [[m, int(v or 0)] for m, v in by_month],
    }


# ---------------- FINANCE ----------------
@app.get("/api/finance", response_model=list[schemas.FinanceOut])
def finance(user: models.User = Depends(security.require_perm("finance.view")), db: Session = Depends(get_db)):
    return db.query(models.FinanceEntry).order_by(models.FinanceEntry.id.desc()).all()


@app.post("/api/finance", response_model=schemas.FinanceOut)
def add_finance(body: schemas.FinanceIn, user: models.User = Depends(security.require_perm("finance.edit")), db: Session = Depends(get_db)):
    f = models.FinanceEntry(**body.model_dump()); db.add(f); db.commit(); db.refresh(f)
    return f


@app.get("/api/finance/summary")
def finance_summary(user: models.User = Depends(security.require_perm("finance.view")), db: Session = Depends(get_db)):
    F = models.FinanceEntry
    income = db.query(func.coalesce(func.sum(F.amount), 0)).filter(F.kind == "income").scalar() or 0
    expense = db.query(func.coalesce(func.sum(F.amount), 0)).filter(F.kind == "expense").scalar() or 0
    pending = db.query(func.coalesce(func.sum(F.amount), 0)).filter(F.status == "pending").scalar() or 0
    by_account = db.query(F.account, func.sum(F.amount)).group_by(F.account).all()
    return {"income": int(income), "expense": int(expense), "net": int(income - expense),
            "pending": int(pending), "by_account": [[a or "—", int(v or 0)] for a, v in by_account]}


# ---------------- SHEETS CONNECTOR (managed in the app) ----------------
@app.get("/api/sheets", response_model=list[schemas.SheetOut])
def list_sheets(user: models.User = Depends(security.require_perm("sheets.manage")), db: Session = Depends(get_db)):
    return db.query(models.SheetSource).order_by(models.SheetSource.id.desc()).all()


@app.post("/api/sheets", response_model=schemas.SheetOut)
def add_sheet(body: schemas.SheetIn, user: models.User = Depends(security.require_perm("sheets.manage")), db: Session = Depends(get_db)):
    s = models.SheetSource(**body.model_dump()); db.add(s); db.commit(); db.refresh(s)
    return s


@app.delete("/api/sheets/{sid}")
def del_sheet(sid: int, user: models.User = Depends(security.require_perm("sheets.manage")), db: Session = Depends(get_db)):
    s = db.query(models.SheetSource).get(sid)
    if s:
        db.delete(s); db.commit()
    return {"ok": True}


@app.post("/api/sheets/{sid}/sync")
def sync_sheet(sid: int, user: models.User = Depends(security.require_perm("sheets.manage")), db: Session = Depends(get_db)):
    s = db.query(models.SheetSource).get(sid)
    if not s:
        raise HTTPException(404, "Sheet not found")
    try:
        n = sync_one(s, db)
        return {"ok": True, "imported": n, "last_synced": s.last_synced}
    except Exception as e:
        raise HTTPException(400, f"Sync failed: {e}")


@app.post("/api/sheets/sync-all")
def sync_all(user: models.User = Depends(security.require_perm("sheets.manage")), db: Session = Depends(get_db)):
    return {"ok": True, "imported": sync_all_sheets(db)}


# ---------------- SETTINGS (admin) ----------------
@app.get("/api/settings")
def get_settings(admin: models.User = Depends(security.require_perm("users.manage")), db: Session = Depends(get_db)):
    return {
        "ig_configured": bool(get_setting(db, "ig_token") and get_setting(db, "ig_business_id")),
        "ig_business_id": get_setting(db, "ig_business_id"),
        "sync_minutes": int(get_setting(db, "sync_minutes", "0") or 0),
    }


@app.post("/api/settings")
def save_settings(body: schemas.SettingsIn, admin: models.User = Depends(security.require_perm("users.manage")), db: Session = Depends(get_db)):
    if body.ig_token is not None and body.ig_token != "":
        set_setting(db, "ig_token", body.ig_token)
    if body.ig_business_id is not None:
        set_setting(db, "ig_business_id", body.ig_business_id)
    if body.sync_minutes is not None:
        set_setting(db, "sync_minutes", str(int(body.sync_minutes)))
    return {"ok": True}


# ---------------- INSTAGRAM SYNC ----------------
@app.post("/api/instagram/sync")
def instagram_sync(limit: int = 200, user: models.User = Depends(security.require_perm("instagram.sync")), db: Session = Depends(get_db)):
    return instagram.sync_all(db, limit=limit)


# ---------------- optional background auto-sync ----------------
def _autosync_loop():
    while True:
        try:
            db = SessionLocal()
            minutes = int(get_setting(db, "sync_minutes", "0") or 0)
            if minutes > 0:
                sync_all_sheets(db)
                try:
                    instagram.sync_all(db, limit=200)
                except Exception:
                    pass
                db.close()
                time.sleep(minutes * 60)
            else:
                db.close()
                time.sleep(60)
        except Exception:
            time.sleep(60)


if os.getenv("MHS_AUTOSYNC") == "1":
    threading.Thread(target=_autosync_loop, daemon=True).start()
