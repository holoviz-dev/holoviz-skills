---
name: cleanup
description: Code cleanup and refactoring guidelines for HoloViz packages. Use when reviewing PRs, refactoring code, or checking adherence to code quality standards in any HoloViz repository.
metadata:
  version: "0.0.3"
  author: holoviz
---

# Code Cleanup

This skill covers code quality patterns and common pitfalls when reviewing or refactoring HoloViz code.

## Review

- Perform a `git diff` from the PR branch to the main branch and review for potential issues, improvements, and adherence to best practices.
- Consider the full set of changes and whether there is a simpler way to achieve the same result. A PR that touches five files to work around a problem may have a two-line fix elsewhere.
- Explain *why* this approach over the alternatives (mixin vs. inheritance vs. duplication); reviewers consistently ask for that rationale.
- Reuse the naming and option behavior of similar existing components instead of inventing a new spelling for the same idea (e.g. `font_size` to match a sibling element, not `fontsize`).
- Don't change an existing default or signature — that breaks users — unless a breaking change is the explicit goal of the PR.
- Share cross-backend/variant logic via a mixin or helper, but extract only what is genuinely common.
- Scrutinize AI-assisted code like any other; flag it and verify the behavior yourself.

## Code Style

- Leave formatting and style enforcement (including type hint syntax) to linters and pre-commit hooks. Run via `pixi run lint`.
- Top-level imports should only be from the standard library, required dependencies, and relative imports. Imports of optional or slow-loading dependencies should go inside the function that uses them.
- Prefer direct attribute access when the attribute is known to exist. `getattr` with a default is appropriate when the attribute may be absent (e.g. checking across class hierarchies or optional mixins) and the caller handles the fallback.
- Order file contents: imports, constants, functions (or a `utils` module), then classes.
- `@staticmethod` is fine when the method is part of the class's public interface or is only meaningful in the context of that class. Move to module level or a `utils` module only if it has clear reuse elsewhere.
- Return or continue early to avoid deep nesting. Prefer comprehensions over loops that just build a list. Refactor code with more than three levels of nesting into helper functions.
- Use consistent naming. If a class is `FollowUpSuggestion`, the variable should be `follow_up_suggestion`, not `followup_suggestion` or `follow_up_suggestions`.
- Sort `param` declarations alphabetically with a blank line between each.
- Include `doc="""..."""` on every public param, starting on a new line.
- Ensure comments are about *why* and *what must remain true*, not what the syntax does. Good comments explain intent, constraints, workarounds, performance rationale, or API quirks. Avoid restating obvious code or narrating line-by-line. Keep them concise; over-explaining is also a smell.
- In tests, put the description of what the test covers and why (including any issue link) in the function docstring, not a leading `#` comment; it then travels with the test in `pytest -v` output. Reserve `#` for a non-obvious step in the body.
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
[transform(item) for item in items if item.is_valid and item.category == 'A' and item.value > 0]
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
