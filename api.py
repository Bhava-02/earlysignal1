"""
EarlySignal web server: serves the React dashboard and the few things a static page cannot do on its own.

    uvicorn api:app --host 0.0.0.0 --port 7860        (after: cd frontend && npm run build)

What it adds to the React app:
  * Data sources: connect read-only to the college ERP / Moodle databases (or the demo server), map the tables,
    sync and rebuild; or upload the Excel template, see the checks, and rebuild. Same code as the Round 1 console
    (src/connector.py, src/simple_upload.py, src/build.py, src/sync.py).
  * Live data: the dashboard loads the latest data file from /api/bundle, so a sync or upload shows on every page.
  * Sign-in codes by email: sent through Brevo's email API (works on Hugging Face, which blocks mail ports) or an
    SMTP account, and checked here. Codes by SMS and "Continue with Google" run in the browser through Firebase.

Settings (environment variables, e.g. Hugging Face Space secrets). All optional:
  EARLYSIGNAL_ADMIN_KEY      if set, changing data (test, sync, upload, reset) needs this key
  BREVO_API_KEY, EMAIL_FROM  email sign-in codes through Brevo (EMAIL_FROM = a sender verified in Brevo)
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM     or through SMTP (e.g. smtp.gmail.com, 587)
  FIREBASE_API_KEY, FIREBASE_AUTH_DOMAIN, FIREBASE_PROJECT_ID, FIREBASE_APP_ID    Google sign-in and SMS codes
  EARLYSIGNAL_ADMIN_EMAIL    shown in the assistant's "please mail your queries to" reply
  EARLYSIGNAL_CORS_ORIGINS   comma-separated sites allowed to call this server from another address

Safety: database logins are read-only and SELECT-only (connector.check_sql); passwords are used for one request or
one sync and never written to disk; codes are stored only as hashes, expire in 5 minutes and allow 5 tries.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import smtplib
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import config as C
from src import connector as cn
from src import demo_server
from src import simple_upload as su

ROOT = C.ROOT
DIST = ROOT / "frontend" / "dist"
BUNDLE = ROOT / "data" / "processed" / "web" / "bundle_r1.json"
JOBS_DIR = ROOT / "data" / "jobs"
EXAMPLE = ROOT / "assets" / "example_college_CSE.xlsx"
VERSION = "3.1.0"
os.environ["EARLYSIGNAL_WEB"] = "1"  # every rebuild also writes the React data file



@asynccontextmanager
async def lifespan(_app):
    if not BUNDLE.exists():  # first start (or the data was cleared): build it in the background
        try:
            _start("startup", [([sys.executable, "-m", "src.pipeline", "--web"], None)])
        except HTTPException:
            pass
    yield


app = FastAPI(title="EarlySignal", version=VERSION, docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=2000)
_origins = [o.strip() for o in os.environ.get("EARLYSIGNAL_CORS_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "X-Admin-Key"])


def india_now():
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))


def need_key(x_admin_key: str = Header(default="")):
    """Changing data needs the admin key when one is set on the server."""
    want = os.environ.get("EARLYSIGNAL_ADMIN_KEY", "")
    if want and not hmac.compare_digest(want, x_admin_key or ""):
        raise HTTPException(401, "This server needs the admin key to change data. Enter it at the top of the page.")


def smtp_ready():
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASSWORD"))


def brevo_ready():
    return bool(os.environ.get("BREVO_API_KEY") and (os.environ.get("EMAIL_FROM") or os.environ.get("SMTP_FROM")))


def email_ready():
    return brevo_ready() or smtp_ready()


def firebase_cfg():
    if not os.environ.get("FIREBASE_API_KEY"):
        return None
    return {k: os.environ.get(e, "") for k, e in (("apiKey", "FIREBASE_API_KEY"), ("authDomain", "FIREBASE_AUTH_DOMAIN"),
                                                  ("projectId", "FIREBASE_PROJECT_ID"), ("appId", "FIREBASE_APP_ID"))}


def send_email(to, subject, text, html):
    """Send one email through Brevo's HTTPS API when set up, otherwise through SMTP. Raises on failure."""
    if brevo_ready():
        sender = os.environ.get("EMAIL_FROM") or os.environ["SMTP_FROM"]
        body = dict(sender=dict(email=sender, name=os.environ.get("EMAIL_FROM_NAME", "EarlySignal")), to=[dict(email=to)],
                    subject=subject, textContent=text, htmlContent=html)
        req = urllib.request.Request(os.environ.get("BREVO_API_URL", "https://api.brevo.com/v3/smtp/email"),
                                     data=json.dumps(body).encode(), method="POST",
                                     headers={"api-key": os.environ["BREVO_API_KEY"], "content-type": "application/json",
                                              "accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                r.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:200]
            raise RuntimeError(f"Brevo answered {e.code}: {detail}") from None
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("SMTP_FROM") or os.environ["SMTP_USER"]
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    port = int(os.environ.get("SMTP_PORT", "587"))
    if port == 465:
        server = smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, timeout=15)
    else:
        server = smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=15)
        server.starttls()
    with server:
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        server.send_message(msg)


# ---------------------------------------------------------------- data the dashboard shows
_cache = {"mtime": None, "data": None}


def bundle():
    if not BUNDLE.exists():
        return None
    m = BUNDLE.stat().st_mtime
    if _cache["mtime"] != m:
        _cache.update(mtime=m, data=json.loads(BUNDLE.read_text()))
    return _cache["data"]


def settings_source():
    try:
        return json.loads(C.SETTINGS_FILE.read_text()).get("source", {}) if C.SETTINGS_FILE.exists() else {}
    except Exception:
        return {}


@app.get("/api/health")
def health():
    return dict(app="earlysignal", version=VERSION, email_codes=email_ready(), firebase=bool(firebase_cfg()),
                admin_key=bool(os.environ.get("EARLYSIGNAL_ADMIN_KEY")), data=BUNDLE.exists(), job=_running_summary())


@app.get("/api/bundle")
def get_bundle():
    if not BUNDLE.exists():
        raise HTTPException(503, "The data is being rebuilt. Try again in a minute.")
    return FileResponse(BUNDLE, media_type="application/json", headers={"Cache-Control": "no-store"})


@app.get("/api/config")
def runtime_config():
    """Browser settings: Firebase (Google sign-in, SMS codes) and the admin's email, from the server's environment."""
    cfg = {}
    if firebase_cfg():
        cfg["firebase"] = firebase_cfg()
        if os.environ.get("FIREBASE_AUTH_EMULATOR_HOST"):  # local testing with the Firebase emulator only
            cfg["firebase"]["emulator"] = "http://" + os.environ["FIREBASE_AUTH_EMULATOR_HOST"]
    if os.environ.get("EARLYSIGNAL_ADMIN_EMAIL"):
        cfg["adminEmail"] = os.environ["EARLYSIGNAL_ADMIN_EMAIL"]
    return JSONResponse(cfg, headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- background jobs (one at a time)
JOBS, LOCK = {}, threading.Lock()
KEEP = re.compile(r"^(Traceback|  File|    )")


def _running():
    return next((j for j in JOBS.values() if j["state"] == "running"), None)


def _running_summary():
    j = _running()
    return dict(id=j["id"], kind=j["kind"]) if j else None


def _start(kind, steps, after=None):
    """steps: list of (command list, extra env) run one after another; after(job) runs at the end (in the thread)."""
    with LOCK:
        if _running():
            raise HTTPException(409, "Another update is running. Wait for it to finish.")
        jid = secrets.token_hex(6)
        job = dict(id=jid, kind=kind, state="running", lines=[], rc=None, result=None, started=time.time())
        JOBS[jid] = job
        for old in sorted(JOBS, key=lambda k: JOBS[k]["started"])[:-10]:
            JOBS.pop(old, None)

    def work():
        rc = 0
        try:
            for item in steps:
                if callable(item):
                    item(job)
                    continue
                cmd, env = item
                proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                        env=dict(os.environ, PYTHONUNBUFFERED="1", **(env or {})))
                for line in proc.stdout:
                    line = line.rstrip()
                    if line and not KEEP.match(line):
                        job["lines"].append(line[:400])
                rc = proc.wait()
                if rc != 0:
                    break
        except Exception as e:  # report, never crash the server
            job["lines"].append(f"Stopped: {type(e).__name__}: {e}")
            rc = 1
        job["rc"] = rc
        try:
            if after:
                after(job)
        except Exception as e:
            job["lines"].append(f"Could not read the results: {e}")
        if job["state"] == "running":
            job["state"] = "done" if rc == 0 else "failed"
        job["ended"] = time.time()

    threading.Thread(target=work, daemon=True).start()
    return dict(job=jid)


@app.get("/api/jobs/{jid}")
def job_status(jid: str, since: int = 0):
    j = JOBS.get(jid)
    if not j:
        raise HTTPException(404, "No such job.")
    return dict(id=jid, kind=j["kind"], state=j["state"], lines=j["lines"][since:], next=len(j["lines"]),
                result=j["result"] if j["state"] != "running" else None)


# ---------------------------------------------------------------- data sources: overview
@app.get("/api/source")
def source():
    b = bundle() or {}
    meta = b.get("meta", {})
    conn = cn.load_conn()
    queries = conn.get("queries") or {}
    slots = [dict(slot=k, server=v[0], sheet=v[1], need=v[2], label=v[3], default=cn.DEFAULT_SQL[k],
                  sql=queries.get(k, cn.DEFAULT_SQL[k]), edited=k in queries) for k, v in cn.SLOTS.items()]
    return dict(using_sample=meta.get("using_sample", True), college=meta.get("college", ""),
                built_at=meta.get("built_at", ""), source=settings_source(), demo_exists=demo_server.exists(),
                conn={k: conn.get(k) for k in ("mode", "erp", "lms", "college_name")},
                dialects=[dict(name=k, port=v[1]) for k, v in cn.DIALECTS.items()], slots=slots,
                sheets=[dict(name=k, required=v["required"], per=v["per"], why=v["why"]) for k, v in su.SHEETS.items()],
                example=EXAMPLE.exists(), job=_running_summary())


# ---------------------------------------------------------------- college server
class Server(BaseModel):
    dialect: str
    host: str = ""
    port: int | None = None
    database: str = ""
    username: str = ""


class Conn(BaseModel):
    mode: str = "server"  # "demo" or "server"
    erp: Server | None = None
    lms: Server | None = None
    passwords: dict = {}


def _cfgs(c: Conn):
    if c.mode == "demo":
        if not demo_server.exists():
            raise HTTPException(400, "Start the demo server first.")
        return cn.demo_cfgs()
    out = {}
    for k in ("erp", "lms"):
        s = getattr(c, k)
        if s and s.database.strip():
            if s.dialect not in cn.DIALECTS:
                raise HTTPException(400, f"Unknown database type: {s.dialect}")
            if s.dialect == "SQLite file":
                raise HTTPException(400, "SQLite files can only be used by the demo server here.")
            out[k] = dict(dialect=s.dialect, host=s.host.strip(), port=int(s.port or cn.DIALECTS[s.dialect][1] or 0),
                          database=s.database.strip(), username=s.username.strip())
    return out


@app.post("/api/demo/start", dependencies=[Depends(need_key)])
def demo_start():
    return _start("demo", [([sys.executable, "-m", "src.demo_server"], None)])


@app.get("/api/demo/tables")
def demo_tables():
    if not demo_server.exists():
        return dict(tables=[])
    return dict(tables=[dict(db=db, table=t, rows=n) for (db, t), n in demo_server.tables().items()])


@app.post("/api/test", dependencies=[Depends(need_key)])
def test_connection(c: Conn):
    cfgs = _cfgs(c)
    if not cfgs.get("erp"):
        raise HTTPException(400, "Fill in the ERP database details first.")
    out = {}
    for k, cfg in cfgs.items():
        ok, msg, tables = cn.test(cfg, c.passwords.get(k, ""))
        out[k] = dict(ok=ok, message=msg, tables=tables[:400])
    if c.mode == "server":
        conn = cn.load_conn()
        cn.save_conn(dict(conn, mode="server", erp=cfgs.get("erp"), lms=cfgs.get("lms")))
    return out


class Peek(Conn):
    server: str = "erp"
    sql: str = ""
    table: str = ""


@app.post("/api/preview", dependencies=[Depends(need_key)])
def preview(p: Peek):
    cfgs = _cfgs(p)
    if p.server not in cfgs:
        raise HTTPException(400, "Connect to that database first.")
    if p.table:
        if not re.fullmatch(r"[A-Za-z0-9_$.]+", p.table):
            raise HTTPException(400, "Unusual table name; open it with a query instead.")
        sql = f"SELECT * FROM {p.table}"
    else:
        sql = p.sql
    df, secs, err = cn.preview(cfgs[p.server], p.passwords.get(p.server, ""), sql)
    if err:
        return dict(ok=False, error=err, secs=secs)
    data = json.loads(df.to_json(orient="split", date_format="iso", default_handler=str))
    return dict(ok=True, secs=secs, sql=sql, columns=[str(c) for c in data["columns"]], rows=data["data"])


class Query(BaseModel):
    slot: str
    sql: str | None = None  # None puts the default back


@app.post("/api/queries", dependencies=[Depends(need_key)])
def save_query(q: Query):
    if q.slot not in cn.SLOTS:
        raise HTTPException(400, "Unknown query.")
    conn = cn.load_conn()
    queries = dict(conn.get("queries") or {})
    if q.sql is None or q.sql.strip() == cn.DEFAULT_SQL[q.slot]:
        queries.pop(q.slot, None)
    else:
        try:
            queries[q.slot] = cn.check_sql(q.sql) and q.sql.strip()
        except ValueError as e:
            raise HTTPException(400, str(e))
    cn.save_conn(dict(conn, queries=queries))
    return dict(ok=True, edited=q.slot in queries)


class Sync(Conn):
    college_name: str = ""


@app.post("/api/sync", dependencies=[Depends(need_key)])
def sync(s: Sync):
    demo = s.mode == "demo"
    cfgs = _cfgs(s)
    if not demo and not cfgs.get("erp"):
        raise HTTPException(400, "Fill in the ERP database details first.")
    conn = cn.load_conn()
    name = s.college_name.strip() or ("Demo College" if demo else "My College")
    cn.save_conn(dict(conn, mode="demo" if demo else "server", college_name=name,
                      **({} if demo else {"erp": cfgs.get("erp"), "lms": cfgs.get("lms")})))
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    out = JOBS_DIR / f"sync_{secrets.token_hex(4)}.json"
    env = {"EARLYSIGNAL_ERP_PASSWORD": s.passwords.get("erp", ""), "EARLYSIGNAL_LMS_PASSWORD": s.passwords.get("lms", "")}

    def after(job):
        res = json.loads(out.read_text()) if out.exists() else None
        out.unlink(missing_ok=True)
        if res is None:
            job["result"] = dict(ok=False, built=False, errors=["The sync stopped before it finished. The dashboard "
                                                                "still shows the previous data."])
            job["state"] = "failed"
            return
        res.pop("log", None) if res.get("built") else None
        job["result"] = res
        if res.get("built") and demo:
            sim = demo_server.load_sim()
            if sim:
                demo_server.save_sim(dict(sim, synced=True))
        job["state"] = "done" if res.get("built") else "failed"

    return _start("sync", [([sys.executable, "-m", "src.sync", "--json", str(out)] + (["--demo"] if demo else []), env)],
                  after)


# ---------------------------------------------------------------- prove it's live (demo server only)
def _snap(s):
    v = s["v"]
    return dict(att=v.get("att_pct"), lms=v.get("lms_avg"), asg=100 * (v.get("asg_rate") or 0),
                proj=v.get("projected_attendance"), risk=s.get("ar"), score=v.get("success_score"),
                segment=s.get("seg"), reason=(s.get("reasons") or ["No warning signs"])[0])


@app.get("/api/demo/live")
def live_state():
    b = bundle() or {}
    by = {s["id"]: s for s in b.get("students", [])}
    sim = demo_server.load_sim()
    if sim:
        now = by.get(sim["roll"])
        return dict(sim=sim, after=_snap(now) if (now and sim.get("synced")) else None, candidates=[])
    if not demo_server.exists():
        return dict(sim=None, candidates=[])
    on = demo_server.rolls()
    cand = [s for s in by.values() if s["id"] in on and s.get("ar") == "Low" and (s["v"].get("att_pct") or 0) >= 88]
    cand.sort(key=lambda s: -(s["v"].get("success_score") or 0))
    return dict(sim=None, candidates=[dict(roll=s["id"], name=s["name"], dept=s["dept"], year=s["year"],
                                           score=round(s["v"]["success_score"]), att=round(s["v"]["att_pct"]))
                                      for s in cand[:15]])


class Pick(BaseModel):
    roll: str


@app.post("/api/demo/live", dependencies=[Depends(need_key)])
def live_change(p: Pick):
    if _running():
        raise HTTPException(409, "Another update is running. Wait for it to finish.")
    s = {x["id"]: x for x in (bundle() or {}).get("students", [])}.get(p.roll)
    if not s:
        raise HTTPException(400, "That student is not in the current data.")
    try:
        ch = demo_server.simulate_dropout(p.roll)
    except ValueError as e:
        raise HTTPException(400, str(e))
    sim = dict(roll=p.roll, name=s["name"], before=_snap(s), change=dict(ch, from_date=f"{ch['from_date']:%d %b}"),
               synced=False)
    demo_server.save_sim(sim)
    return dict(sim=sim)


@app.post("/api/demo/undo", dependencies=[Depends(need_key)])
def live_undo():
    return _start("demo", [([sys.executable, "-m", "src.demo_server"], None), lambda job: demo_server.save_sim(None)])


# ---------------------------------------------------------------- Excel upload
PENDING = {}  # token -> (prepared result, time)
MAX_UPLOAD = 40 * 1024 * 1024


@app.get("/api/template")
def template():
    return Response(su.template_bytes(), headers={"Content-Disposition": 'attachment; filename="EarlySignal_template.xlsx"'},
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/example")
def example():
    if not EXAMPLE.exists():
        raise HTTPException(404, "No example file in this copy.")
    return FileResponse(EXAMPLE, filename="EarlySignal_example_CSE.xlsx")


@app.post("/api/upload/check", dependencies=[Depends(need_key)])
def upload_check(files: list[UploadFile] = File(...)):
    got, total = [], 0
    for f in files:
        name = f.filename or "upload.xlsx"
        if not name.lower().endswith((".xlsx", ".xlsm", ".csv")):
            raise HTTPException(400, f"{name}: upload the Excel template (.xlsx) or CSV files.")
        data = f.file.read(MAX_UPLOAD + 1)
        total += len(data)
        if total > MAX_UPLOAD:
            raise HTTPException(413, "The upload is larger than 40 MB.")
        got.append((name, data))
    raw, notes = su.read_files(got)
    res = su.prepare(raw)
    token = None
    if res["ok"]:
        token = secrets.token_hex(8)
        PENDING[token] = (res, time.time())
        for old in sorted(PENDING, key=lambda k: PENDING[k][1])[:-2]:
            PENDING.pop(old, None)
    return dict(ok=res["ok"], checks=res["checks"], notes=notes, facts=res["facts"], token=token)


class Build(BaseModel):
    token: str
    college_name: str = ""


@app.post("/api/upload/build", dependencies=[Depends(need_key)])
def upload_build(b: Build):
    if b.token not in PENDING:
        raise HTTPException(400, "Upload the file again: the checked copy has expired.")
    from src import build
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    out = JOBS_DIR / f"build_{secrets.token_hex(4)}.json"

    def stage(job):
        res, _ = PENDING.pop(b.token)
        job["lines"].append("Saving your data and setting the previous version aside ...")
        build.stage(res["files"], dict(college_name=b.college_name.strip() or "My College",
                                       source=dict(type="upload", uploaded_at=india_now().strftime("%d %b %H:%M")),
                                       **res["settings"]))
        out.write_text(json.dumps(dict(facts=res["facts"])))
        job["lines"].append("Matching, scoring and training on your students. This takes about a minute ...")

    def after(job):
        res = json.loads(out.read_text()) if out.exists() else {}
        out.unlink(missing_ok=True)
        job["result"] = dict(built=bool(res.get("built")), facts=res.get("facts", {}),
                             errors=[] if res.get("built") else ["The data could not be processed, so nothing was changed."],
                             log=None if res.get("built") else res.get("log", ""))
        job["state"] = "done" if res.get("built") else "failed"

    return _start("upload", [stage, ([sys.executable, "-m", "src.build", "--finish", "--json", str(out)], None)], after)


@app.post("/api/reset", dependencies=[Depends(need_key)])
def reset():
    def clear(job):
        job["lines"].append("Switching back to the sample college ...")
        C.SETTINGS_FILE.unlink(missing_ok=True)
        shutil.rmtree(C.PROC_DIR, ignore_errors=True)

    def after(job):
        job["result"] = dict(built=job["rc"] == 0)

    return _start("reset", [clear, ([sys.executable, "-m", "src.pipeline", "--web"], None)], after)


# ---------------------------------------------------------------- sign-in codes by email
CODES, SENT = {}, {}  # challenge -> dict(hash, expires, tries); key -> [send times]
CODE_MINUTES, MAX_TRIES = 5, 5
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _hash(code, salt):
    return hashlib.sha256(f"{salt}:{code}".encode()).hexdigest()


def _limited(key, n, window):
    now = time.time()
    t = [x for x in SENT.get(key, []) if now - x < window]
    SENT[key] = t
    if len(t) >= n:
        return True
    t.append(now)
    return False


class EmailCode(BaseModel):
    email: str
    name: str = ""


@app.post("/api/otp/email")
def send_email_code(e: EmailCode, request: Request):
    if not email_ready():
        raise HTTPException(501, "Email codes are not set up on this server.")
    email = e.email.strip()
    if not EMAIL_RE.match(email) or len(email) > 200:
        raise HTTPException(400, "That email address does not look right.")
    ip = request.client.host if request.client else "?"
    if _limited("ip:" + ip, 20, 3600) or _limited("to:" + email.lower(), 5, 900):
        raise HTTPException(429, "Too many codes asked for. Wait a few minutes and try again.")
    code = f"{secrets.randbelow(10 ** 6):06d}"
    salt = secrets.token_hex(8)
    name = re.sub(r"[<>&\"]", "", e.name.strip())[:60]
    hello = f"Hello {name}," if name else "Hello,"
    text = (f"{hello}\n\nYour EarlySignal sign-in code is {code}. It expires in {CODE_MINUTES} minutes.\n\n"
            "If you did not try to sign in, you can ignore this email; nobody can sign in without the code.\n")
    html = (f"<div style='font-family:Arial,sans-serif;color:#1b2a2c;max-width:460px'>"
            f"<p>{hello}</p><p>Your EarlySignal sign-in code is</p>"
            f"<p style='font-size:30px;font-weight:bold;letter-spacing:6px;color:#0f766e;margin:8px 0'>{code}</p>"
            f"<p>It expires in {CODE_MINUTES} minutes.</p>"
            "<p style='color:#637275;font-size:13px'>If you did not try to sign in, you can ignore this email; nobody can "
            "sign in without the code.</p></div>")
    try:
        send_email(email, f"{code} is your EarlySignal sign-in code", text, html)
    except Exception as ex:
        print(f"Email code not sent: {type(ex).__name__}: {ex}", flush=True)
        raise HTTPException(502, "The email could not be sent. Try the other option, or try again in a minute.")
    cid = secrets.token_urlsafe(12)
    CODES[cid] = dict(hash=_hash(code, salt), salt=salt, expires=time.time() + CODE_MINUTES * 60, tries=0)
    for k in [k for k, v in CODES.items() if v["expires"] < time.time() - 600]:
        CODES.pop(k, None)
    return dict(challenge=cid, minutes=CODE_MINUTES)


class Verify(BaseModel):
    challenge: str
    code: str


@app.post("/api/otp/verify")
def verify_email_code(v: Verify):
    c = CODES.get(v.challenge)
    if not c:
        return dict(ok=False, reason="expired")
    if time.time() > c["expires"]:
        CODES.pop(v.challenge, None)
        return dict(ok=False, reason="expired")
    if hmac.compare_digest(c["hash"], _hash(v.code.strip(), c["salt"])):
        CODES.pop(v.challenge, None)
        return dict(ok=True)
    c["tries"] += 1
    if c["tries"] >= MAX_TRIES:
        CODES.pop(v.challenge, None)
        return dict(ok=False, reason="locked")
    return dict(ok=False, reason="wrong", left=MAX_TRIES - c["tries"])


@app.exception_handler(HTTPException)
def http_error(request, exc):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


# ---------------------------------------------------------------- the React app itself
if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="app")
else:
    @app.get("/")
    def no_build():
        return Response("Build the React app first: cd frontend && npm install && npm run build",
                        media_type="text/plain")
