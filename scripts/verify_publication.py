"""Read-only checks for the additive public-documentation revision."""
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASE = "176f8c594f24bf5f35037bf78974069c9863a576"
RESEARCH_BASE = "159f059d0e9ff4afcdbf9ad206d1b426aa1339aa"
ORIGINAL = "results/live_demo/freeze_manifest.json"
AMENDMENT = "docs/publication/documentation-amendment.json"
MODIFIED = {
    "README.md", "docs/PROJECT_OVERVIEW_STATUS_AND_TECHNOLOGY.md",
    "docs/MODEL_CARD.md", "docs/REPRODUCIBILITY.md",
}
REMOVED = {"HANDOFF.md", "PROJECT_PLAN.md"}
ADDED = {
    "docs/README.md", "docs/DOCUMENTATION_REVISION.md",
    "docs/assets/README.md", "docs/assets/live-availability-20260927.png",
    "docs/assets/static-redistribution-20260927.png",
    "scripts/verify_publication.py", "tests/test_publication_integrity.py",
}
IMMUTABLE_RECORDS = {
    ORIGINAL, "results/offline_research/freeze_manifest.json",
    "docs/RESEARCH_FREEZE.md", "docs/LIVE_DEMO_DELIVERY.md",
}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_blob(path, commit=BASE, root=ROOT):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=root)


def safe_path(root, name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or name != path.as_posix():
        raise ValueError(f"Unsafe relative path: {name}")
    target = root / path
    if target.is_symlink() or root.resolve() not in target.resolve().parents:
        raise ValueError(f"Path escapes repository: {name}")
    return target


def validate_scope(changes, added):
    if set(changes) != MODIFIED | REMOVED or set(added) != ADDED:
        raise ValueError("Amendment is not the exact documentation-only scope")
    for name, entry in changes.items():
        action = "removed" if name in REMOVED else "modified"
        if entry["action"] != action:
            raise ValueError(f"Unexpected action: {name}")
        if action == "removed" and entry["after_sha256"] is not None:
            raise ValueError(f"Removal has an after hash: {name}")
        if action == "modified" and not re.fullmatch(r"[0-9a-f]{64}", entry["after_sha256"] or ""):
            raise ValueError(f"Invalid after hash: {name}")


def check_file_set(root, before, changes, added):
    for name in changes:
        if name not in before:
            raise ValueError(f"Unknown original file: {name}")
    if set(added) & set(before):
        raise ValueError("New file shadows an original file")
    for name, original_hash in before.items():
        path = safe_path(root, name)
        expected = original_hash
        if name in changes:
            entry = changes[name]
            if entry["before_sha256"] != original_hash:
                raise ValueError(f"Before hash does not match original: {name}")
            if entry["action"] == "removed":
                if path.exists():
                    raise ValueError(f"Removed file reappeared: {name}")
                continue
            expected = entry["after_sha256"]
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"Checksum mismatch: {name}")
    for name, expected in added.items():
        path = safe_path(root, name)
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"Added-file checksum mismatch: {name}")


def without_fences(text):
    return re.sub(r"(?ms)^\s*```[^\n]*\n.*?^\s*```\s*$", "", text)


def heading_ids(text):
    counts = Counter()
    anchors = set()
    for line in without_fences(text).splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        label = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", match[1])
        label = re.sub(r"<[^>]+>", "", label).replace("`", "").replace("*", "")
        slug = "".join(c for c in label.lower()
                       if c in " _-" or unicodedata.category(c)[0] in "LN")
        slug = slug.replace(" ", "-")
        n = counts[slug]
        counts[slug] += 1
        anchors.add(slug if not n else f"{slug}-{n}")
    anchors.update(re.findall(r'\bid=["\x27]([^"\x27]+)["\x27]', text))
    return anchors


def local_links(root, name, historical=False):
    path = root / name
    text = path.read_text()
    if len(re.findall(r"(?m)^\s*```", text)) % 2:
        raise ValueError(f"Unbalanced code fences: {name}")
    count = 0
    for dest in re.findall(r"!?(?:\[[^\]\n]*\])\(([^)\s]+)\)", without_fences(text)):
        parsed = urlsplit(dest.strip("<>"))
        if parsed.scheme or parsed.netloc:
            continue
        target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path.resolve()
        # Immutable historical evidence must resolve at its actual old commit.
        if historical and name == "docs/RESEARCH_FREEZE.md" and dest == "../PROJECT_PLAN.md":
            if not git_blob("PROJECT_PLAN.md", RESEARCH_BASE, root).startswith(b"#"):
                raise ValueError("Historical plan reference cannot be resolved")
            count += 1
            continue
        if not target.exists():
            raise ValueError(f"Missing link: {name} -> {dest}")
        if parsed.fragment and target.suffix == ".md":
            if unquote(parsed.fragment) not in heading_ids(target.read_text()):
                raise ValueError(f"Missing anchor: {name} -> {dest}")
        count += 1
    return count


def main():
    amendment = json.loads((ROOT / AMENDMENT).read_text())
    if amendment["base_commit"] != BASE:
        raise ValueError("Wrong documentation base commit")
    for name in IMMUTABLE_RECORDS:
        if (ROOT / name).read_bytes() != git_blob(name):
            raise ValueError(f"Original evidence changed: {name}")
    original = json.loads((ROOT / ORIGINAL).read_text())
    changes, added = amendment["changes"], amendment["added_files"]
    validate_scope(changes, added)
    check_file_set(ROOT, original["files"], changes, added)
    documents = sorted(set(MODIFIED) | {p for p in ADDED if p.endswith(".md")}
                       | {"dashboard/README.md", "docs/RESEARCH_FREEZE.md",
                          "docs/LIVE_DEMO_DELIVERY.md"})
    links = sum(local_links(ROOT, p, historical=True) for p in documents)
    print(json.dumps({
        "base_commit": BASE, "original_delivery_files_checked": len(original["files"]),
        "unchanged_original_files": len(original["files"]) - len(changes),
        "exact_document_changes": len(MODIFIED), "exact_removals": len(REMOVED),
        "added_files_checked": len(added), "local_links_and_anchors": links,
        "historical_links_resolved_at_preservation_commit": 1,
        "research_runtime_and_original_records": "unchanged",
    }, indent=2))


if __name__ == "__main__":
    main()
