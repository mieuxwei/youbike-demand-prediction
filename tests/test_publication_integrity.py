"""Small checks for documentation-only integrity; no models or data needed."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from scripts.verify_publication import (
    ADDED, MODIFIED, REMOVED, check_file_set, heading_ids, local_links,
    safe_path, validate_scope,
)


class PublicationIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def test_exact_changes_removal_and_addition(self):
        old = hashlib.sha256(b"before").hexdigest()
        after = self.fixture("README.md", b"after")
        model = self.fixture("models/frozen.bin", b"unchanged")
        new = self.fixture("docs/new.md", b"new")
        before = {"README.md": old, "HANDOFF.md": old, "models/frozen.bin": model}
        changes = {
            "README.md": {"action": "modified", "before_sha256": old, "after_sha256": after},
            "HANDOFF.md": {"action": "removed", "before_sha256": old, "after_sha256": None},
        }
        check_file_set(self.root, before, changes, {"docs/new.md": new})
        self.fixture("models/frozen.bin", b"tampered")
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            check_file_set(self.root, before, changes, {"docs/new.md": new})

    def test_removed_file_cannot_reappear(self):
        old = self.fixture("HANDOFF.md", b"old")
        with self.assertRaisesRegex(ValueError, "reappeared"):
            check_file_set(self.root, {"HANDOFF.md": old}, {
                "HANDOFF.md": {"action": "removed", "before_sha256": old}}, {})

    def test_before_hash_and_added_file_are_verified(self):
        value = self.fixture("README.md", b"current")
        with self.assertRaisesRegex(ValueError, "Before hash"):
            check_file_set(self.root, {"README.md": value}, {
                "README.md": {"action": "modified", "before_sha256": "wrong",
                              "after_sha256": value}}, {})
        with self.assertRaisesRegex(ValueError, "Added-file checksum"):
            check_file_set(self.root, {}, {}, {"README.md": "wrong"})

    def test_scope_rejects_model_or_extra_file_exclusion(self):
        changes = {p: {"action": "modified", "after_sha256": "a" * 64} for p in MODIFIED}
        changes.update({p: {"action": "removed", "after_sha256": None} for p in REMOVED})
        validate_scope(changes, dict.fromkeys(ADDED, "b" * 64))
        changes["models/anything.joblib"] = {"action": "modified", "after_sha256": "c" * 64}
        with self.assertRaisesRegex(ValueError, "exact documentation-only"):
            validate_scope(changes, dict.fromkeys(ADDED, "b" * 64))

    def test_path_traversal_and_symlink_rejected(self):
        for name in ("../outside", "/tmp/outside"):
            with self.assertRaises(ValueError):
                safe_path(self.root, name)
        (self.root / "alias").symlink_to("/tmp")
        with self.assertRaises(ValueError):
            safe_path(self.root, "alias")

    def test_markdown_links_anchors_and_code_fences(self):
        self.fixture("guide.md", "# 開始\n## Details\n## Details\n".encode())
        self.fixture("README.md", b"[guide](guide.md#details-1)\n")
        self.assertEqual(local_links(self.root, "README.md"), 1)
        self.assertIn("開始", heading_ids((self.root / "guide.md").read_text()))
        self.fixture("README.md", b"[missing](guide.md#absent)\n")
        with self.assertRaisesRegex(ValueError, "Missing anchor"):
            local_links(self.root, "README.md")
        self.fixture("README.md", b"```python\nprint(1)\n")
        with self.assertRaisesRegex(ValueError, "Unbalanced"):
            local_links(self.root, "README.md")


if __name__ == "__main__":
    unittest.main()
