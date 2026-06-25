---
name: write_report
description: Render the Analyst's insights into a structured, source-cited Markdown research report of at least 600 words.
---

# Skill Name

`write_report` — produce a five-section Markdown research report from the Analyst's insights.

# Trigger

Invoke this skill whenever the orchestrator dispatches a turn to the Writer agent. The user message will contain:

- A `## Topic` section with the original topic string.
- An `## Analyst insights` section holding the Analyst's JSON block verbatim.
- An optional `## Researcher findings` section with the Researcher's JSON block (for additional citation URLs).
- An optional `## Revision notes from Critic` section with bullet points from a prior Critic pass — present only on draft 2 and beyond.

# Input

- **topic** *(string, required)* — taken from the `## Topic` section.
- **insights** *(list, required)* — parsed from the JSON block under `## Analyst insights`.
- **findings** *(list, optional)* — parsed from the JSON block under `## Researcher findings`, used as a citation pool.
- **revision_notes** *(list of strings, optional)* — present on revision passes; each note is a hard requirement to address in this draft.

# Steps

1. Parse the Analyst's insights and, if present, the Researcher's findings into in-memory lists.
2. If `revision_notes` is present, read each note and plan which section will absorb the fix. Each note must be addressed in this draft; do not defer.
3. Choose 3–5 insights for the **Key Findings** section, preferring those with the strongest evidence arrays and the broadest decision relevance.
4. Draft the report top-down in this exact section order, using the H1 title `# <Topic Title>`:
   - `## Executive Summary` — 3–5 sentences summarizing the most important conclusions a busy reader needs.
   - `## Background` — 1–2 paragraphs of context, scoped strictly to material the Analyst surfaced.
   - `## Key Findings` — 3 to 5 H3 subsections, one per chosen insight. Each subsection is 2–4 short paragraphs. Cite each substantive claim inline with a Markdown link to an Analyst evidence URL.
   - `## Practical Applications` — concrete, actionable implications drawn only from the insights. Bullet list or short paragraphs.
   - `## Conclusion` — one tight paragraph synthesizing the report. No new facts.
5. After drafting, count the total words. If under 600, expand the weakest section with substance from the insights (never filler). Re-count.
6. Self-check: every Markdown link's URL must appear either in the Analyst's `evidence` arrays or in the Researcher's `findings[*].source_url` list. Drop any link that fails this check rather than fabricate.
7. Emit the final output as raw Markdown. No fenced code blocks wrapping the report, no JSON, no preamble.

# Output Format

The entire response is the Markdown report itself, beginning with `# <Topic Title>` and ending with the final paragraph of the Conclusion. Required structure, in order:

```
# <Topic Title>

## Executive Summary
...

## Background
...

## Key Findings

### <Insight 1 Title>
...

### <Insight 2 Title>
...

### <Insight 3 Title>
...

## Practical Applications
...

## Conclusion
...
```

Minimum length: 600 words. No trailing references section — citations are inline.

# Tools

No external tools. Your only inputs are the Analyst's insights, the Researcher's findings (as a citation pool), and any Critic revision notes.

# Handoff

On completion, the orchestrator passes your Markdown report, unmodified, to the **Critic** agent for scoring. If the Critic approves (score ≥ 7 and decision == "approve"), the orchestrator renders your draft to the user. Otherwise the Critic's notes return to you for another pass, up to a maximum of three drafts in total.
