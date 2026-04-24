---
name: your-skill-name
description: What the skill does AND when to use it, in third person. Example — "Extracts text and tables from PDF files. Use when the user mentions PDFs or forms."
# dependencies: python>=3.8, pandas>=1.5.0   # optional
---

# Your Skill Name

One-line summary of what this skill does.

Frontmatter rules:

- name:        ≤64 chars, lowercase + hyphens, no "anthropic" or "claude"
- description: ≤1024 chars (claude.ai limit), third person, must say WHAT and WHEN
- dependencies: optional; list packages your scripts need
- version: optional; add the current version of this skill

Keep this file under ~500 lines. Delete sections you don't need.

## When to use

- [Concrete situation that should trigger this skill]
- [Another situation]

Do not use for: [adjacent task with a better-suited tool, if any].

## Instructions

[Core procedure. Use prose for flexible tasks; numbered steps for fragile ones.
Explain *why* things matter — agents follows reasoning better than ALL CAPS rules.]

1. [Step one]
2. [Step two]
3. Validate the result. If it fails, return to step [N] and retry.

## Examples

**Input:** [realistic input]

**Output:** [what the skill should produce]

## Resources

- [Primary docs](https://example.com)

### References

This template was built from Anthropic's official Skills documentation:

- [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Quickstart](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/quickstart)
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [How to create custom Skills (Help Center)](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)
