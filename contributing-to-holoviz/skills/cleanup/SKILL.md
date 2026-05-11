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

## Imports

- Place imports at the top of the file. Avoid imports inside functions unless there is a specific reason (slow import, circular import, optional dependency).

## Attribute Access

- Avoid `hasattr` and `getattr` when the attribute is known to be present. Access it directly — the `AttributeError` on a typo is more useful than a silent fallback.

```python
# WRONG — attribute is always present on this or parent class
color = getattr(self, 'color', None)

# CORRECT
color = self.color
```

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

- Use Python 3.11+ built-in generics and union syntax. No need to import from `typing` for common types.

```python
# WRONG — legacy typing imports
from typing import Dict, List, Optional, Tuple, Union

def process(items: List[str], config: Optional[Dict[str, int]] = None) -> Tuple[str, ...]:
    ...

def load(path: Union[str, Path]) -> None:
    ...

# CORRECT — built-in generics and | syntax
def process(items: list[str], config: dict[str, int] | None = None) -> tuple[str, ...]:
    ...

def load(path: str | Path) -> None:
    ...
```

## File Organization

- Order file contents: imports, constants, functions (or ideally a separate `utils` module), then classes.
- Avoid `@staticmethod` unless it is evidently necessary over a plain function. If the method doesn't access `cls` or `self`, it's usually a function that belongs at module level or in a utils file.

```python
# WRONG — staticmethod that doesn't need the class
class DataProcessor(param.Parameterized):
    @staticmethod
    def normalize(values):
        return (values - values.min()) / (values.max() - values.min())

# CORRECT — plain function at module level or in utils.py
def normalize(values):
    return (values - values.min()) / (values.max() - values.min())

class DataProcessor(param.Parameterized):
    def process(self, values):
        return normalize(values)
```

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

## Magic Numbers

- Minimize magic numbers. Expose the value as a `param` parameter so users can customize it.

```python
# WRONG — hardcoded threshold buried in logic
def process(self, items):
    if len(items) > 50:
        self._paginate(items)

# CORRECT — exposed as a param parameter
class ItemProcessor(param.Parameterized):
    max_items_per_page = param.Integer(default=50, bounds=(1, None), doc="""
        Maximum number of items to display per page before paginating.""")

    def process(self, items):
        if len(items) > self.max_items_per_page:
            self._paginate(items)
```
