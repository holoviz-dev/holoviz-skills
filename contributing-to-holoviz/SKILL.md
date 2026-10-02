---
name: contributing-to-holoviz
description: Maintain and contribute to HoloViz packages. Use when reviewing PRs, refactoring code, writing tests, or updating docs in HoloViz repositories (Panel, hvPlot, HoloViews, Param, etc.).
user-invocable: true
argument-hint: "[review PR | write tests | write docs | PR description | minimal example | deslop | blog post]"
metadata:
  version: "2026.10.01"
  author: holoviz
---

# Contributing to HoloViz

This is a **routing skill**. You MUST read every sub-skill file listed in the table below that matches the task BEFORE writing any code or giving any answer. Do not skip this step.

## Contents

- [Instructions](#instructions)
- [Loading Table](#loading-table)
- [Skill Map](#skill-map)

## Instructions

1. Identify which sub-skill(s) apply from the Loading Table below.
2. Read each matching sub-skill file in full.
3. Only after reading the sub-skill file(s), proceed with the task.

## Loading Table

A single request often spans multiple skills. Read ALL that apply. Paths below are relative to this file's directory (`contributing-to-holoviz/`).

| User Need | Sub-skill file(s) to read |
|---|---|
| Write, change or refactor code | `skills/cleanup/SKILL.md`, `skills/testing/SKILL.md` |
| Review a PR | `skills/cleanup/SKILL.md`, `skills/testing/SKILL.md`, `skills/pr-description/SKILL.md`, `skills/deslop/SKILL.md` |
| Write or review tests | `skills/testing/SKILL.md` |
| Write or review docs | `skills/documentation/SKILL.md`, `skills/deslop/SKILL.md` |
| Write or review a PR description | `skills/pr-description/SKILL.md`, `skills/deslop/SKILL.md` |
| Write a reproducer or minimal example | `skills/minimal-example/SKILL.md` |
| Strip LLM slop from prose | `skills/deslop/SKILL.md` |
| Write or review a blog post | `skills/outreach/SKILL.md`, `skills/outreach/writing-a-blog-post.md`, `skills/deslop/SKILL.md` |

## Skill Map

| Sub-skill | Covers |
|---|---|
| [cleanup](skills/cleanup/SKILL.md) | Code cleanup and refactoring guidelines — whole-repo review, reuse and duplication, error handling and guards, code style, naming, comments, param ordering |
| [deslop](skills/deslop/SKILL.md) | Keep LLM slop out of prose — the HoloViz voice before drafting, then AI vocabulary, rhetorical tics, false-profundity constructions, boilerplate |
| [documentation](skills/documentation/SKILL.md) | Documentation guidelines — docs coverage, prose quality, Diátaxis structure, example/reference notebooks |
| [minimal-example](skills/minimal-example/SKILL.md) | Writing minimal, self-contained, reproducible examples for bug reports, issue reproducers, and "How to test" snippets |
| [outreach](skills/outreach/SKILL.md) | Writing for readers outside a PR — blog posts: reader and point, structure, voice, code, figures, people and sources, review loop |
| [pr-description](skills/pr-description/SKILL.md) | Writing clear PR descriptions — title, description, before/after, AI disclosure, voice and style |
| [testing](skills/testing/SKILL.md) | Testing guidelines — general practices, testing expected behavior, edge cases, logical errors |
