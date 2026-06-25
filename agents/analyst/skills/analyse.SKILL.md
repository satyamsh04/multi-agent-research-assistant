---
name: analyse
description: Compress the Researcher's findings into five evidence-linked insights plus explicit gaps and conflicts.
---

# Skill Name

`analyse` — convert raw findings into a five-insight memo with gaps and conflicts.

# Trigger

Invoke this skill whenever the orchestrator dispatches a turn to the Analyst agent. The user message will contain:

- A `## Topic` section with the original topic string.
- A `## Researcher findings` section holding the Researcher's JSON block verbatim.

# Input

- **topic** *(string, required)* — taken from the `## Topic` section.
- **findings** *(list of objects, required)* — parsed from the JSON block under `## Researcher findings`. Each element has `claim`, `source_url`, `source_title`, and `date`.

# Steps

1. Parse the Researcher's JSON block. If it is malformed, emit an empty insights array and put the parse error under `gaps` as a single string.
2. Build a quick mental index: which URLs support which claims? Drop any finding whose `source_url` is `null` *unless* it is the only support for an otherwise critical claim, in which case keep it and flag the lack of citation in `gaps`.
3. Cluster the surviving findings into thematic buckets. Each bucket becomes one candidate insight.
4. Select exactly **five** insights, ranked from most decision-relevant to least. For each, write a one-sentence `insight` and attach the supporting `evidence` URLs (deduplicated, max five per insight).
5. Identify **gaps**: questions a thoughtful reader would expect a report on this topic to answer that the findings do not address. Aim for 2–4 gaps, each a single sentence.
6. Identify **conflicts**: pairs or groups of findings whose claims disagree. For each conflict, list the disagreeing claims and a one-sentence note explaining the disagreement. Empty array is allowed.
7. Self-check: every `evidence` URL must appear in the Researcher's findings. Drop any URL that does not.
8. Emit the final output as a single fenced ```json block following the schema in *Output Format*. No prose before or after.

# Output Format

Return exactly one fenced ```json code block and nothing else:

```json
{
  "topic": "<verbatim topic string>",
  "insights": [
    {
      "insight": "<one-sentence analytical claim>",
      "evidence": ["<https URL>", "<https URL>"]
    }
  ],
  "gaps": ["<one-sentence gap>"],
  "conflicts": [
    {
      "claims": ["<claim A>", "<claim B>"],
      "note": "<one-sentence explanation of disagreement>"
    }
  ]
}
```

`insights` MUST contain exactly five entries.

# Tools

No external tools. Your only input is the Researcher's JSON block.

# Handoff

On completion, the orchestrator passes your entire JSON block, unmodified, to the **Writer** agent. The Writer will choose 3–5 of your insights for the "Key Findings" section of the report. Your job ends the moment the JSON block is emitted.
