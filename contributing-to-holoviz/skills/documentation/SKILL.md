---
name: documentation
description: Documentation guidelines for HoloViz packages. Use when writing or reviewing docs, changelog entries, or API references in any HoloViz repository.
metadata:
  version: "0.0.1"
  author: holoviz
---

# Documentation

This skill covers documentation expectations when contributing to HoloViz repositories.

Most HoloViz projects follow the [Diátaxis](https://diataxis.fr/) documentation framework (tutorials, how-to guides, explanation, reference). Place new docs in the appropriate category. If the project doesn't follow Diátaxis yet, match the existing structure.

## Docs Coverage

- New features and enhancements must be documented. A PR that adds a parameter, method, or behavior change without updating docs is incomplete.
- Build docs via pixi. Check `pixi.toml` for the task (e.g. `pixi run docs-build`).
