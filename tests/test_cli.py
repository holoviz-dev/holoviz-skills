"""Tests for the holoviz-skills CLI: skill selection, install, update, doctor."""

import os
import shutil
from pathlib import Path

import pytest

from holoviz_skills import cli


def write_skill(path: Path, version: str, compatibility: str = "") -> Path:
    path.mkdir(parents=True)
    extra = f"compatibility: {compatibility}\n" if compatibility else ""
    (path / "SKILL.md").write_text(
        f'---\nname: {path.name}\ndescription: x\n{extra}metadata:\n  version: "{version}"\n---\n'
    )
    return path


@pytest.fixture
def source(tmp_path):
    """A release with a routing skill, one sub-skill and a second category."""
    root = tmp_path / "source"
    write_skill(root / "developing-with-holoviz", "2026.10.01")
    write_skill(root / "developing-with-holoviz" / "skills" / "panel", "2026.10.15", "panel>=1.5")
    write_skill(root / "contributing-to-holoviz", "2026.10.13")
    return root


@pytest.fixture
def project(tmp_path, monkeypatch, source):
    """A project directory as cwd, with its own home, installing from ``source``."""
    home, proj = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    proj.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.chdir(proj)
    monkeypatch.setattr(cli, "_skills_root", lambda: source)
    return proj


def test_exact_skill_name_wins_over_a_prefix():
    dirs = [Path("developing"), Path("developing-with-holoviz")]
    assert cli._select_skills(dirs, ["developing"]) == [Path("developing")]
    assert cli._select_skills(dirs, ["developing-w"]) == [Path("developing-with-holoviz")]


@pytest.mark.parametrize(("name", "reason"), [("contrib", "ambiguous"), ("nope", "unknown")])
def test_bad_skill_name_is_rejected_not_guessed(capsys, name, reason):
    dirs = [Path("contributing-to-holoviz"), Path("contributing-extra")]
    assert cli._select_skills(dirs, [name]) is None
    assert f"{name} ({reason})" in capsys.readouterr().err


def test_install_skips_script_tests(project, source):
    scripts = source / "developing-with-holoviz" / "scripts"
    scripts.mkdir()
    (scripts / "lint.py").write_text("")
    (scripts / "test_lint.py").write_text("")
    assert cli.main(["install", "developing", "--claude-code"]) == 0
    installed = project / ".claude" / "skills" / "developing-with-holoviz" / "scripts"
    assert sorted(p.name for p in installed.iterdir()) == ["lint.py"]


def test_update_reports_the_sub_skill_that_changed(project, capsys):
    """A stale sub-skill shows up even when the routing skill's version is current."""
    assert cli.main(["install", "developing", "--claude-code"]) == 0
    stale = project / ".claude" / "skills" / "developing-with-holoviz" / "skills" / "panel"
    md = stale / "SKILL.md"
    md.write_text(md.read_text().replace("2026.10.15", "2026.09.01"))
    capsys.readouterr()

    assert cli.main(["update"]) == 0
    assert "panel 2026.09.01 → 2026.10.15" in capsys.readouterr().out
    assert "2026.10.15" in md.read_text()


def test_update_with_nothing_installed_fails(project):
    assert cli.main(["update"]) == 1


def test_symlinked_skill_is_unlinked_not_deleted_through(project, source):
    """`npx skills` links each agent's directory to one copy; ours must leave that copy."""
    copy = project / ".agents" / "skills" / "developing-with-holoviz"
    shutil.copytree(source / "developing-with-holoviz", copy)
    link = project / ".claude" / "skills" / "developing-with-holoviz"
    link.parent.mkdir(parents=True)
    try:
        os.symlink(copy, link, target_is_directory=True)
    except OSError:
        pytest.skip("can't create symlinks here")

    assert cli.main(["uninstall", "--claude-code"]) == 0
    assert not link.is_symlink() and not link.exists()
    assert (copy / "SKILL.md").exists()

    link.parent.mkdir(parents=True)
    os.symlink(copy, link, target_is_directory=True)
    assert cli.main(["install", "developing", "--claude-code"]) == 0
    assert link.is_dir() and not link.is_symlink()
    assert (copy / "SKILL.md").exists()


@pytest.mark.parametrize(
    ("found", "op", "wanted", "expected"),
    [
        ("1.5.0", ">=", "1.5", True),
        ("1.4.9", ">=", "1.5", False),
        ("2.4.3", "<", "3.0", True),
        ("1.5", "==", "1.5.0", True),
        ("3.0", "!=", "3.0.0", False),
        ("1.5.0rc1", ">=", "1.5", True),
    ],
    ids=[
        "ge",
        "ge_fails",
        "lt",
        "trailing_zero_equal",
        "trailing_zero_not_equal",
        "prerelease_counts_as_release",
    ],
)
def test_satisfies(found, op, wanted, expected):
    assert cli._satisfies(found, op, wanted) is expected


def test_doctor_fails_an_unmet_compatibility_requirement(project, monkeypatch, capsys):
    assert cli.main(["install", "developing", "--claude-code"]) == 0
    versions = {name: None for name in cli.LIBRARIES} | {"panel": "1.4.0"}
    monkeypatch.setattr(cli, "_library_versions", lambda python, names: versions)
    capsys.readouterr()

    assert cli.main(["doctor", "--python", "python"]) == 1
    assert "FAIL panel needs panel>=1.5, found 1.4.0" in capsys.readouterr().out


def test_doctor_reports_an_interpreter_it_cannot_run(project, tmp_path, capsys):
    assert cli.main(["install", "developing", "--claude-code"]) == 0
    missing = tmp_path / "no-such-python"
    capsys.readouterr()

    assert cli.main(["doctor", "--python", str(missing)]) == 1
    assert f"couldn't query {missing}" in capsys.readouterr().out
