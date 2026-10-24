"""Assemble the Hugging Face Docker Space folder for the EarlySignal web server.

    cd frontend && npm run build && cd ..     # the React app for the server (frontend/dist)
    python deploy/build_space.py              # writes deploy/space/ ; upload its contents to the Space
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deploy" / "space"
README = """---
title: EarlySignal
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# EarlySignal

Student success analytics for colleges. Open the app at the Space's direct address
(https://YOUR-NAME-SPACE-NAME.hf.space) so that Continue with Google works.

Settings go in this Space's **Settings > Variables and secrets** (all optional):

| Name | What it is |
|---|---|
| `EARLYSIGNAL_ADMIN_KEY` | Secret. If set, changing data on the Data sources page needs this key. Recommended. |
| `BREVO_API_KEY`, `EMAIL_FROM` | Secret + variable. Sign-in codes by email through Brevo (EMAIL_FROM is a sender verified in Brevo). |
| `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`, `FIREBASE_APP_ID` | Variables. Continue with Google and SMS codes (Firebase web app settings). |
| `EARLYSIGNAL_ADMIN_EMAIL` | Variable. Shown when the AI assistant cannot answer a question. |

The full setup guide is in the project's README.
"""
SKIP_RAW = {"_ground_truth_DO_NOT_USE.csv"}


def main():
    dist = ROOT / "frontend" / "dist"
    if not (dist / "index.html").exists():
        raise SystemExit("Build the React app first: cd frontend && npm run build")
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    for f in ("api.py", "requirements-web.txt", "requirements-server.txt"):
        shutil.copy2(ROOT / f, OUT / f)
    shutil.copy2(ROOT / "Dockerfile.web", OUT / "Dockerfile")
    (OUT / "README.md").write_text(README)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(ROOT / "src", OUT / "src", ignore=ignore)
    shutil.copytree(ROOT / "assets", OUT / "assets", ignore=ignore)
    shutil.copytree(ROOT / "demo", OUT / "demo", ignore=ignore)
    shutil.copytree(dist, OUT / "frontend" / "dist")
    (OUT / "data" / "raw").mkdir(parents=True)
    for p in (ROOT / "data" / "raw").iterdir():
        if p.is_file() and p.name not in SKIP_RAW:
            shutil.copy2(p, OUT / "data" / "raw" / p.name)
    (OUT / ".dockerignore").write_text("__pycache__\n*.pyc\ndata/processed\ndata/uploads\n")
    n = sum(1 for _ in OUT.rglob("*") if _.is_file())
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file()) / 1e6
    print(f"Wrote {OUT} ({n} files, {size:.1f} MB)")


if __name__ == "__main__":
    main()
