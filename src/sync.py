"""
Sync from the college's servers and rebuild every page. Runs as its own process, so the app stays light.

    python -m src.sync                # the server saved on the Data sources page
    python -m src.sync --demo         # the built-in demo college server
    python -m src.sync --json out.json   # also write the results for the app to show

Nightly (cron, on a machine inside the campus network):
    0 2 * * * cd /opt/earlysignal && EARLYSIGNAL_ERP_PASSWORD=... python -m src.sync >> sync.log 2>&1

Passwords come only from the environment; EarlySignal never stores them.
"""
import json
import os
import sys
import time

from datetime import datetime, timedelta, timezone

from . import build, connector


def india_now():
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))


def say(msg):
    print(msg, flush=True)


def main(argv):
    out_path = argv[argv.index("--json") + 1] if "--json" in argv else None
    summary = dict(ok=False, built=False, errors=[], report=[], notes=[], checks=[], facts={}, log="")

    def finish(code):
        if out_path:
            with open(out_path, "w") as f:
                json.dump(summary, f, default=str)
        return code

    conn = connector.load_conn()
    if "--demo" in argv:
        from . import demo_server
        if not demo_server.exists():
            say("Creating the demo college server ...")
            demo_server.build()
        cfgs, name = connector.demo_cfgs(), conn.get("college_name") or "Demo College"
    else:
        cfgs = {k: conn[k] for k in ("erp", "lms") if conn.get(k)}
        name = conn.get("college_name") or "My College"
        if not cfgs.get("erp"):
            summary["errors"] = ["No server saved yet. Connect once from the Data sources page."]
            say(summary["errors"][0])
            return finish(2)
    pw = {"erp": os.environ.get("EARLYSIGNAL_ERP_PASSWORD", ""), "lms": os.environ.get("EARLYSIGNAL_LMS_PASSWORD", "")}
    t0 = time.time()
    say("Reading from the college server (read-only) ...")
    out = connector.sync(cfgs, conn.get("queries"), pw, progress=lambda m: say("  " + m))
    res = out["result"]
    summary.update(ok=out["ok"], errors=out["errors"], report=out["report"], notes=out["notes"],
                   checks=res["checks"] if res else [], facts=res["facts"] if res else {})
    if not out["ok"]:
        for e in out["errors"]:
            say("  ! " + e)
        for c in summary["checks"]:
            if c["status"] == "error":
                say(f"  ! {c['sheet']}: {c['text']}")
        say("Sync stopped. The dashboard still shows the previous data.")
        return finish(1)
    files, settings = res["files"], res["settings"]
    del out, res
    build.stage(files, dict(college_name=name, source=dict(type="server", synced_at=india_now().strftime("%d %b %H:%M")),
                            **settings))
    finish(0)
    say(f"Data read and checked in {time.time() - t0:.0f} s. Rebuilding every page (about a minute) ...")
    # hand over to a fresh process for the rebuild, so this one's memory is released completely
    args = [sys.executable, "-m", "src.build", "--finish"] + (["--json", out_path] if out_path else [])
    sys.stdout.flush()
    if os.name == "posix":
        os.chdir(str(build.C.ROOT))
        os.execv(sys.executable, args)
    import subprocess
    return subprocess.call(args, cwd=str(build.C.ROOT))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
