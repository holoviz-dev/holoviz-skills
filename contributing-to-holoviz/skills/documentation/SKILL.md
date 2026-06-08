---
name: documentation
description: Documentation guidelines for HoloViz packages. Use when writing or reviewing docs, changelog entries, or API references in any HoloViz repository.
metadata:
  version: "0.0.2"
  author: holoviz
---

# Documentation

This skill covers documentation expectations when contributing to HoloViz repositories.

Most HoloViz projects follow the [Diátaxis](https://diataxis.fr/) documentation framework (tutorials, how-to guides, explanation, reference). Place new docs in the appropriate category. If the project doesn't follow Diátaxis yet, match the existing structure.

## Docs Coverage

- New features and enhancements must be documented. A PR that adds a parameter, method, or behavior change without updating docs is incomplete.
- Build docs via pixi. Check `pixi.toml` for the task (e.g. `pixi run docs-build`).

## Example and Reference Notebooks

- Run notebooks and review the rendered output, not just the code: watch for clipping/overlap (e.g. legend over plot), adequate size, and legible labels.
- Demonstrate options representatively, not exhaustively — values distinct enough to show the effect, with `hv.help(...)` for the full list.
- Cover each supported backend; add a per-backend gallery thumbnail if the docs gallery uses them.
