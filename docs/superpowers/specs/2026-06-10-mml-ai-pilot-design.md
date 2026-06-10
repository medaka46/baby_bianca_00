# MML AI API Pilot — Design Spec

**Date:** 2026-06-10
**Status:** Approved for planning
**Author:** Mike + Claudy

## Goal

A minimal, standalone FastAPI web app in `LLM_API/` to try the company's
**MML AI API** (a Workato-hosted LLM gateway). The pilot confirms the API works
end-to-end: type a system prompt + user prompt, pick a model, send, and see the
generated text plus token usage. Text prompts only (no file attachment yet).

## The API contract (as provided)

- **Endpoint:** `POST {MML_API_URL}` — the full URL ends in `/invoke_llm`.
- **Auth:** header `API-TOKEN: <token>`.
- **Request body (JSON):**
  - `system_prompt` *(required, string)* — system instruction
  - `user_prompt` *(required, string)* — the question/instruction
  - `model_id` *(optional, string)* — e.g. `global.anthropic.claude-sonnet-4-6`;
    if omitted the gateway defaults to **Gemini 3 Flash**
  - *(out of scope for this pilot)* `file_name_N` + `document_binary_string_N`
    (Base64), N = 1,2,3 — document attachment
- **Response (JSON):**
  - `response_text` *(string)* — generated text
  - `stop_reason` *(string)*
  - `Usage` — `{ input_tokens, output_tokens, total_tokens }`

Because it is a Workato proxy (not the direct Anthropic API), it is called with
a plain HTTP POST via `httpx` — **not** the `anthropic` SDK.

## Architecture (Approach A — standalone)

Self-contained app, isolated from the production `api/` app, run on its own port
(8001). No login / tab-permission system.

```
LLM_API/
  __init__.py
  mml_client.py      # pure, testable client: talks to the Workato endpoint
  app.py             # FastAPI: GET "/" form, POST "/invoke" -> render result
  templates/
    index.html       # form + response display
  README.md          # how to run + required .env vars
test_mml_client.py   # unit tests (mocked HTTP), at project root like other tests
```

### Components

**`mml_client.py`** — the only unit that knows the API.
- `invoke_llm(system_prompt: str, user_prompt: str, model_id: str | None = None) -> dict`
- Builds the JSON payload (omits `model_id` when blank/None so the gateway
  default applies).
- Reads `MML_API_URL` and `MML_API_TOKEN` from the environment; raises a clear
  error if either is missing.
- POSTs with header `API-TOKEN`, a sane timeout (e.g. 60s).
- Returns a normalized dict: `{response_text, stop_reason, input_tokens,
  output_tokens, total_tokens}`.
- Raises a typed error (e.g. `MMLClientError`) carrying the HTTP status and
  body on non-200 responses.
- No web/FastAPI concerns.

**`app.py`** — the web layer.
- `GET "/"` renders the empty form.
- `POST "/invoke"` reads form fields, calls `invoke_llm`, and re-renders the page
  with the response (or an error message). Catches `MMLClientError` and missing
  config, showing a friendly message instead of a 500.
- No knowledge of how the Workato request is built.

**`templates/index.html`** — presentation only.
- Fields: System prompt (textarea), User prompt (textarea).
- Model selector: a dropdown — `Default (Gemini 3 Flash)` and
  `Claude Sonnet 4.6 (global.anthropic.claude-sonnet-4-6)` — plus an optional
  free-text `model_id` box that overrides the dropdown when filled (lets the
  pilot try any model from the pricing page without code changes).
- Send button.
- Response area: `response_text`, `stop_reason`, and the three token counts.
- Keeps the submitted prompts populated after submit for easy iteration.

## Config / secrets

Two new vars added to the existing `.env` (already loaded via `python-dotenv`):
- `MML_API_URL` — the full `…/invoke_llm` URL
- `MML_API_TOKEN` — the API token

Nothing hard-coded; never logged.

## Error handling

| Situation | Behaviour |
|-----------|-----------|
| `MML_API_URL` or `MML_API_TOKEN` missing | Page shows "API not configured — set MML_API_URL and MML_API_TOKEN in .env" |
| Non-200 from gateway | Page shows the status code and response body |
| Timeout / network error | Page shows a friendly "request failed/timed out" message |
| Empty required prompt | Basic validation message; no request sent |

## Testing

- Unit tests for `mml_client.invoke_llm` with a **mocked** `httpx` transport:
  1. **Success** — asserts the request URL, `API-TOKEN` header, JSON payload
     (incl. `model_id` omitted when blank), and that the response is parsed into
     the normalized dict.
  2. **Error** — a 400/500 response raises `MMLClientError` with status + body.
  3. **Missing config** — absent env vars raise a clear error.
- The web page is verified manually: `uvicorn LLM_API.app:app --reload --port
  8001`, then `open http://127.0.0.1:8001/`, send a prompt, confirm the response.

## Dependencies

- `httpx` — used for the POST. Already present transitively (the `anthropic`
  package depends on it); will confirm at implementation and add to
  `requirements.txt` explicitly if needed.

## Out of scope (future)

- Document attachment (the 3 Base64 file slots).
- Multi-turn conversation / history.
- Streaming responses.
- Auth / integration into the main app.

## How to run

```bash
uvicorn LLM_API.app:app --reload --port 8001
open http://127.0.0.1:8001/
```
