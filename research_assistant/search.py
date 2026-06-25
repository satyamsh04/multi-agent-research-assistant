"""Serper (Google Search) integration.

Only *transient* failures (network errors, timeouts, 429, and 5xx) are retried;
client errors such as 401 (bad key) or 400 (bad request) fail fast so the user
gets an actionable message instead of a multi-second retry storm.
"""

from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .config import SERPER_TIMEOUT_S, clamp_search_results

SERPER_URL = "https://google.serper.dev/search"


class SearchError(RuntimeError):
    """Raised when a web search cannot be completed."""


def _is_transient(exc: BaseException) -> bool:
    """Return True for errors worth retrying (network/timeout/429/5xx)."""
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or 500 <= status < 600
    return False


@retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=8),
    reraise=True,
)
def _post_serper(api_key: str, query: str, k: int) -> dict:
    response = httpx.post(
        SERPER_URL,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": k},
        timeout=SERPER_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()


def web_search(api_key: str | None, query: str, k: int = 8) -> list[dict[str, str]]:
    """Run a Serper query and return a compact list of result dicts.

    Raises :class:`SearchError` (never leaking the API key) on any failure so
    the caller can degrade gracefully to model-only research.
    """
    if not api_key:
        raise SearchError("Serper API key is not configured.")
    query = (query or "").strip()
    if not query:
        raise SearchError("Search query must not be empty.")
    k = clamp_search_results(k)

    try:
        payload = _post_serper(api_key, query, k)
    except httpx.HTTPStatusError as exc:
        # Surface the status code but never the response body or headers, which
        # could echo the request (and therefore the key) back to logs/UI.
        raise SearchError(
            f"Serper returned HTTP {exc.response.status_code}."
        ) from None
    except httpx.HTTPError as exc:
        raise SearchError(f"Serper request failed: {type(exc).__name__}.") from None
    except ValueError as exc:  # JSON decode
        raise SearchError("Serper returned a malformed response.") from None

    results: list[dict[str, str]] = []
    for item in (payload.get("organic") or [])[:k]:
        results.append(
            {
                "title": str(item.get("title", "") or ""),
                "link": str(item.get("link", "") or ""),
                "snippet": str(item.get("snippet", "") or ""),
                "date": str(item.get("date", "") or ""),
            }
        )
    return results


def format_web_results(results: list[dict[str, str]]) -> str:
    """Render Serper hits as a numbered Markdown list for prompt injection."""
    if not results:
        return "_(no live web results available)_"
    lines: list[str] = []
    for idx, hit in enumerate(results, start=1):
        date = f" ({hit['date']})" if hit.get("date") else ""
        lines.append(
            f"{idx}. **{hit['title']}**{date}\n"
            f"   - URL: {hit['link']}\n"
            f"   - Snippet: {hit['snippet']}"
        )
    return "\n".join(lines)
