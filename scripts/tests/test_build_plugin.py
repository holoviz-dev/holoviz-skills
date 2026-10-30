"""Tests for the marketplace file build_plugin.py writes for Claude Code and npx skills."""

import json

import build_plugin


def write_skill(path, version):
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(
        f'---\nname: {path.name}\ndescription: x\nmetadata:\n  version: "{version}"\n---\n'
    )


def test_marketplace_lists_every_category_in_one_plugin(tmp_path, monkeypatch):
    """Sub-skills stay out of the skills list, and a sub-skill edit still bumps the version."""
    write_skill(tmp_path / "developing-with-holoviz", "2026.10.20")
    write_skill(tmp_path / "developing-with-holoviz" / "skills" / "panel", "2026.10.21")
    write_skill(tmp_path / "contributing-to-holoviz", "2026.10.13")
    marketplace_json = tmp_path / ".claude-plugin" / "marketplace.json"
    monkeypatch.setattr(build_plugin, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(build_plugin, "MARKETPLACE_JSON", marketplace_json)

    build_plugin.build_marketplace()

    marketplace = json.loads(marketplace_json.read_text(encoding="utf-8"))
    skills, mcp = marketplace["plugins"]
    assert marketplace["name"] == "holoviz-skills"
    assert skills["name"] == "holoviz"
    assert skills["skills"] == ["./contributing-to-holoviz", "./developing-with-holoviz"]
    assert skills["version"] == "2026.10.21"
    assert mcp["name"] == "panel-live-server"
    assert "skills" not in mcp
