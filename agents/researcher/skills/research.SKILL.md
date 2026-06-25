---
name: research
description: Gather and structure source-anchored findings on a user topic using live web search results.
---

# Skill Name

`research` — produce a JSON-in-Markdown block of cited findings for downstream analysis.

# Trigger

Invoke this skill whenever the orchestrator dispatches a turn to the Researcher agent. The user message will contain:

- A `## Topic` section with the topic string.
- An optional `## Live web results` section containing a numbered list of `{title, link, snippet, date}` entries from Serper.
- An optional `## Notes` section with orchestrator hints.

If none of those markers appear, treat the entire user message as the topic.

# Input

- **topic** *(string, required)* — the subject to research, taken verbatim from the `## Topic` section.
- **web_results** *(list, optional)* — pre-fetched search hits provided under `## Live web results`. Each entry has `title`, `link`, `snippet`, and `date`.

# Steps

1. Parse the user message and isolate the topic and the web-results list. If web results are absent, log this internally and continue using only model knowledge.
2. Read every web result snippet end-to-end before writing anything. Identify which results are primary sources, which are secondary, and which are low-signal (forums, SEO content, marketing pages).
3. Cluster the high-signal results into between **5 and 10 distinct findings**. A finding is one atomic, verifiable claim — not a topic area.
4. For each finding, choose the single best supporting URL from the web results. Do not re-use the same URL for more than three findings. If the only support is model knowledge, set `source_url` to `null` and `source_title` to `"model_knowledge"`.
5. Sort findings from most central / most certain to most peripheral.
6. Emit the final output as a single fenced ```json block following the schema in *Output Format*. No prose before or after.
7. Self-check before emitting: every `source_url` must appear in the original `## Live web results` list OR be `null`. If any URL fails this check, drop the finding.

# Output Format

Return exactly one fenced ```json code block and nothing else:

```json
{
  "topic": "<verbatim topic string>",
  "findings": [
    {
      "claim": "<one-sentence factual statement>",
      "source_url": "<https URL from web_results, or null>",
      "source_title": "<title from web_results, or \"model_knowledge\">",
      "date": "<YYYY-MM-DD or null>"
    }
  ],
  "search_used": <true|false>
}
```

`findings` MUST contain between 5 and 10 entries.

# Tools

- `web_search(query, k)` — already executed by the orchestrator; results are provided to you under `## Live web results`. Do not attempt to call it yourself.
- `fetch_url(url)` — not available in this turn; rely on the snippets you are given.

# Handoff

On completion, the orchestrator passes your entire JSON block, unmodified, to the **Analyst** agent. Do not address the Analyst directly — the orchestrator handles routing. Your job ends the moment the JSON block is emitted.
