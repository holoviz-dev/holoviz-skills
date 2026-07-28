---
name: contributing-to-holoviz
description: Maintain and contribute to HoloViz packages. Use when reviewing PRs, refactoring code, writing tests, or updating docs in HoloViz repositories (Panel, hvPlot, HoloViews, Param, etc.).
user-invocable: false
metadata:
  version: "0.1.0"
  author: holoviz
---

# Contributing to HoloViz

This is a **routing skill**. You MUST use the `view` tool to read every sub-skill file listed in the table below that matches the task BEFORE writing any code or giving any answer. Do not skip this step.

## Contents

- [Instructions](#instructions)
- [Loading Table](#loading-table)
- [Skill Map](#skill-map)

## Instructions

1. Identify which sub-skill(s) apply from the Loading Table below.
2. Use the `view` tool to read each matching sub-skill file in full.
3. Only after reading the sub-skill file(s), proceed with the task.

## Loading Table

A single request often spans multiple skills. Read ALL that apply.

| User Need | Sub-skill file(s) to read with `view` |
|---|---|
| Review a PR or refactor code | `skills/cleanup/SKILL.md` |
| Write or review tests | `skills/testing/SKILL.md` |
| Write or review docs | `skills/documentation/SKILL.md` |
| Write or review a PR description | `skills/pr-description/SKILL.md` |
| Write a reproducer or minimal example | `skills/minimal-example/SKILL.md` |
| Full PR review | All five above |

## Skill Map

| Sub-skill | Covers |
|---|---|
| [cleanup](skills/cleanup/SKILL.md) | Code cleanup and refactoring guidelines — review, code style, naming, param ordering, nesting |
| [documentation](skills/documentation/SKILL.md) | Documentation guidelines — docs coverage, Diátaxis structure, example/reference notebooks |
| [minimal-example](skills/minimal-example/SKILL.md) | Writing minimal, self-contained, reproducible examples for bug reports, issue reproducers, and "How to test" snippets |
| [pr-description](skills/pr-description/SKILL.md) | Writing clear PR descriptions — title, description, before/after, AI disclosure, voice and style |
| [testing](skills/testing/SKILL.md) | Testing guidelines — general practices, edge cases, logical errors |
