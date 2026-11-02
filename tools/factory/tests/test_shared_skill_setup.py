import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

DIRECTORY = Path(__file__).resolve().parents[1] / "agent_skills"
sys.path.insert(0, str(DIRECTORY))
SPEC = importlib.util.spec_from_file_location("shared_skill_setup", DIRECTORY / "setup.py")
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


class SharedSkillSetupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.user = Path(temporary.name)
        self.canonical = self.user / ".agents/skills"
        self.skill = self.canonical / "fixture"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: fixture\ndescription: Fixture\n---\n")
        self.expected = {"fixture": setup.recipe.tree_digest(self.skill)}
        self.registry = json.loads((DIRECTORY / "harnesses.json").read_text())

    def test_all_global_harnesses_and_current_antigravity_paths(self):
        paths = setup.roots(self.registry, self.user, {})
        self.assertEqual(sum(x["global"] is not None for x in self.registry["harnesses"]), 77)
        self.assertNotIn("eve", paths)
        self.assertNotIn("promptscript", paths)
        project_only = {x["id"]: x["project"] for x in self.registry["harnesses"] if x["global"] is None}
        self.assertEqual(project_only["eve"], "agent/skills")
        self.assertEqual(project_only["promptscript"], ".agents/skills")
        self.assertEqual(paths["claude-code"], self.user / ".claude/skills")
        self.assertEqual(paths["antigravity-current"], self.user / ".gemini/config/skills")
        self.assertEqual(paths["codex"], self.canonical)
        self.assertEqual(paths["pi-compatibility"], self.user / ".pi/agent/skills")
        self.assertEqual(paths["openhands"], self.user / ".openhands/skills")

    def test_existing_harness_roots_are_respected_without_repurposing_home(self):
        values = {"CODEX_HOME": str(self.user / "custom-code"), "CLAUDE_CONFIG_DIR": str(self.user / "custom-claude"), "XDG_CONFIG_HOME": str(self.user / "xdg")}
        before = dict(values)
        paths = setup.roots(self.registry, self.user, values)
        self.assertEqual(paths["codex-helper-compatibility"], self.user / "custom-code/skills")
        self.assertEqual(paths["claude-code"], self.user / "custom-claude/skills")
        self.assertEqual(paths["opencode"], self.user / "xdg/opencode/skills")
        self.assertEqual(before, values)

    def test_registration_and_offline_verification_across_multiple_projects(self):
        paths = {"claude": self.user / ".claude/skills", "project-one": self.user / "one/.agents/skills", "project-two": self.user / "two/.agents/skills", "canonical": self.canonical}
        setup.ensure_registrations(self.expected, self.expected, paths, self.canonical)
        self.assertFalse(paths["claude"].exists())
        setup.ensure_registrations(self.expected, self.expected, paths, self.canonical, publish=True)
        for root in paths.values():
            self.assertEqual((root / "fixture").resolve(), self.skill.resolve())
        before = {str(p): p.lstat().st_mtime_ns for p in self.user.rglob("*")}
        setup.ensure_registrations(self.expected, self.expected, paths, self.canonical, verify=True)
        self.assertEqual(before, {str(p): p.lstat().st_mtime_ns for p in self.user.rglob("*")})
        self.assertFalse(self.skill.is_symlink())

    def test_foreign_skill_is_preserved_before_any_alias_is_created(self):
        foreign = self.user / "foreign/fixture"
        foreign.mkdir(parents=True)
        (foreign / "SKILL.md").write_text("preserve")
        paths = {"first": self.user / "new", "foreign": foreign.parent}
        with self.assertRaisesRegex(ValueError, "Preserve conflicting"):
            setup.ensure_registrations(self.expected, self.expected, paths, self.canonical, publish=True)
        self.assertFalse(paths["first"].exists())
        self.assertEqual((foreign / "SKILL.md").read_text(), "preserve")

    def test_broken_and_missing_links_cannot_be_reported_verified(self):
        target = self.user / "broken"
        target.mkdir()
        (target / "fixture").symlink_to(self.user / "absent")
        with self.assertRaisesRegex(ValueError, "Missing or broken"):
            setup.ensure_registrations(self.expected, self.expected, {"x": target}, self.canonical)
        with self.assertRaisesRegex(ValueError, "Missing or broken"):
            setup.ensure_registrations(self.expected, self.expected, {"x": self.user / "missing"}, self.canonical, verify=True)

    def test_mcp_merge_preserves_servers_and_other_settings(self):
        path = self.user / "mcp.json"
        original = {"otherSetting": 42, "mcpServers": {"existing": {"command": "keep"}}}
        path.write_text(json.dumps(original))
        entry = {"command": "/tools/rea", "args": ["mcp"], "env": {"PROFILE": "compact"}}
        setup.merge_mcp(path, entry)
        result = json.loads(path.read_text())
        self.assertEqual(result["mcpServers"]["existing"], original["mcpServers"]["existing"])
        self.assertEqual(result["otherSetting"], 42)
        backup = path.with_name(path.name + ".before-agent-skills")
        self.assertEqual(json.loads(backup.read_text()), original)
        before = path.stat().st_mtime_ns
        setup.merge_mcp(path, entry, verify=True)
        setup.merge_mcp(path, entry)
        self.assertEqual(path.stat().st_mtime_ns, before)

    def test_foreign_mcp_registration_and_malformed_configuration_are_preserved(self):
        path = self.user / "mcp.json"
        original = '{"mcpServers":{"rea":{"command":"foreign","args":[]}}}'
        path.write_text(original)
        with self.assertRaisesRegex(ValueError, "Preserve conflicting REA"):
            setup.merge_mcp(path, {"command": "/tools/rea", "args": ["mcp"]})
        self.assertEqual(path.read_text(), original)
        path.write_text('{"mcpServers":[]}')
        with self.assertRaisesRegex(TypeError, "Malformed MCP"):
            setup.merge_mcp(path, {"command": "/tools/rea", "args": ["mcp"]})

    def test_claude_profile_configuration_is_kept_with_its_profile(self):
        profile = self.user / "profiles/claude"
        with patch.object(setup.shutil, "which", return_value=None):
            clients = setup.configure_mcp(Path("/tools/rea"), self.user, {"CLAUDE_CONFIG_DIR": str(profile)})
            setup.configure_mcp(Path("/tools/rea"), self.user, {"CLAUDE_CONFIG_DIR": str(profile)}, verify=True)
        self.assertEqual(clients, ["claude-code", "antigravity"])
        self.assertTrue((profile / ".claude.json").exists())
        self.assertFalse((self.user / ".claude.json").exists())

    def test_project_verification_detects_missing_mcp_configuration(self):
        project = self.user / "project"
        setup.configure_project_mcp(project, "/tools/rea")
        setup.configure_project_mcp(project, "/tools/rea", verify=True)
        (project / ".agents/mcp_config.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing or stale REA"):
            setup.configure_project_mcp(project, "/tools/rea", verify=True)
        self.assertFalse((project / ".agents/mcp_config.json").exists())

    def test_installed_setup_runs_outside_any_project_with_spaced_paths(self):
        cache = self.user / "shared cache"
        command = setup.install_commands(cache, "/usr/bin/node")
        unrelated = self.user / "unrelated-project"
        unrelated.mkdir()
        result = subprocess.run([command, "--help"], cwd=unrelated, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--all-harnesses", result.stdout)
        self.assertIn("--project", result.stdout)

    def test_large_node_output_is_complete_even_with_immediate_exit(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required to validate the skills CLI output contract")
        output = setup.run([node, "-e", "process.stdout.write('x'.repeat(200000)); process.exit(0)"])
        self.assertEqual(output, "x" * 200000)


if __name__ == "__main__":
    unittest.main()
