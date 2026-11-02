import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "agent_skills/install.py"
SPEC = importlib.util.spec_from_file_location("neptune_agent_skills", SCRIPT)
skills = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skills)


class AgentSkillPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / "cache"
        self.dest = self.root / "installed"
        archive_dir = self.cache / "archives"
        archive_dir.mkdir(parents=True)
        self.archive = archive_dir / "fixture.tar.gz"
        self.body = b"---\nname: fixture\ndescription: Test fixture\n---\n"
        self.make_archive([("source/skill/SKILL.md", self.body)])
        source = self.root / "source-skill"
        source.mkdir()
        (source / "SKILL.md").write_bytes(self.body)
        self.lock = {
            "schema": "neptune.agent-skills.v1",
            "sources": [{"id": "fixture", "repository": "example/skills",
                         "revision": "a" * 40,
                         "archive_url": "https://codeload.github.com/example/skills/tar.gz/" + "a" * 40,
                         "archive_sha256": skills.digest(self.archive),
                         "skills": [{"name": "fixture", "path": "skill",
                                     "tree_sha256": skills.tree_digest(source)}]}],
        }
        self.lock_path = self.root / "lock.json"
        self.write_lock()

    def make_archive(self, entries):
        with tarfile.open(self.archive, "w:gz") as archive:
            for name, body in entries:
                member = tarfile.TarInfo(name)
                member.size = len(body)
                archive.addfile(member, io.BytesIO(body))

    def write_lock(self):
        self.lock_path.write_text(json.dumps(self.lock))

    def run_install(self, **kwargs):
        return skills.install(self.lock_path, self.cache, self.dest, **kwargs)

    def test_real_install_reuse_and_read_only_verification(self):
        result = self.run_install()
        self.assertEqual(result["skills"], 1)
        self.assertTrue((self.dest / "fixture").is_symlink())
        self.assertEqual((self.dest / "fixture").stat().st_mode & 0o222, 0)
        self.assertEqual((self.dest / "fixture/SKILL.md").stat().st_mode & 0o222, 0)
        before = {str(p): p.lstat().st_mtime_ns for p in self.root.rglob("*")}
        self.assertEqual(self.run_install(verify=True), result)
        after = {str(p): p.lstat().st_mtime_ns for p in self.root.rglob("*")}
        self.assertEqual(before, after)
        self.assertEqual(self.run_install(), result)

    def test_wrong_archive_hash_refuses_publication(self):
        self.archive.write_bytes(b"wrong release")
        with self.assertRaisesRegex(ValueError, "archive identity mismatch"):
            self.run_install()
        self.assertFalse(self.dest.exists())

    def test_tampered_installed_bytes_fail_offline_verification(self):
        self.run_install()
        (self.dest / "fixture/SKILL.md").chmod(0o644)
        (self.dest / "fixture/SKILL.md").write_text("forged success")
        with self.assertRaisesRegex(ValueError, "skill identity mismatch"):
            self.run_install(verify=True)

    def test_missing_archive_stays_resumable(self):
        saved = self.archive.read_bytes()
        self.archive.unlink()
        with self.assertRaisesRegex(ValueError, "Missing cached archive"):
            self.run_install()
        self.archive.write_bytes(saved)
        self.assertEqual(self.run_install()["status"], "verified")

    def test_escaping_archive_path_is_rejected(self):
        self.make_archive([("source/../../escaped", b"bad")])
        self.lock["sources"][0]["archive_sha256"] = skills.digest(self.archive)
        self.write_lock()
        with self.assertRaisesRegex(ValueError, "Unsafe relative path"):
            self.run_install()
        self.assertFalse((self.root / "escaped").exists())

    def test_archive_symlink_is_rejected(self):
        with tarfile.open(self.archive, "w:gz") as archive:
            member = tarfile.TarInfo("source/skill/SKILL.md")
            member.type = tarfile.SYMTYPE
            member.linkname = "/etc/passwd"
            archive.addfile(member)
        self.lock["sources"][0]["archive_sha256"] = skills.digest(self.archive)
        self.write_lock()
        with self.assertRaisesRegex(ValueError, "links or special files"):
            self.run_install()

    def test_foreign_skill_is_preserved(self):
        foreign = self.dest / "fixture"
        foreign.mkdir(parents=True)
        (foreign / "SKILL.md").write_text("keep")
        with self.assertRaisesRegex(ValueError, "conflicting skill registration"):
            self.run_install()
        self.assertEqual((foreign / "SKILL.md").read_text(), "keep")

    def test_missing_entrypoint_cannot_report_success(self):
        self.make_archive([("source/skill/README.md", self.body)])
        self.lock["sources"][0]["archive_sha256"] = skills.digest(self.archive)
        self.write_lock()
        with self.assertRaisesRegex(ValueError, "skill identity mismatch"):
            self.run_install()

    def test_duplicate_names_and_mutable_revisions_are_rejected(self):
        self.lock["sources"][0]["skills"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicate skill"):
            skills.validate_lock(self.lock)
        self.lock["sources"][0]["skills"] = self.lock["sources"][0]["skills"][:1]
        self.lock["sources"][0]["revision"] = "main"
        with self.assertRaisesRegex(ValueError, "full commit"):
            skills.validate_lock(self.lock)

    def test_real_lock_is_valid_and_local_skill_matches(self):
        lock = json.loads((SCRIPT.parent / "skills-lock.json").read_text())
        skills.validate_lock(lock)
        self.assertEqual(len(skills.all_skills(lock)), 60)
        for skill in lock["local_skills"]:
            self.assertEqual(skills.tree_digest(SCRIPT.parent / skill["path"]), skill["tree_sha256"])


if __name__ == "__main__":
    unittest.main()
