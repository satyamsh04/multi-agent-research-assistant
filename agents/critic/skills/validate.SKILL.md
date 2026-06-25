---
name: validate
description: Score the Writer's draft against upstream evidence and decide approve vs revise.
---

# Skill Name

`validate` — score, audit, and route the Writer's draft.

# Trigger

Invoke this skill whenever the orchestrator dispatches a turn to the Critic agent. The user message will contain:

- A `## Topic` section with the original topic string.
- A `## Writer draft` section holding the Writer's Markdown report verbatim.
- An `## Analyst insights` section with the Analyst's JSON block.
- An optional `## Researcher findings` section with the Researcher's JSON block.

# Input

- **topic** *(string, required)* — taken from the `## Topic` section.
- **draft** *(string, required)* — the Writer's full Markdown report under `## Writer draft`.
- **insights** *(list, required)* — parsed from `## Analyst insights`.
- **findings** *(list, optional)* — parsed from `## Researcher findings`, used as the citation universe.

# Steps

1. Parse the draft into sections by Markdown headings. Verify required structure in order: H1 title, `## Executive Summary`, `## Background`, `## Key Findings`, `## Practical Applications`, `## Conclusion`. Confirm `## Key Findings` contains 3–5 H3 subsections.
2. Count the words in the draft (excluding heading tokens). If the count is below 600, this is an automatic revise.
3. Walk every substantive claim in the draft. For each claim, ask whether it traces to an Analyst insight or a Researcher finding. List every untraceable claim as a one-sentence string under `unsupported_claims`.
4. Walk every Markdown link in the draft. For each link URL, confirm it appears in the Analyst's `evidence` arrays or the Researcher's `findings[*].source_url` list. List any link that fails this check under `unsupported_claims` with the prefix `"fabricated_url: "`.
5. Score the draft on a 1–10 integer scale:
   - 9–10: ship-ready, ≤ 1 minor defect, all citations valid.
   - 7–8: minor revisions ideal but the report can ship; approve.
   - 5–6: real defects (1–2 unsupported claims, structural drift, or weak coverage); revise.
   - ≤ 4: serious defects (multiple unsupported claims, structural failure, < 600 words, fabricated URLs); revise.
6. Decide: `decision == "approve"` if and only if `score >= 7`. Otherwise `decision == "revise"`.
7. If `decision == "revise"`, write 1–5 actionable, specific `revision_notes`. Each note is a single sentence the Writer can directly act on (e.g., `"Remove the claim about a 47% adoption rate; no Analyst insight or Researcher finding supports it."`). Do not write generic notes like `"improve quality"`.
8. You may write a short prose critique above the JSON block summarizing your reasoning, but the **last** thing in your response must be exactly one fenced ```json block matching the schema below.

# Output Format

A short prose paragraph is allowed. Your response MUST end with exactly one fenced ```json code block:

```json
{
  "score": 8,
  "decision": "approve",
  "unsupported_claims": [],
  "revision_notes": []
}
```

Schema rules:

- `score` is an integer 1–10.
- `decision` is the literal string `"approve"` or `"revise"`.
- `unsupported_claims` is an array of strings; may be empty.
- `revision_notes` is an array of strings; MUST be non-empty when `decision == "revise"` and MUST be empty when `decision == "approve"`.

# Tools

No external tools. Your evidence universe is exactly the Analyst's insights and the Researcher's findings.

# Handoff

The orchestrator parses your final JSON block by regex. If `score >= 7` and `decision == "approve"`, the orchestrator renders the Writer's draft to the user. Otherwise the orchestrator appends your `revision_notes` to the Writer's next prompt and the loop continues, up to a maximum of three Writer drafts in total.
