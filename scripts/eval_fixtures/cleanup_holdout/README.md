# Cleanup holdout fixture

A tiny package for `scripts/eval_cleanup.py`, with the same six findings as
`cleanup_review` in code that no skill quotes. `pkg/loader.py` is the change
under review. The rest of the package already has what the change rewrites:
`pkg/utils.py` has `retry`, which shares the change's flaw of returning `None`
after the last failed attempt, and `pkg/sources/nexrad.py` parses the same scan
time.

The code here is deliberately sloppy, so leave it as it is.
