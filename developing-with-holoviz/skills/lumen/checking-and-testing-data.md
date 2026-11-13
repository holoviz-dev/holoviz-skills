# Checking and Testing Data

Look at data before asking about it, assert rules it should keep, and test code built on `ask` without calling an LLM in CI.

## Contents

- [Overview Before Asking](#overview-before-asking)
- [Data Rules with check](#data-rules-with-check)
- [Testing Code That Asks](#testing-code-that-asks)
  - [Cassettes](#cassettes)
  - [Privacy of Recordings](#privacy-of-recordings)

## Overview Before Asking

```python
source.overview()                   # columns, types, nulls, ranges, quality flags, 5 suggested questions
source.overview(questions=False)    # same without the one LLM call that writes the questions
```

Flags cover missing values, duplicate rows, padded text, numbers stored as text, constant columns and outliers, from the first 5,000 rows. Large tables get distinct counts and ranges from a sample, and the overview says so. In a notebook each suggested question is a button that asks it. Run this first when the user does not know the data: the ranges tell you which questions it can answer at all.

## Data Rules with check

```python
source.check("SELECT * FROM penguins WHERE body_mass_g <= 0")   # runs as written, no LLM
source.check("no penguin weighs under 2 kg")                     # one LLM call writes the SELECT
```

- The rule is a SELECT that returns the **offending** rows, or plain language.
- The result is falsy when rows break the rule, so `assert source.check(...)` works in pytest; the failure message shows the rule, the query, the count and the first rows.
- `result.count` is how many rows break it (`result.passed` is `count == 0`), `result.rows` up to 1,000 of them in the input's type, `result.sql` the query; `result.raise_()` raises the same message outside pytest.
- Only read-only queries run, including SQL the LLM writes.
- `table=` names the table when the source has several and the rule is plain language.

Keep tests LLM-free: write a plain-language rule once, then paste its `result.sql` into the test.

```python
def test_no_negative_mass():
    assert source.check("SELECT * FROM penguins WHERE body_mass_g <= 0")
```

## Testing Code That Asks

### Cassettes

`lumen.ai.testing` records a real LLM's responses once and replays them, so tests of code built on `ask` run offline, fast and deterministic:

```python
from lumen.ai.testing import cassette

def test_penguins_in_2008(source):
    with cassette("tests/cassettes/penguins_2008.json") as llm:
        answer = source.ask("How many penguins were measured in 2008?", llm=llm, returns=int)
    assert answer.result == 114
```

- `cassette(path)` **replays** by default. Record once with `LUMEN_AI_RECORD=1 pytest ...` (uses the configured LLM) or `cassette(path, llm)`, then commit the JSON.
- A call that was not recorded raises `MissingRecording` naming the closest recorded call, usually because a prompt changed. Record again.
- Recording replaces the file; `record(llm, path, append=True)` keeps old calls. `record(llm, path)` and `ReplayLLM(path)` are the two halves for use outside a `with` block.
- Tool calls replay as their final answer; the tools do not run again.
- Pin the agents and options in the test the same way when recording and replaying, or the prompts differ and miss.

```python
# WRONG: a live LLM in CI is slow, costs money and flakes
def test_count():
    assert source.ask("How many rows?").result == 344
# CORRECT: replay a recording
def test_count():
    with cassette("tests/cassettes/count.json") as llm:
        assert source.ask("How many rows?", llm=llm, returns=int).result == 344
```

### Privacy of Recordings

A cassette holds every response and the start of each prompt; at the default `share="sample"` both can carry values from the data. Review the file before committing, or record with `cassette(path, preview=False)` to leave the prompts out (a replay miss then cannot name the closest call).
