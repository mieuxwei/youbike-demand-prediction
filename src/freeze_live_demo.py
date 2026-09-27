"""Record/verify v7 delivery without rewriting the v6 research freeze.

Run `verify-research` at any time. Run `record` only after documented acceptance;
it records the already accepted files, never trains, exports, deploys or commits.
"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "159f059d0e9ff4afcdbf9ad206d1b426aa1339aa"
OLD = "results/offline_research/freeze_manifest.json"
MANIFEST = "results/live_demo/freeze_manifest.json"
# Exact, authorized presentation/route changes only. All other v6 files remain
# byte-identical, including Stage 17/19, Phase 3/4, models, results and bundles.
PRESENTATION = {
    ".gitignore", "HANDOFF.md", "PROJECT_PLAN.md", "README.md",
    "cloudflare/track-b-collector/README.md",
    "cloudflare/track-b-collector/src/index.mjs",
    "dashboard/README.md", "dashboard/app/globals.css",
    "dashboard/app/layout.tsx", "dashboard/app/page.tsx",
    "dashboard/tests/rendered-html.test.mjs",
    "docs/PROJECT_OVERVIEW_STATUS_AND_TECHNOLOGY.md",
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def research_check():
    saved = git("show", f"{BASE}:{OLD}")
    if (ROOT / OLD).read_bytes() != saved:
        raise ValueError("Original research freeze manifest changed")
    files = json.loads(saved)["files"]
    protected = {p: h for p, h in files.items() if p not in PRESENTATION}
    bad = [p for p, h in protected.items()
           if not (ROOT / p).is_file() or digest(ROOT / p) != h]
    if bad:
        raise ValueError(f"Frozen research changed: {bad}")
    return len(protected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["verify-research", "record", "verify"])
    args = parser.parse_args()
    count = research_check()
    if args.action == "verify-research":
        print(json.dumps({"unchanged_v6_files": count, "preservation_commit": BASE}))
        return
    target = ROOT / MANIFEST
    if args.action == "record":
        if target.exists():
            raise ValueError("Delivery manifest already exists; refusing to overwrite")
        names = set(git("ls-files", "-z").decode().split("\0"))
        names.update(git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0"))
        names.discard("")
        names.discard(MANIFEST)
        record = {
            "status": "研究與展示交付完成，實作 frozen",
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "research_preservation_commit": BASE,
            "source_parent_commit": git("rev-parse", "HEAD").decode().strip(),
            "working_tree_before_record": git("status", "--short").decode(),
            "commit_identity_note": "The final commit containing this manifest is obtained with git log -1 -- results/live_demo/freeze_manifest.json; it cannot self-hash.",
            "unchanged_v6_files": count,
            "authorized_v6_presentation_changes": sorted(PRESENTATION),
            "site_url": "https://youbike-demand-observatory.rwhqgqfdk2.chatgpt.site",
            "site_source_commit": "930ef06b094ffde278b93201150f1e9e40c17b54",
            "site_version": "appgver_e5d6fb29f48881919a9229df858c06b8",
            "site_deployment": "appgdep_6ab8cdcfd9648191b6f76878881b25e7",
            "worker_version": "069e3f5a-5966-4efa-aafc-0ab2697dfa62",
            "acceptance_record": "docs/LIVE_DEMO_DELIVERY.md",
            "stop_rule": "No new research, models, windows, features, reminders or autonomous work. Existing cloud collection remains separate infrastructure.",
            "files": {p: digest(ROOT / p) for p in sorted(names) if (ROOT / p).is_file()},
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"recorded_files": len(record["files"]), "manifest": MANIFEST}))
    else:
        record = json.loads(target.read_text())
        bad = [p for p, h in record["files"].items()
               if not (ROOT / p).is_file() or digest(ROOT / p) != h]
        if bad:
            raise ValueError(f"Delivery files changed: {bad}")
        print(json.dumps({"verified_delivery_files": len(record["files"]),
                          "unchanged_v6_files": count}))


if __name__ == "__main__":
    main()
