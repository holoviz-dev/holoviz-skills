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

- Perform a `git diff` from the PR branch to the main branch and review for potential issues, improvements, and adherence to best practices.
- Consider the full set of changes and whether there is a simpler way to achieve the same result. A PR that touches five files to work around a problem may have a two-line fix elsewhere.

## Linting

- Leave formatting and style enforcement (including type hint syntax) to linters and pre-commit hooks. Run via `pixi run lint`.

## Code Structure

- Top-level imports should only be from the standard library, required dependencies, and relative imports. Imports of optional or slow-loading dependencies should go inside the function that uses them.
- Prefer direct attribute access when the attribute is known to exist. `getattr` with a default is appropriate when the attribute may be absent (e.g. checking across class hierarchies or optional mixins) and the caller handles the fallback.
- Order file contents: imports, constants, functions (or a `utils` module), then classes.
- `@staticmethod` is fine when the method is part of the class's public interface or is only meaningful in the context of that class. Move to module level or a `utils` module only if it has clear reuse elsewhere.

## Nesting and Early Returns

- Return or continue early to avoid deep nesting.
- Prefer comprehensions over loops that just build a list.
- Refactor code with more than three levels of nesting into helper functions.

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
    return [
        transform(item)
        for item in items
        if item.is_valid and item.category == 'A' and item.value > 0
    ]
```

## Naming and Style

- Use consistent naming. If a class is `FollowUpSuggestion`, the variable should be `follow_up_suggestion`, not `followup_suggestion` or `follow_up_suggestions`.
- Sort `param` declarations alphabetically with a blank line between each.
- Include `doc="""..."""` on every public param.

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
