# Cleanup review fixture

A tiny package for `scripts/eval_cleanup.py`. `pkg/query.py` is the change under
review: the opening snippet from "Deslop AI Slop Part 2: Code", plus a caller so
the helpers it defines are used. The rest of the package already has what the
change rewrites: `pkg/utils.py` has `with_timeout`, and `pkg/sources/duckdb.py`
parses the same error message.

The code here is deliberately sloppy, so leave it as it is.
