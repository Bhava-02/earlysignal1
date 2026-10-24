"""Install a college's data (from an upload or a server sync) and rebuild every page. Shared by the app and the
nightly sync. If anything fails, the previous data and settings are put back.

Two steps, so the heavy rebuild can run in a fresh process that holds nothing else in memory:
  stage(files, settings)  save the new data, remember the old settings, set the old results aside
  finish()                rebuild; keep the new data if it worked, otherwise put everything back

    python -m src.build --finish [--json results.json]   (used by the sync)
"""
import gc
import json
import shutil
import subprocess
import sys
import time

from . import config as C

PREV = C.ROOT / "data" / "settings_previous.json"
BACKUP = C.ROOT / "data" / "processed_backup"


def rebuild():
    """Run the pipeline in a fresh process so the new settings are used everywhere."""
    r = subprocess.run([sys.executable, "-m", "src.pipeline"], cwd=str(C.ROOT), capture_output=True, text=True,
                       timeout=1800)
    return r.returncode == 0, (r.stdout + "\n" + r.stderr)[-3000:]


def stage(files, settings):
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest = C.ROOT / "data" / "uploads" / stamp
    dest.mkdir(parents=True, exist_ok=True)
    for fname, df in files.items():
        df.to_csv(dest / fname, index=False)
    files.clear()  # free memory before the rebuild starts
    gc.collect()
    PREV.write_text(C.SETTINGS_FILE.read_text() if C.SETTINGS_FILE.exists() else "")
    C.SETTINGS_FILE.write_text(json.dumps(dict(raw_dir=str(dest), **settings), indent=1))
    if C.PROC_DIR.exists():
        shutil.rmtree(BACKUP, ignore_errors=True)
        shutil.move(str(C.PROC_DIR), str(BACKUP))


def settle(ok):
    """After a rebuild: tidy up if it worked, otherwise put the previous data and settings back."""
    if ok:
        shutil.rmtree(BACKUP, ignore_errors=True)
        uploads = C.ROOT / "data" / "uploads"
        for old_dir in sorted(uploads.iterdir())[:-3] if uploads.exists() else []:  # keep the last 3 versions
            shutil.rmtree(old_dir, ignore_errors=True)
    else:
        prev = PREV.read_text() if PREV.exists() else ""
        if prev:
            C.SETTINGS_FILE.write_text(prev)
        else:
            C.SETTINGS_FILE.unlink(missing_ok=True)
        shutil.rmtree(C.PROC_DIR, ignore_errors=True)
        if BACKUP.exists():
            shutil.move(str(BACKUP), str(C.PROC_DIR))
    PREV.unlink(missing_ok=True)


def install(files, settings):
    """files: {internal file name: DataFrame}. settings: college details. Returns (ok, log)."""
    stage(files, settings)
    ok, log = rebuild()
    settle(ok)
    return ok, log


def finish(json_path=None):
    """Rebuild in THIS process (started fresh by the sync, so it holds nothing else) and settle."""
    import traceback
    ok, log = True, ""
    try:
        from . import pipeline
        pipeline.run(verbose=True)
    except Exception:
        ok, log = False, traceback.format_exc()[-3000:]
    settle(ok)
    if json_path:
        try:
            with open(json_path) as f:
                summary = json.load(f)
        except Exception:
            summary = {}
        summary.update(built=ok, log=log)
        with open(json_path, "w") as f:
            json.dump(summary, f, default=str)
    print("Done. Every page now uses the new data." if ok else "Build failed; the previous data is kept.\n" + log,
          flush=True)
    return ok


def reset_to_sample():
    C.SETTINGS_FILE.unlink(missing_ok=True)
    shutil.rmtree(C.PROC_DIR, ignore_errors=True)
    return rebuild()


if __name__ == "__main__":
    if "--finish" in sys.argv:
        jp = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
        sys.exit(0 if finish(jp or None) else 1)
