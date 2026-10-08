---
name: testing
description: Testing guidelines for HoloViz packages. Use when writing tests, reviewing test coverage in PRs, or identifying missing edge cases in any HoloViz repository.
metadata:
  version: "2026.10.01"
  author: holoviz
---

# Testing

This skill covers testing patterns and edge cases specific to HoloViz repositories.

## Contents

- [General Guidelines](#general-guidelines)
- [Edge Cases and Logical Errors](#edge-cases-and-logical-errors)

## General Guidelines

- Run tests via pixi. Check `pixi.toml` for tasks (e.g. `pixi run test-unit`, `pixi run test-ui`).
- New tests must fail on `main` before submitting, since a test that passes without the fix doesn't test the fix.
- Write tests from the issue or the expected behavior, not from what the new code does. A test written to match the implementation checks the author's assumptions, so it can pass on the very bug it was meant to catch. Agents tend to write this kind of test for their own code.
- Never change a test's expected value just to make it pass. Change it only after confirming the new output is correct, and say why in the PR, since editing the expectation to match wrong output hides the regression the test caught.
- UI tests require the `--ui` flag.
- Only create a new test file if no existing file is a good fit, so tests for one module stay in one place and the next contributor finds them.
- Cover the lines you add; exercise new behavior, don't just import it.

## Edge Cases and Logical Errors

- Identify logical errors and edge cases in the changed code. Trace branching logic and boundary conditions to find inputs that could produce wrong results, silent data loss, or unexpected exceptions.
- Test for NaN and datetime types (np, pd) — these are common edge cases across HoloViz that are easy to miss.
- Also probe (where the logic branches on them): empty/single-element inputs, duplicate/colliding labels, negative/reversed values, unsorted input.
- Parameterize tests when the same logic is exercised with different inputs.
- Name tests for intent. Put what the test covers and why — including any issue link — in the function **docstring**, not a leading `#` comment: the docstring travels with the test in `pytest -v` output. Reserve `#` for a genuinely non-obvious step in the body, and skip comments that just restate what the test does.

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
