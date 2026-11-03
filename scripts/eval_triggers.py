#!/usr/bin/env python3
"""Check that the skill descriptions get agents to load the right skills.

``eval.py`` points the agent at the skills through ``AGENTS.md``, so it measures
what the skills teach once loaded, not whether an agent finds them on its own.
This eval measures the finding. For each prompt in ``trigger_queries.yaml`` it
installs the skills into a fresh scratch project the way a user would
(``.kilo/skills/``), runs the prompt through ``kilo run`` there, and records
which of our skills the agent loaded, either through its skill tool or by
reading a ``SKILL.md``.

A run passes when the agent loaded every skill in ``expect``, or, for
``expect: []``, none of ours at all. The second kind catches over-triggering,
which costs context on work the skills don't cover.

Usage::

    python scripts/eval_triggers.py
    python scripts/eval_triggers.py --queries blog_post review_pr
    python scripts/eval_triggers.py --models kilo/kilo-auto/free --runs 3

Agents vary between runs, so ``--runs`` repeats each prompt to show a rate
rather than a single verdict. Exit status: 0 if every run passed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import yaml
from build_plugin import find_skill_dirs
from eval import REPO_ROOT, TIMEOUT_RETURNCODE, run_kilo_query

QUERIES = Path(__file__).parent / "trigger_queries.yaml"
# Where `holoviz-skills install --kilo-code` puts skills in a project.
PROJECT_SKILLS = Path(".kilo") / "skills"


def install_skills(project: Path) -> None:
    dest = project / PROJECT_SKILLS
    dest.mkdir(parents=True)
    for skill_dir in find_skill_dirs(REPO_ROOT):
        shutil.copytree(
            skill_dir,
            dest / skill_dir.name,
            ignore=shutil.ignore_patterns(".*", "__pycache__", "test_*.py"),
        )


def skill_names() -> set[str]:
    """Every routing skill and sub-skill name, so other skills the agent has are ignored."""
    return {md.parent.name for d in find_skill_dirs(REPO_ROOT) for md in d.rglob("SKILL.md")}


def skills_loaded(events: list[dict], known: set[str]) -> list[str]:
    """Our skills the agent loaded, in order, from the `kilo run` JSON events."""
    loaded: list[str] = []
    for event in events:
        part = event.get("part") or {}
        tool_input = (part.get("state") or {}).get("input") or {}
        if part.get("tool") == "skill":
            # Match on value rather than a key name, which differs between CLI versions.
            names = [v for v in tool_input.values() if isinstance(v, str) and v in known]
        elif part.get("tool") == "read":
            path = tool_input.get("filePath") or tool_input.get("path") or ""
            names = [Path(path).parent.name] if path.endswith("SKILL.md") else []
        else:
            continue
        loaded.extend(n for n in names if n in known and n not in loaded)
    return loaded


def warn_about_global_skills(known: set[str]) -> None:
    """A global install is visible to every scratch project and would inflate the pass rate."""
    global_dir = Path.home() / PROJECT_SKILLS
    leaked = sorted(p.name for p in global_dir.glob("*") if p.name in known)
    if leaked:
        print(
            f"warning: {global_dir} already has {', '.join(leaked)}; results reflect "
            "those copies too. Uninstall them for a clean run.",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--queries", nargs="*", metavar="ID", help="Only these query ids")
    parser.add_argument("--models", nargs="*", metavar="MODEL", help="Kilo model ids")
    parser.add_argument("--runs", type=int, default=1, help="Runs per prompt (default 1)")
    parser.add_argument("--timeout", type=int, default=300, help="Seconds per run")
    args = parser.parse_args(argv)

    queries = yaml.safe_load(QUERIES.read_text(encoding="utf-8"))
    if args.queries:
        queries = [q for q in queries if q["id"] in args.queries]
    known = skill_names()
    warn_about_global_skills(known)

    passed = failed = 0
    for model in args.models or [None]:
        label = model or "default"
        for query in queries:
            expected = query.get("expect") or []
            for run in range(1, args.runs + 1):
                with tempfile.TemporaryDirectory(prefix="holoviz-trigger-") as tmp:
                    project = Path(tmp)
                    install_skills(project)
                    _, seconds, events, code = run_kilo_query(
                        query["prompt"], model=model, timeout=args.timeout, cwd=project
                    )
                loaded = skills_loaded(events, known)
                if code == TIMEOUT_RETURNCODE or not events:
                    verdict = "ERROR"
                elif expected:
                    verdict = "PASS" if set(expected) <= set(loaded) else "FAIL"
                else:
                    verdict = "PASS" if not loaded else "OVER"
                passed += verdict == "PASS"
                failed += verdict != "PASS"
                run_tag = f" run {run}" if args.runs > 1 else ""
                print(
                    f"{verdict:5} {query['id']}{run_tag} [{label}] "
                    f"expected {', '.join(expected) or 'none'}; "
                    f"loaded {', '.join(loaded) or 'none'} ({seconds:.0f}s)"
                )

    total = passed + failed
    print(f"\n{passed}/{total} runs passed" + (f", {failed} need a look" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
