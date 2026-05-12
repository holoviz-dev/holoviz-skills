---
name: cleanup
description: Code cleanup and refactoring guidelines for HoloViz packages. Use when reviewing PRs, refactoring code, or checking adherence to code quality standards in any HoloViz repository.
metadata:
  version: "0.0.1"
  author: holoviz
---

# Code Cleanup

This skill covers code quality patterns and common pitfalls when reviewing or refactoring HoloViz code.

## Review

Perform a `git diff` from the PR branch to the main branch, and review the code changes for potential issues, improvements, and adherence to best practices. Then provide a plan, pointing to lines of code and modules for refactoring the code to improve its quality, readability, and maintainability.

## Linting

- Leave formatting and style enforcement to linters and pre-commit hooks. Run via `pixi run lint`.

## Imports

- Top-level imports should only be from the standard library, required dependencies, and relative imports. Imports of optional or slow-loading dependencies should go inside the function that uses them.

## Attribute Access

- Prefer direct attribute access when the attribute is known to exist. `getattr` with a default is appropriate when the attribute may be absent (e.g. checking across class hierarchies or optional mixins) and the caller handles the fallback.

## Holistic Review

- Consider the full set of changes and whether there is a more efficient or cleaner way to achieve the same result. A PR that touches five files to work around a problem may have a simpler two-line fix elsewhere.

## Nesting and Early Returns

- Return or continue early to avoid deep nesting.
- Consolidate multiple guard clauses into a single condition when possible.
- Refactor code with more than three levels of nesting into helper functions.

```python
# WRONG — deeply nested
def process(items):
    results = []
    for item in items:
        if item.is_valid:
            if item.category == 'A':
                if item.value > 0:
                    results.append(transform(item))
    return results

# CORRECT — early continue, flat logic
def process(items):
    results = []
    for item in items:
        if not item.is_valid or item.category != 'A' or item.value <= 0:
            continue
        results.append(transform(item))
    return results
```

## Type Hints

- Prefer Python 3.11+ built-in generics and `|` union syntax for new code. Leave enforcement to the linter.

## File Organization

- Order file contents: imports, constants, functions (or ideally a separate `utils` module), then classes.
- `@staticmethod` is fine when the method is part of the class's public interface or is only meaningful in the context of that class. Move to module level or a `utils` module only if it has clear reuse elsewhere.

## Naming and Style

- Use consistent and readable naming conventions. If a class is `FollowUpSuggestion`, the variable name should be `follow_up_suggestion`, not `followup_suggestion` or `follow_up_suggestions` (plural when singular is meant).
- Sort `param` parameter declarations alphabetically on `Parameterized` classes, with a blank line between each declaration.
- Include `doc="""..."""` on every public param to describe its purpose.

```python
# WRONG — arbitrary order, no docs, no spacing
class MyWidget(param.Parameterized):
    zoom = param.Number(default=1.0)
    alpha = param.Number(default=0.5)
    color = param.String(default='blue')

# CORRECT — alphabetical, spaced, documented
class MyWidget(param.Parameterized):

    alpha = param.Number(default=0.5, doc="""
        The opacity of the widget.""")

    color = param.String(default='blue', doc="""
        The primary color of the widget.""")

    zoom = param.Number(default=1.0, doc="""
        The zoom level of the widget.""")
```
