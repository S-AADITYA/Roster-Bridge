# MyHaulStore — the REAL software (baby steps)

This is no longer a single file. This is real software with two parts:

  - **backend**  = the brain. It has the database, the login, the security,
                   and all the data (creators, executions, brands, reports, finance).
  - **frontend** = the screen you look at. It talks to the brain.

You will: (1) run it on your computer from VS Code, (2) put it online so it runs
24/7 and opens on any device, (3) edit it later and have changes go live by themselves
(that last part is "CI/CD").

Take it slow. Do one line at a time.

═══════════════════════════════════════════════════════════════
PART 0 — INSTALL 3 FREE THINGS (one time)
═══════════════════════════════════════════════════════════════
1. **Python**  → https://www.python.org/downloads/  → download → install.
   On Windows, on the first install screen, TICK the box "Add Python to PATH".
2. **VS Code** (the code editor) → https://code.visualstudio.com → install.
3. **Git** (saves + ships your code) → https://git-scm.com/downloads → install.

═══════════════════════════════════════════════════════════════
PART 1 — OPEN THE PROJECT IN VS CODE
═══════════════════════════════════════════════════════════════
1. Open **VS Code**.
2. Top menu **File → Open Folder…**
3. Choose the **myhaulstore-app** folder (this folder). Click Open.
4. If it asks "Do you trust the authors?", click **Yes, I trust**.
5. Top menu **Terminal → New Terminal**. A black box opens at the bottom.
   You will type commands there.

═══════════════════════════════════════════════════════════════
PART 2 — RUN THE BRAIN (backend)
═══════════════════════════════════════════════════════════════
In that terminal, type these lines one at a time, pressing Enter after each:

1.  Go into the backend folder:
        cd backend
2.  Install the parts it needs (only the first time):
        pip install -r requirements.txt
    (If "pip" is not found, try  pip3  instead. On Mac/Linux you may need
     python3 -m pip install -r requirements.txt )
3.  Start the brain:
        uvicorn app.main:app --reload
4.  You will see a line like:  Uvicorn running on http://127.0.0.1:8000
    🎉 The brain is alive. LEAVE THIS TERMINAL RUNNING.
    (To stop it later: click the terminal and press Ctrl + C.)

✅ Quick check: open a browser, go to  http://127.0.0.1:8000/api/health
   You should see  {"ok":true,...}

═══════════════════════════════════════════════════════════════
PART 3 — OPEN THE SCREEN (frontend)
═══════════════════════════════════════════════════════════════
The screen is the file  frontend/index.html.

EASIEST way (recommended) — Live Server:
1. In VS Code, click the **Extensions** icon on the left (four little squares).
2. Search **Live Server** (by Ritwick Dey) → click **Install**.
3. In the file list on the left, open the **frontend** folder.
4. Right-click **index.html** → **Open with Live Server**.
5. Your browser opens the login screen.

(Or just double-click index.html in your file explorer — Live Server is smoother.)

═══════════════════════════════════════════════════════════════
PART 4 — MAKE YOUR ADMIN ACCOUNT + APPROVE YOUR TEAM
═══════════════════════════════════════════════════════════════
1. On the login screen, click **Create account**.
2. Put your name, email, password → **Create account**.
3. The FIRST account ever created becomes the **ADMIN** and is logged in straight away.
4. When a teammate makes an account, they CANNOT log in until you approve them:
     - You (admin) → left menu **Admin · Approvals** → click **Approve** next to them.
     - You can also click **Make admin** to let them approve others.
5. This is your security: nobody sees any data without an approved account + login.

═══════════════════════════════════════════════════════════════
PART 5 — PUT YOUR SHEET DATA IN (no Google login needed)
═══════════════════════════════════════════════════════════════
1. Open your Google Sheet.
2. **File → Share → Publish to web**.
3. Choose the tab, choose **Comma-separated values (.csv)** → **Publish** → copy the link.
4. Bring it into the app (admin only). Two ways:
     EASY (with a tool like the browser): the app's import runs on the server.
     Use this address in your browser while logged in as admin is not enough — instead,
     from the VS Code terminal (new terminal, keep the server one running) run:
        cd backend
        python -c "from app.db import SessionLocal; from app import importer; db=SessionLocal(); print('rows:', importer.import_csv_url('PASTE_CSV_LINK', db, source='withprice', price_default='paid')); db.close()"
     Replace PASTE_CSV_LINK with your published link. price_default is paid/barter/open.
5. Refresh the app → your creators appear on the Dashboard and Creators page.
6. Repeat for each sheet (up to as many as you like — it is a database now, not 50-sheet-limited).

To keep it fresh automatically, run that import on a timer later (ask me to add a
scheduled job — every 30 min, say).

═══════════════════════════════════════════════════════════════
PART 6 — PUT IT ONLINE 24/7 (so any device opens it)  + CI/CD
═══════════════════════════════════════════════════════════════
"CI/CD" in baby words: you change the code in VS Code → you press a button →
it goes live on the internet by itself. No manual uploading.

You said "I'll keep a laptop always on." A laptop that must never sleep is fragile.
A free cloud host is better and truly 24/7. Here is the cloud way:

STEP A — put your code on GitHub
1. Make a free account at https://github.com
2. In VS Code terminal (at the project root, not inside backend):
        git init
        git add .
        git commit -m "first version"
3. On GitHub click **New repository** → name it **myhaulstore-app** → **Create**.
4. GitHub shows commands under "…or push an existing repository". Copy the two lines
   that start with  git remote add origin …  and  git push …  → paste in the terminal.
5. Refresh GitHub — your code is there. (CI runs the tests automatically — see the green tick.)

STEP B — deploy the BRAIN on Render (always-on, free)
1. Make a free account at https://render.com → sign in with GitHub.
2. Click **New +** → **Blueprint**.
3. Pick your **myhaulstore-app** repo. Render reads the render.yaml and sets it up.
4. Click **Apply**. Wait a few minutes. It gives you a URL like
        https://myhaulstore-api.onrender.com
5. That is your live brain. Test:  that-url/api/health  → {"ok":true}.

STEP C — point the screen at the live brain, then deploy the screen
1. In VS Code open  frontend/index.html.
2. Near the top change this line:
        var API_BASE = "http://127.0.0.1:8000";
   to your Render URL:
        var API_BASE = "https://myhaulstore-api.onrender.com";
3. Save. Commit + push:
        git add . ; git commit -m "point to live api" ; git push
4. Put the screen online: go to https://app.netlify.com/drop and drag the
   **frontend/index.html** file (or connect the GitHub repo in Netlify for auto-deploy).
5. Netlify gives you a link. Open it on your phone → log in → done. Any device, anywhere.

THE CI/CD LOOP (from now on):
   edit code in VS Code  →  git add . ; git commit -m "..."  ;  git push
   →  GitHub runs the tests  →  Render redeploys the brain by itself.
That is it. You change things from VS Code and they go live automatically.

═══════════════════════════════════════════════════════════════
PART 7 — BIG DATA (10–20 LAKH ROWS)
═══════════════════════════════════════════════════════════════
SQLite (the simple built-in file database) is fine for development and up to a
few lakh rows. For 10–20 lakh, switch to **Postgres** (still free on Render):
1. In Render → **New + → PostgreSQL** → create (free).
2. Copy its **Internal Database URL**.
3. In your API service → **Environment** → add  DATABASE_URL = that URL → Save.
4. Render redeploys. Now your data lives in a real database that laughs at 20 lakh rows.
The screens and graphs DON'T break, because the graphs ask the database for small
summary numbers (totals, top 8), not for all the rows. The Creators page also only
ever loads 60 rows at a time (server-side paging). That is why it stays fast and smooth.

═══════════════════════════════════════════════════════════════
WHAT YOU ASKED FOR → WHERE IT IS
═══════════════════════════════════════════════════════════════
- Give each person only certain permissions          → Admin · Access → "Permissions" per user.
  They see and can do ONLY what you tick. Admins get everything automatically.
- Password + admin-protected, approve before login   → Login + Admin·Access (Part 4).
- No data extraction without authorization           → every API route checks a permission (tested).
- The sheet connector (no more "add sheet each time") → "Sheets & Sync" page: add a sheet ONCE,
  press Sync, or set auto-sync minutes. It stays connected.
- Instagram updates per creator                       → "Sheets & Sync" page → Instagram panel →
  paste token + business id → "Sync Instagram now" (updates followers + engagement in the DB).
- Reports section                                     → Reports page.
- Finance + bank section                              → Finance & Bank page.
- 10–20 lakh data, graphs stay intact                 → Postgres + server-side paging + summaries (Part 7).
- Brand history (how much MHS did with a brand)       → Brands page → click a brand.
- Edit live from VS Code, CI/CD                        → Parts 1–3 and 6.
- Runs online 24/7, any device                        → Part 6 (cloud, better than a laptop).

PER-USER PERMISSIONS (the list you can grant):
  creators.view / creators.edit, executions.view / executions.edit, brands.view,
  reports.view, finance.view / finance.edit, sheets.manage, instagram.sync, users.manage.

AUTO-SYNC 24/7: start the server with the always-on flag so it refreshes sheets + Instagram
on the minutes you set (Sheets & Sync page). On your machine:
      MHS_AUTOSYNC=1 uvicorn app.main:app
  On Render, add an environment variable  MHS_AUTOSYNC = 1.

═══════════════════════════════════════════════════════════════
HONEST LIMITS
═══════════════════════════════════════════════════════════════
- Data now lives in a database, not "read live from the sheet every time" — that is
  the ONLY way to be fast at 20 lakh rows. Sheets become the INPUT: you publish them
  and import (Part 5), on a timer if you want. Near-live, not instant.
- This is a strong foundation, not every feature finished to the last detail. The finance
  and reports pages are real and working but basic; tell me what columns/looks you want
  and I'll grow them.
- Instagram auto-numbers still come from the IG robot (separate, 6-hour timer) and only
  for public business accounts. Audience gender/location stays manual.
