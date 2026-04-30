---
name: your-skill-name (≤64 chars, lowercase + hyphens)
description: What the skill does AND when to use it, in third person. Example — "Extracts text and tables from PDF files. Use when the user mentions PDFs or forms." (≤1024 chars (claude.ai limit), third person, must say WHAT and WHEN)
# version: 0.0.1
# dependencies: python>=3.8   # optional
---

# Your Skill Name

One-line summary of what this skill does.

Keep this file under ~500 lines. Focus on patching hallucinations and filling
knowledge gaps: API gotchas, deprecated patterns, and non-obvious conventions.
Don't restate general knowledge or upstream docs.

Structure for progressive disclosure: put essentials here in SKILL.md, split
detailed references or advanced workflows into separate files that the agent
loads only when needed.

## Instructions

Core procedure for the skill. Only include what the model gets wrong or can't
know from its training data.

Use prose for flexible tasks; numbered steps for fragile sequences where order
matters. Explain *why* a rule exists; LLMs follow reasoning better than bare
directives.

## Examples

Concrete input → output pairs. At least 2–3 covering common and edge cases.

**Input:** [realistic user request]

**Output:** [what the skill should produce: code, file, or response]

## Resources

- [Primary docs](https://holoviz.com)

### References

This template heavily references Anthropic's official Skills docs:

- [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Quickstart](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/quickstart)
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [How to create custom Skills](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)
