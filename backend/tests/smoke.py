"""Run:  cd backend && python -m tests.smoke
Proves the whole flow works on a throwaway in-memory DB.
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///./_smoke.db"
if os.path.exists("_smoke.db"):
    os.remove("_smoke.db")

from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app import importer

c = TestClient(app)
ok = 0; fail = 0
def check(label, cond):
    global ok, fail
    if cond: ok += 1; print(f"  PASS  {label}")
    else: fail += 1; print(f"  FAIL  {label}")

print("AUTH + APPROVAL")
r = c.post("/api/auth/register", json={"email": "boss@mhs.com", "name": "Boss", "password": "secret123"})
check("first user becomes admin+approved", r.json().get("role") == "admin" and r.json().get("approved") is True)

r = c.post("/api/auth/register", json={"email": "kam@mhs.com", "name": "Kam", "password": "pw12345"})
check("second user is unapproved", r.json().get("approved") is False)

r = c.post("/api/auth/login", data={"username": "kam@mhs.com", "password": "pw12345"})
check("unapproved user cannot log in (403)", r.status_code == 403)

r = c.post("/api/auth/login", data={"username": "boss@mhs.com", "password": "secret123"})
admin_tok = r.json()["access_token"]
A = {"Authorization": f"Bearer {admin_tok}"}
check("admin can log in", r.status_code == 200 and admin_tok)

users = c.get("/api/admin/users", headers=A).json()
kam_id = [u for u in users if u["email"] == "kam@mhs.com"][0]["id"]
r = c.post(f"/api/admin/users/{kam_id}/approve", headers=A)
check("admin approves the KAM", r.json().get("approved") is True)

r = c.post("/api/auth/login", data={"username": "kam@mhs.com", "password": "pw12345"})
check("KAM can log in after approval", r.status_code == 200)

print("SECURITY")
r = c.get("/api/creators")
check("no token -> 401 (no data extraction without auth)", r.status_code == 401)

print("SHEET IMPORT + DATA")
db = SessionLocal()
csv_text = ("Name,Profile Link,Followers,Category,Tier,Location,Added By,Reel Cost\n"
            "Vaishali,https://www.instagram.com/vaishalimitra.official/,196000,Fashion,Mid,Delhi,Avinash,30000\n"
            "Baviya,https://www.instagram.com/baviyaaaaaa/,22000,Beauty,Micro,Delhi,Amritansh,15000\n"
            "Lipika,https://www.instagram.com/lipika_mj/,6333,Lifestyle,Nano,Bengaluru,Shivam,3000\n")
n = importer.import_csv_text(csv_text, db, source="test", price_default="paid")
db.close()
check("imported 3 creators from CSV", n == 3)

r = c.get("/api/creators", headers=A, params={"page": 1, "page_size": 60, "sort": "followers"})
j = r.json()
check("creators list returns total=3", j["total"] == 3)
check("sorted by followers desc (Vaishali first)", j["rows"][0]["name"] == "Vaishali")
check("handle parsed from link", j["rows"][0]["handle"] == "vaishalimitra.official")

r = c.get("/api/creators", headers=A, params={"q": "lipika"})
check("search finds Lipika", r.json()["total"] == 1)

r = c.get("/api/stats", headers=A).json()
check("stats reach summed", r["reach"] == 196000 + 22000 + 6333)
check("stats price bucket paid=3", r["by_price"]["paid"] == 3)

print("EXECUTIONS + BRANDS + REPORTS")
r = c.post("/api/executions", headers=A, json={"creator_name": "Vaishali", "brand": "Mamaearth",
            "brand_category": "Beauty", "campaign": "Summer", "reels": 2, "budget": 80000, "deliv": 60000,
            "status": "Completed", "paid": True, "stage": "PO Received"})
check("execution created", r.status_code == 200)
r = c.get("/api/brands", headers=A).json()
check("brand history shows Mamaearth", r["brands"][0]["brand"] == "Mamaearth" and r["brands"][0]["completion"] == 100)
r = c.get("/api/reports/summary", headers=A).json()
check("report margin 20000", r["margin"] == 20000)

print("FINANCE / BANK")
c.post("/api/finance", headers=A, json={"kind": "income", "amount": 80000, "account": "HDFC", "category": "Brand payment", "status": "cleared"})
c.post("/api/finance", headers=A, json={"kind": "expense", "amount": 60000, "account": "HDFC", "category": "Creator payout", "status": "pending"})
r = c.get("/api/finance/summary", headers=A).json()
check("finance net = 20000", r["net"] == 20000)
check("finance pending = 60000", r["pending"] == 60000)

print("PER-USER PERMISSIONS")
r = c.post("/api/auth/login", data={"username": "kam@mhs.com", "password": "pw12345"})
K = {"Authorization": f"Bearer {r.json()['access_token']}"}
check("KAM with no permissions is blocked from creators (403)", c.get("/api/creators", headers=K).status_code == 403)
check("KAM cannot reach admin users (403)", c.get("/api/admin/users", headers=K).status_code == 403)
c.post(f"/api/admin/users/{kam_id}/permissions", headers=A, json={"permissions": ["creators.view"]})
check("after grant, KAM can view creators", c.get("/api/creators", headers=K).status_code == 200)
check("KAM still blocked from finance (403)", c.get("/api/finance", headers=K).status_code == 403)
me_k = c.get("/api/auth/me", headers=K).json()
check("KAM /me lists exactly the granted permission", me_k["permissions"] == ["creators.view"])

print("SHEET CONNECTOR (stored in app)")
r = c.post("/api/sheets", headers=A, json={"name": "With price", "csv_url": "https://example.com/x.csv", "price_default": "paid", "active": False})
sid = r.json()["id"]
check("sheet source created + stored", r.status_code == 200)
check("sheet appears in list", any(s["id"] == sid for s in c.get("/api/sheets", headers=A).json()))
check("KAM (no sheets.manage) blocked from sheets", c.get("/api/sheets", headers=K).status_code == 403)
check("sync-all runs (inactive source skipped)", c.post("/api/sheets/sync-all", headers=A).json()["ok"] is True)
check("sheet can be deleted", c.delete(f"/api/sheets/{sid}", headers=A).json()["ok"] is True)

print("SETTINGS + INSTAGRAM")
s0 = c.get("/api/settings", headers=A).json()
check("IG starts not configured", s0["ig_configured"] is False)
c.post("/api/settings", headers=A, json={"ig_business_id": "17841400000000000", "sync_minutes": 30})
s1 = c.get("/api/settings", headers=A).json()
check("sync_minutes saved", s1["sync_minutes"] == 30)
check("IG sync without token returns friendly not-configured", c.post("/api/instagram/sync", headers=A).json().get("ok") is False)
c.post("/api/settings", headers=A, json={"ig_token": "FAKE_TOKEN_FOR_TEST"})
check("IG now reports configured (token + business id set)", c.get("/api/settings", headers=A).json()["ig_configured"] is True)

print(f"\nRESULT: {ok} passed, {fail} failed")
if os.path.exists("_smoke.db"):
    os.remove("_smoke.db")
raise SystemExit(1 if fail else 0)
