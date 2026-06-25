# Multi-Agent Research Assistant

A four-agent (Researcher → Analyst → Writer → Critic) pipeline that turns a
topic into a fact-checked Markdown research report, with a Critic-driven
revision loop and a Streamlit UI. Agent personas are bootstrapped from
OpenClaw-style `SOUL.md` + `SKILL.md` files and executed via the OpenClaw
gateway when available, falling back transparently to OpenAI GPT-4o-mini.

## Architecture

```
            +-----------+        +---------+        +--------+        +--------+
 topic ---> | Researcher| -----> | Analyst | -----> | Writer | -----> | Critic |
            +-----------+        +---------+        +--------+        +--------+
                  |                   |                  ^                |
                  | findings JSON     | insights JSON    |                | score >= 7
                  |                   |                  |                | approve
                  v                   v                  |                v
            (Serper web        (5 insights,              |          rendered .md
             results)           gaps, conflicts)         |          + download
                                                         |
                                                         |   score < 7 / revise
                                                         +-------- revision_notes
                                                                   (max 3 drafts)
```

Orchestration is decoupled from the UI: `research_assistant.pipeline.run_pipeline`
runs the whole sequence and reports progress through callbacks, so the same
logic powers both the Streamlit front-end and the headless test suite.

## Project structure

```
multi-agent-research-assistant/
├── app.py                       # Thin Streamlit UI (wires callbacks -> pipeline)
├── research_assistant/          # UI-agnostic core package
│   ├── config.py                # Settings, secret handling, input validation
│   ├── agents.py                # SOUL + SKILL loading (hot-reloaded per run)
│   ├── search.py                # Serper client (transient-only retries)
│   ├── backends.py              # OpenClaw primary + OpenAI fallback
│   ├── critic.py                # Robust Critic verdict parser (safe fallback)
│   ├── prompts.py               # Per-stage prompt builders
│   └── pipeline.py              # Orchestration + revision loop
├── agents/                      # Agent persona definitions
│   ├── researcher/{SOUL.md, skills/research.SKILL.md}
│   ├── analyst/{SOUL.md, skills/analyse.SKILL.md}
│   ├── writer/{SOUL.md, skills/write_report.SKILL.md}
│   └── critic/{SOUL.md, skills/validate.SKILL.md}
├── tests/                       # Pure-logic tests (no network/keys needed)
├── .env.example
├── .gitignore
└── requirements.txt
```

## Tech stack

| Layer         | Tech               | Purpose                                                           |
|---------------|--------------------|-------------------------------------------------------------------|
| Agent runtime | OpenClaw SDK       | Local gateway that hosts each agent's SOUL.md + SKILL.md bootstrap |
| LLM fallback  | OpenAI GPT-4o-mini | Direct API path used when the OpenClaw gateway is not reachable    |
| Web search    | SerperDev          | Live Google results injected into the Researcher's prompt          |
| UI            | Streamlit          | Topic input, per-stage status, sidebar traces, Markdown download   |

## Setup

1. Clone the repository and `cd multi-agent-research-assistant/`.
2. Install dependencies: `pip install -r requirements.txt`.
   - The OpenClaw SDK is **optional** and intentionally not pinned in
     `requirements.txt`; the app runs end-to-end on the OpenAI fallback. Install
     it separately only if you run a gateway: `pip install "openclaw-sdk>=2.0,<3.0"`.
3. Copy the env template: `cp .env.example .env` (Windows: `copy .env.example .env`).
4. Edit `.env` and add your `OPENAI_API_KEY` and `SERPER_API_KEY` (optionally
   `OPENCLAW_API_KEY`).
5. Launch the app: `streamlit run app.py`.

The app boots even without a running OpenClaw gateway — `run_agent`
auto-falls-back to OpenAI using the same SOUL.md + SKILL.md content as the
system prompt, so every agent persona stays identical across backends.

## Security

- **Secrets stay local.** Keys are read from `.env` via `python-dotenv` and are
  never displayed, logged, or embedded in error messages. The sidebar shows only
  whether each key is *configured*, never its value.
- **`.env` is git-ignored.** `.gitignore` excludes `.env`, key/PEM files, and
  Streamlit secrets; only `.env.example` (placeholders) is tracked.
- **Input validation.** Topics are length-capped (500 chars) and stripped of
  control characters; Serper result counts are clamped to 1–10.
- **No HTML injection.** The final report renders with `unsafe_allow_html=False`,
  and the Researcher prompt instructs the model to treat web snippets as data,
  not instructions (prompt-injection mitigation).
- **No key leakage on failure.** Serper errors surface only the HTTP status code,
  never the response body or request headers.
- **Fail fast, retry sparingly.** Web-search retries are limited to transient
  errors (network, timeout, 429, 5xx); auth/validation errors (401/400) fail
  immediately with a clean message.

## Reliability

- The Critic verdict parser tolerates fenced/bare JSON, prose-wrapped JSON, and
  braces inside string values. If output is unparseable it returns a safe
  fallback (`score=5`, `decision="revise"`) instead of crashing, so a completed
  Writer draft is never lost.
- The revision loop is bounded (1–5 drafts, default 3) and the UI shows the full
  score progression.

## Testing

```bash
pip install pytest
pytest -q
```

The suite covers the Critic parser and input-validation helpers and needs no
network access or API keys.

## Example topics

- "The state of solid-state batteries in 2026"
- "Tradeoffs between RAG and long-context LLMs for enterprise search"
- "Recent regulatory developments in stablecoins"

## Known limitations

- The OpenClaw execution path assumes a local gateway that already knows each
  agent id; without it, the app uses the OpenAI fallback.
- Report quality depends on Serper coverage for the topic; sparse search results
  yield thinner, model-knowledge-only reports.
- Costs scale with the number of revision drafts and the configured model.
