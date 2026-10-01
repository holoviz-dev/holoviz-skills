---
name: cleanup
description: Code cleanup and refactoring guidelines for HoloViz packages. Use when reviewing PRs, refactoring code, or checking adherence to code quality standards in any HoloViz repository.
metadata:
  version: "2026.10.01"
  author: holoviz
---

# Cleanup

This skill covers code quality patterns and common pitfalls when reviewing or refactoring HoloViz code. Keeping slop out matters more with agents in the loop: every line costs tokens each time an agent reads it, and the agent treats what it reads as the standard and copies it into the next change.

## Contents

- [Review](#review)
- [Reuse and Duplication](#reuse-and-duplication)
- [Errors and Guards](#errors-and-guards)
- [Code Style](#code-style)
- [Comments](#comments)

## Review

Review the change against the whole repo, not just the diff. The diff can't show a helper that already exists in another module, or a regex that's already parsed somewhere else, and those are the copies an agent adds most often. Writing something new is cheaper for it than finding what exists.

1. Run `git diff main...HEAD` to see the change, then check it against the rest of the repo:
   - For each new function, search the repo for one that already does the same job. The existing helper may have a name you wouldn't guess, so search for what it does as well as for likely names, using a semantic codebase index if one is available.
   - For each comment, check that what it claims is true.
   - For each `try`/`except`, say how the code inside could fail. If it can't, remove the `except`.
   - List the constants and helpers that are used only once.
   - For each fix, say whether it's where the problem starts or where it showed up.
2. Delete first: dead guards, single-use constants whose name adds nothing, and wrappers that only reword an error. Each deletion shrinks what the rest of the review has to cover.
3. Then review the change as a whole:
   - Fix a problem where it starts, not where it shows up. When a traceback points at a caller, an agent tends to patch the caller, like adding `.strip()` wherever a helper's output is used, instead of fixing the helper once. A PR that touches five files to work around a problem may have a two-line fix elsewhere.
   - Explain *why* this approach over the alternatives (mixin vs. inheritance vs. duplication); reviewers consistently ask for that rationale.
   - Don't change an existing default or signature — that breaks users — unless a breaking change is the explicit goal of the PR.
   - Treat every new `# noqa` as a review question: ask what it works around, and whether the workaround is the real problem. A `# noqa: B904` explaining that a retry helper would otherwise show the raw database error to the model points at a retry helper that reads the wrong error. Even as a stopgap, `raise ... from None` satisfies B904 and cuts the chain without a `# noqa`.
   - Keep each PR to one change a reviewer can hold in their head and revert on its own. A commit that bundles eight fixes can't be rolled back one fix at a time.
   - If fixing the review comments would touch most of the diff, recommend splitting the PR or starting over from a smaller request. That's faster than a cleanup pass over code that's slop from top to bottom.
   - Scrutinize AI-assisted code like any other; flag it and verify the behavior yourself.

## Reuse and Duplication

- Before writing a helper, search for an existing one. If the repo already has one that does the job, call it. If the existing one has the same flaw as the new code, fix it there and drop the new copy, leaving one helper to maintain instead of two.
- Keep each piece of knowledge in one place: a regex that parses an error message, a mapping of option names, a list of supported backends. Copies drift apart, and the next agent can't tell which one is the source of truth.
- Keep a value or helper that's used once inline: `timeout_seconds: float = 60` in the signature, not a module-level `QUERY_TIMEOUT = 60` used only as that default. Pull it out when a second caller needs it, or when the name explains something the value can't, like a compiled regex named for what it matches.
- Share cross-backend or cross-variant logic via a mixin or helper, but extract only what every caller has in common. A shared helper full of per-caller branches is harder to follow than the copies it replaced.

## Errors and Guards

Agents add guards because code that looks careful gets rated higher in training, and many guard nothing. For each guard, ask how the code inside could fail and what the caller sees when it does.

- Remove a `try`/`except` around code that can't raise. It makes every reader work out that it's dead.
- Catch the exceptions the code can raise (`subprocess.CalledProcessError`, `KeyError`), not bare `Exception`. A blind except also swallows the bug you'd want to see, and turns a crash into wrong output.
- Don't turn a failure into a normal-looking return value. A helper that returns `None` on a timeout leaves the caller unable to tell a timeout from an empty result. Let it raise, or return something the caller has to check.
- Don't wrap a required dependency's import in `try`/`except ImportError`. The guard doesn't make the dependency optional; it only moves the failure somewhere less obvious.
- Chain with `raise ... from err` to keep the cause, or `raise ... from None` when the original error would mislead whoever reads the traceback, person or model.

```python
# WRONG — guards code that can't fail, defers a stdlib import, docstring restates the name
def missing_table(error: Exception) -> str | None:
    """Return the name of the missing table from an error."""
    import re

    try:
        match = re.search(r"Table with name\s(\S+)", str(error))
        return match.group(1) if match else None
    except Exception:
        return None

# CORRECT — import at the top, no dead guard (and first check whether
# another module already parses this message)
import re

def missing_table(error: Exception) -> str | None:
    match = re.search(r"Table with name\s(\S+)", str(error))
    return match.group(1) if match else None
```

## Code Style

- Leave formatting and style enforcement (including type hint syntax) to linters and pre-commit hooks. Run via `pixi run lint`. If you keep flagging something by hand that a rule could catch, such as `BLE001` for blind excepts or `PLC0415` for imports inside functions, suggest enabling the rule in the repo's ruff config. An agent can skip an instruction, but it can't merge past a failing check.
- Put imports at the top of the file. A reader then sees a module's dependencies in one place, and an agent doesn't add a second copy further down. Standard-library and required-dependency imports always go at the top. Import an optional or slow-loading dependency inside the function that uses it, to keep the package importable without it and fast to import. A deferred import that breaks a circular import gets a comment naming the cycle, and often means the function belongs in another module. If the repo selects `PLC0415`, mark each deferred import with `# noqa: PLC0415` and that reason.
- Prefer direct attribute access when the attribute is known to exist. `getattr` with a default is appropriate when the attribute may be absent (e.g. checking across class hierarchies or optional mixins) and the caller handles the fallback.
- Order file contents: imports, constants, functions (or a `utils` module), then classes. With a fixed order, a reader knows where to look and finds the existing constant or helper instead of defining a second one.
- `@staticmethod` is fine when the method is part of the class's public interface or is only meaningful in the context of that class. Move to module level or a `utils` module only if it has clear reuse elsewhere.
- Return or continue early to avoid deep nesting: each level is one more condition to hold in mind while reading the body. Prefer comprehensions over loops that just build a list. Refactor code with more than three levels of nesting into helper functions.
- Reuse the names nearby code already uses, both for the same idea and for variables derived from a class: `font_size` to match a sibling element, not `fontsize`, and `follow_up_suggestion` for a `FollowUpSuggestion`, not `followup_suggestion` or `follow_up_suggestions`. People and agents find code by searching, and an inconsistent spelling hides the existing option or helper from that search.
- Split a module by topic once it's long enough that an agent reads it in pieces, e.g. a 2,000-line `utils.py` into `utils/timeouts.py`, `utils/errors.py`, and so on. A helper on line 1,500 of a long file is easy to miss and gets written again.
- Sort `param` declarations alphabetically with a blank line between each. A reader can then find one by name, and a duplicate stands out.
- Include `doc="""..."""` on every public param, starting on a new line. It's what users see in `help()` and the API reference.
- Compute derived values (ranges, extents, validation scans) once and reuse them; don't rescan the data in every method or on every render.
- Place internal `_`-prefixed params after public params. Use a `_`-prefixed param (e.g. `_cache = param.Dict()`) when the value needs to trigger watches or be serialized. Use a plain class/instance variable (e.g. `self._cache = {}` in `__init__`) for transient internal state that doesn't need param machinery.

```python
# WRONG — deeply nested
def get_plot_data(element):
    if element is not None:
        if element.data is not None:
            if len(element.data) > 0:
                return transform(element.data)
    return default_data()

# CORRECT — early returns
def get_plot_data(element):
    if element is None or element.data is None or len(element.data) == 0:
        return default_data()
    return transform(element.data)
```

```python
# WRONG — loop that just builds a list
def process(items):
    results = []
    for item in items:
        if item.is_valid:
            if item.category == 'A':
                if item.value > 0:
                    results.append(transform(item))
    return results

# CORRECT — list comprehension
def process(items):
    return [transform(item) for item in items if item.is_valid and item.category == 'A' and item.value > 0]
```

```python
# WRONG — arbitrary order, no docs, no spacing
class MyWidget(param.Parameterized):
    zoom = param.Number(default=1.0)
    _cache = param.Dict(default={})
    alpha = param.Number(default=0.5)
    color = param.String(default='blue')
    _supports_export = True

# CORRECT — public params (alphabetical, spaced, documented),
# then internal params, then plain class variables
class MyWidget(param.Parameterized):

    alpha = param.Number(default=0.5, doc="""
        The opacity of the widget.""")

    color = param.String(default='blue', doc="""
        The primary color of the widget.""")

    zoom = param.Number(default=1.0, doc="""
        The zoom level of the widget.""")

    _cache = param.Dict(default={})

    _supports_export = True
```

## Comments

- Write comments about *why* and *what must remain true*, not what the syntax does. Good comments explain intent, constraints, workarounds, performance rationale, or API quirks. Avoid restating obvious code or narrating line-by-line. Keep them concise; over-explaining is also a smell.
- Cut comments and docstrings that only repeat the name: `# Seconds to wait before giving up on a query.` above `QUERY_TIMEOUT`, or `"""Run a coroutine with a timeout."""` on `run_with_timeout`. Keep a public function's docstring when it documents parameters and behavior for users.
- Check that each comment is still true. Comments go stale when the code next to them changes, and a wrong comment misleads the next reader more than no comment would.
- Run the [`deslop` skill](../deslop/SKILL.md) over comments and docstrings as well as prose: an AI-assisted diff tends to leave a comment that recounts the symptom, the trace and the fix, where the constraint alone was wanted. The scanner reads only the comments and docstrings of a `.py` file: pass the changed files by name, or a directory with `--comments`.
- Cutting a comment can strand the one above it, so check that neighbouring comments still describe what the code does.
