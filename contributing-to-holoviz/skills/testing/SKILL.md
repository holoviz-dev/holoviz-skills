---
name: testing
description: Testing guidelines for HoloViz packages. Use when writing tests, reviewing test coverage in PRs, or identifying missing edge cases in any HoloViz repository.
metadata:
  version: "0.0.2"
  author: holoviz
---

# Testing

This skill covers testing patterns and edge cases specific to HoloViz repositories.

## General Guidelines

- Run tests via pixi. Check `pixi.toml` for tasks (e.g. `pixi run test-unit`, `pixi run test-ui`).
- New tests must fail on `main` before submitting.
- UI tests require the `--ui` flag.
- Only create a new test file if no existing file is a good fit.
- Cover the lines you add; exercise new behavior, don't just import it.

## Edge Cases and Logical Errors

- Identify logical errors and edge cases in the changed code. Trace branching logic and boundary conditions to find inputs that could produce wrong results, silent data loss, or unexpected exceptions.
- Test for NaN and datetime types (np, pd) — these are common edge cases across HoloViz that are easy to miss.
- Also probe (where the logic branches on them): empty/single-element inputs, duplicate/colliding labels, negative/reversed values, unsorted input.
- Parameterize tests when the same logic is exercised with different inputs.
- Name tests for intent; skip comments that just restate what the test does.

```python
# WRONG — only tests the happy path
def test_filter_by_range():
    df = pd.DataFrame({'x': [1, 2, 3]})
    result = filter_by_range(df, 'x', low=1, high=3)
    assert len(result) == 3

# CORRECT — covers edge cases and logical boundaries
@pytest.mark.parametrize(
    ("data", "low", "high", "expected_len"),
    [
        ([1, 2, 3], 1, 3, 3),
        ([1, 2, 3], 2, 2, 1),
        ([1, 2, 3], 5, 10, 0),
        ([], 0, 1, 0),
        ([np.nan, 1, 2], 0, 2, 2),
        ([1, 2, None], 0, 2, 2),
    ],
    ids=[
        "inclusive_bounds",
        "single_value_range",
        "no_matches",
        "empty_input",
        "nan_values",
        "none_values",
    ],
)

def test_filter_by_range(data, low, high, expected_len):
    df = pd.DataFrame({'x': data})
    result = filter_by_range(df, 'x', low=low, high=high)
    assert len(result) == expected_len
```
