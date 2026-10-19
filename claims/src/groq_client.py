#!/usr/bin/env python3
"""Stdlib-only LLM client for the claims pipeline. Two backends, selected
via LLM_BACKEND ("ollama" or "groq", default "ollama" as of 11 Sep 2026 --
see below for why):

  - Local Ollama (default): no rate limit, no cost, bounded only by this
    machine's own hardware. Model defaults to qwen2.5:14b-instruct-q4_K_M --
    chosen empirically, not by assumption. Real 3-way test on one real
    22K-char chunk of the Anthropic source (SRC15), same prompt, same
    quote-verification check:
      gpt-oss:20b              -- 1 claim,  100% verified,   4.9s/chunk
      qwen2.5:1.5b-instruct    -- 0 claims (used full budget, unparseable), 27s
      qwen2.5:14b-instruct-q4  -- 23 claims,  96% verified, 138s/chunk
    gpt-oss:20b is NOT thin because of a bug -- its own `thinking` trace
    admitted it: "Need many claims. Due to time, produce few? ... Probably
    produce some sample." It's a reasoning model tuned to converge on one
    good answer, not to exhaustively enumerate every claim in a document --
    the wrong shape for this task, confirmed by trying `think` at low/
    medium/high (medium and high made it WORSE: the entire token budget
    went to hidden reasoning and it never reached any output at all).
    qwen2.5:14b-instruct is a plain instruct model with no hidden-reasoning
    tax, and it did the job thoroughly and precisely -- 138s/chunk is slow
    next to Groq's ~4s, but slow-and-complete beats fast-and-empty for a
    pipeline whose entire point is exhaustive claim coverage. Override
    with OLLAMA_MODEL / OLLAMA_HOST env vars if you want to re-check this
    against a different candidate later.
  - Groq cloud API (LLM_BACKEND=groq): kept fully working, not removed --
    see the historical notes below for why we moved off it as the default.

Both backends return the same OpenAI-style {"choices":[{"message":{...}}],
"usage":{...}} shape, so extract_claims.py / corroborate.py need ZERO
changes to work with either -- they only ever call call_groq() /
extract_message_text() / call_budget_used(), never touch the wire format.
Kept the filename groq_client.py (not renamed to something backend-neutral)
specifically so nothing importing `from groq_client import ...` needed to
change when the default backend did.

Why the default moved off Groq (real, verified history, 11 Sep 2026):
  - Groq's Cloudflare front-end 403s (Cloudflare error 1010, "banned based
    on your browser's signature") on Python's default urllib User-Agent --
    a real browser-shaped UA is required.
  - `openai/gpt-oss-120b` is a reasoning model: without `reasoning_effort`,
    a trivial call spent ALL of a 100-token budget on hidden reasoning and
    returned empty content (finish_reason="length"). `reasoning_effort:
    "low"` cut that from 98 to 15 tokens with correct output still produced.
  - The account's token-per-minute limit is a genuine ~8000-tokens/minute
    ACCOUNT-level cap (confirmed identical across 4 different models), not
    a fast-refilling per-second bucket. Chunking (see extract_claims.py)
    keeps individual requests under it, but the account-wide budget still
    means real waits between calls, and -- confirmed directly from the
    Groq dashboard after several hours of real use tonight -- occasional
    `Retry-After` values of tens of minutes on top of the routine ~40-60s
    per-minute-budget waits. Locally-run Ollama has neither constraint.
  - Ollama's own gotcha, found the hard way in a DIFFERENT part of this
    project (a separate second-monitor experiment, not part of this release): its `format`
    JSON-schema-constrained decoding silently returns an EMPTY response
    when combined with a gpt-oss-family model's hidden reasoning channel.
    Fix carried over here too: never pass `format` to Ollama; ask for the
    JSON shape in the prompt text instead (prompt_extract.txt /
    prompt_corroborate.txt already do this) and parse strictly, same as
    the Groq path already did.
"""

from __future__ import annotations

import json
import os
import re
import signal
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY_PATH = HERE.parent / ".groq_key"
OPENROUTER_KEY_PATH = HERE.parent / ".openrouter_key"
SAMBANOVA_KEY_PATH = HERE.parent / ".sambanova_key"

BACKEND = os.environ.get("LLM_BACKEND", "ollama").lower()  # "ollama" (default), "groq", "openrouter", or "sambanova"

# Same open-weight model, three cloud hosts -- openrouter/sambanova are
# same-model failovers for when Groq's connection hangs or rate-limits,
# not different models in the comparison. Model id differs per host:
# groq/openrouter both use the "openai/" prefix, sambanova doesn't.
GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
SAMBANOVA_ENDPOINT = "https://api.sambanova.ai/v1/chat/completions"
SAMBANOVA_MODEL = "gpt-oss-120b"

if BACKEND == "openrouter":
    CLOUD_ENDPOINT = OPENROUTER_ENDPOINT
    CLOUD_MODEL = GROQ_MODEL
elif BACKEND == "sambanova":
    CLOUD_ENDPOINT = SAMBANOVA_ENDPOINT
    CLOUD_MODEL = SAMBANOVA_MODEL
else:
    CLOUD_ENDPOINT = GROQ_ENDPOINT
    CLOUD_MODEL = GROQ_MODEL
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b-instruct-q4_K_M")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

MODEL = OLLAMA_MODEL if BACKEND == "ollama" else CLOUD_MODEL

SELF_THROTTLE_SECONDS = 1.0
MAX_RETRIES_429 = 5
MAX_RETRIES_5XX = 3
TPM_LIMIT = 8000  # real measured Groq account-level cap, see module docstring; irrelevant for ollama

# SIGALRM backstop, per backend: Ollama generating up to ~1500 tokens locally
# on CPU/unified-memory can legitimately take longer than a cloud call, plus
# a one-time ~8s model-load cost if it had been idle -- give it real margin
# rather than reusing Groq's tighter ceiling and risking a false kill.
HARD_TIMEOUT_SECONDS = 600 if BACKEND == "ollama" else 150
# bumped from 300 on 2026-09-13: a real corroborate.py batch (medium
# reasoning_effort, up to 3000 output tokens) exceeded the old 290s socket
# timeout and crashed the whole pipeline mid-run -- that was genuine slow
# generation under this session's GPU contention, not a stuck connection.


def _alarm_handler(signum, frame):  # noqa: ARG001
    raise GroqHangError(f"backend call exceeded hard {HARD_TIMEOUT_SECONDS}s SIGALRM safety timeout")


_last_call_ts: float = 0.0
_remaining_tokens: int | None = None
_reset_tokens_seconds: float = 5.0


class GroqError(RuntimeError):
    pass


class RequestTooLargeError(GroqError):
    """413 (Groq backend only) -- the request itself exceeds the account's
    token budget even fully replenished. Caller must reduce request size
    (smaller chunk), not just retry the same payload."""


class GroqHangError(GroqError):
    """Hard safety-net timeout fired via SIGALRM, NOT urllib's own `timeout=`
    parameter. Confirmed happening in practice, twice, on this network (a
    corporate VPN proxy in the path):
    urlopen(timeout=90) simply did not bound the call. Both times, the
    process sat with a CLOSE_WAIT (or stale CLOSED) socket and literally
    zero CPU-time movement for 40-90+ minutes -- not slow, genuinely stuck,
    confirmed by taking two ps/lsof snapshots seconds apart and seeing no
    change at all. A per-socket Python timeout doesn't help when the hang
    is below that layer. SIGALRM forcibly interrupts the blocking syscall
    so the pipeline fails loud within HARD_TIMEOUT_SECONDS instead of
    hanging for hours. Not retried automatically -- everything up to the
    failing source is already safely on disk (extract_claims.py persists
    after every completed source), so just re-run with --sources for
    whatever's left."""


def estimate_tokens(text: str) -> int:
    """Rough chars/4 estimate for pre-flight budget checks. Not exact --
    real usage always comes from the response's `usage` field -- but good
    enough to decide whether to wait before sending (Groq backend only)."""
    return len(text) // 4 + 1


def _parse_duration(s: str) -> float:
    """Parses Groq's duration strings: '1.485s', '26.4s', '1m26.4s'."""
    m = re.match(r"(?:(\d+)m)?([\d.]+)s", s)
    if not m:
        return 5.0
    minutes = float(m.group(1) or 0)
    seconds = float(m.group(2) or 0)
    return minutes * 60 + seconds


def _record_headers(headers) -> None:
    global _remaining_tokens, _reset_tokens_seconds
    remaining = headers.get("x-ratelimit-remaining-tokens")
    reset = headers.get("x-ratelimit-reset-tokens")
    if remaining is not None:
        _remaining_tokens = int(remaining)
    if reset is not None:
        _reset_tokens_seconds = _parse_duration(reset)


def wait_for_token_budget(estimated_need: int) -> None:
    """Groq backend: sleep if the known remaining budget is too small for
    the upcoming request, rather than firing a call guaranteed to 413.
    Ollama backend: no-op -- there is no external token budget to wait for,
    the only limit is this machine's own generation speed."""
    if BACKEND == "ollama":
        return
    global _remaining_tokens
    if _remaining_tokens is not None and _remaining_tokens < estimated_need:
        sleep_for = max(_reset_tokens_seconds, 1.0)
        print(
            f"  [throttle] ~{_remaining_tokens} tokens left, need ~{estimated_need} "
            f"-- waiting {sleep_for:.1f}s for budget to refill"
        )
        time.sleep(sleep_for)
        _remaining_tokens = None  # unknown until next response headers arrive


def _get_key() -> str:
    if BACKEND == "openrouter":
        env_key = os.environ.get("OPENROUTER_API_KEY")
        if env_key:
            return env_key.strip()
        if OPENROUTER_KEY_PATH.exists():
            return OPENROUTER_KEY_PATH.read_text().strip()
        raise GroqError(
            f"No OPENROUTER_API_KEY found: set the env var or put the key in {OPENROUTER_KEY_PATH} (chmod 600, gitignored)."
        )
    if BACKEND == "sambanova":
        env_key = os.environ.get("SAMBANOVA_API_KEY")
        if env_key:
            return env_key.strip()
        if SAMBANOVA_KEY_PATH.exists():
            return SAMBANOVA_KEY_PATH.read_text().strip()
        raise GroqError(
            f"No SAMBANOVA_API_KEY found: set the env var or put the key in {SAMBANOVA_KEY_PATH} (chmod 600, gitignored)."
        )
    env_key = os.environ.get("GROQ_API_KEY")
    if env_key:
        return env_key.strip()
    if KEY_PATH.exists():
        return KEY_PATH.read_text().strip()
    raise GroqError(
        f"No GROQ_API_KEY found: set the env var or put the key in {KEY_PATH} (chmod 600, gitignored)."
    )


def _throttle() -> None:
    global _last_call_ts
    elapsed = time.time() - _last_call_ts
    if elapsed < SELF_THROTTLE_SECONDS:
        time.sleep(SELF_THROTTLE_SECONDS - elapsed)
    _last_call_ts = time.time()


def _with_alarm(fn):
    """Arm the SIGALRM hang-backstop around exactly one blocking network
    call, then always disarm -- never around a subsequent retry/backoff
    sleep (a real bug, found and fixed the hard way: an alarm that also
    wrapped a legitimate long `Retry-After` sleep fired mid-wait and killed
    a correct backoff, misdiagnosed at first as a stuck network call)."""
    old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(HARD_TIMEOUT_SECONDS)
    try:
        return fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


_thinking_capable_cache: dict[str, bool] = {}


def _model_supports_thinking(model: str) -> bool:
    """Not every local model supports Ollama's `think` field -- confirmed
    directly: sending it to qwen2.5:1.5b-instruct gets a 400 `"...does not
    support thinking"`. Query /api/show once per model and cache it, rather
    than hardcoding a list of which models are reasoning models."""
    if model in _thinking_capable_cache:
        return _thinking_capable_cache[model]
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/show",
            data=json.dumps({"model": model}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            info = json.loads(r.read())
        supported = "thinking" in (info.get("capabilities") or [])
    except Exception:  # noqa: BLE001
        supported = False
    _thinking_capable_cache[model] = supported
    return supported


def _call_ollama(
    messages: list[dict],
    reasoning_effort: str,
    temperature: float,
    seed: int,
    max_tokens: int,
    timeout: int,
) -> dict:
    payload_dict = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        # Deliberately NOT setting `format` -- see module docstring:
        # confirmed this silently empties gpt-oss's response when
        # combined with its hidden reasoning channel. The prompt
        # templates already ask for the JSON shape in plain text.
        "options": {"temperature": temperature, "seed": seed, "num_predict": max_tokens},
    }
    if _model_supports_thinking(OLLAMA_MODEL):
        # Ollama's equivalent of Groq's reasoning_effort for gpt-oss --
        # WITHOUT this, confirmed directly: even a 4KB document burned the
        # entire token budget on hidden "thinking" and left `content`
        # completely empty (0 claims parsed, no error at all -- the exact
        # same failure class the Groq-side findings docs already documented
        # for this model family, just reached via a different door).
        payload_dict["think"] = reasoning_effort
    payload = json.dumps(payload_dict).encode()
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat", data=payload, headers={"Content-Type": "application/json"}
    )

    def _do():
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.URLError as e:
            raise GroqError(
                f"Ollama unreachable at {OLLAMA_HOST} (is `ollama serve` running? "
                f"is {OLLAMA_MODEL} pulled?): {e}"
            )
        except TimeoutError as e:
            # Real, verified case: qwen2.5:14b-instruct on a big chunk (12
            # chunks needed for the HF blog source) legitimately took longer
            # than a too-tight per-request socket timeout, well under the
            # SIGALRM backstop (HARD_TIMEOUT_SECONDS) that would otherwise
            # catch a genuine hang -- this isn't a hang, just slow local
            # generation on a bigger/harder chunk than our one measured
            # sample. Surfaced as a clear GroqError (caller can retry the
            # same chunk manually via --sources) instead of a raw traceback.
            raise GroqError(
                f"local Ollama call exceeded socket timeout={timeout}s (not the "
                f"{HARD_TIMEOUT_SECONDS}s hang backstop -- this was slow generation, "
                f"not a stuck connection): {e}"
            )

    raw = _with_alarm(_do)
    msg = raw.get("message", {})
    prompt_tokens = raw.get("prompt_eval_count", 0)
    completion_tokens = raw.get("eval_count", 0)
    # Normalized into the same shape the Groq cloud response has, so
    # extract_message_text() / call_budget_used() work unmodified.
    return {
        "choices": [{"message": {"content": msg.get("content", ""), "reasoning": msg.get("thinking")}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _call_groq_cloud(
    messages: list[dict],
    reasoning_effort: str,
    temperature: float,
    seed: int,
    top_p: float,
    max_tokens: int,
    timeout: int,
) -> dict:
    key = _get_key()
    body = json.dumps(
        {
            "model": CLOUD_MODEL,
            "messages": messages,
            "temperature": temperature,
            "seed": seed,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "reasoning_effort": reasoning_effort,
        }
    ).encode()

    backoff = 1.0
    attempt = 0
    while True:
        _throttle()
        req = urllib.request.Request(
            CLOUD_ENDPOINT,
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": UA,
            },
        )

        def _do():
            with urllib.request.urlopen(req, timeout=timeout) as r:
                _record_headers(r.headers)
                return json.loads(r.read())

        try:
            return _with_alarm(_do)
        except urllib.error.HTTPError as e:
            _record_headers(e.headers)
            attempt += 1
            retry_after = None
            if e.code == 413:
                body_text = e.read().decode("utf-8", errors="replace")
                raise RequestTooLargeError(f"HTTP 413: {body_text[:400]}")
            if e.code == 429:
                if attempt > MAX_RETRIES_429:
                    raise GroqError(f"429 rate-limited after {MAX_RETRIES_429} retries")
                retry_after = e.headers.get("Retry-After")
                sleep_for = float(retry_after) if retry_after else backoff
                backoff = min(backoff * 2, 16)
            elif 500 <= e.code < 600:
                if attempt > MAX_RETRIES_5XX:
                    raise GroqError(f"{e.code} server error after {MAX_RETRIES_5XX} retries")
                sleep_for = backoff
                backoff = min(backoff * 2, 16)
            else:
                body_text = e.read().decode("utf-8", errors="replace")
                raise GroqError(f"HTTP {e.code}: {body_text[:500]}")

        # Only reached via the 429/5xx branches above. Sleep OUTSIDE the
        # alarm's scope (handled by _with_alarm already returning/raising),
        # however long the server actually asked for.
        print(f"  [429/5xx backoff] waiting {sleep_for:.1f}s before retry "
              f"{attempt}/{MAX_RETRIES_429}" + (" (server-specified Retry-After)" if retry_after else ""))
        time.sleep(sleep_for)


def call_groq(
    messages: list[dict],
    reasoning_effort: str = "low",
    temperature: float = 0,
    seed: int = 42,
    top_p: float = 1,
    max_tokens: int = 4000,
    # Just under HARD_TIMEOUT_SECONDS so the SIGALRM backstop -- not this
    # per-request socket timeout -- is what actually bounds a real hang.
    # Confirmed necessary: qwen2.5:14b-instruct legitimately took >180s on
    # at least one real chunk (the old default), which is slow generation
    # on a bigger/harder chunk, not a hang.
    timeout: int = HARD_TIMEOUT_SECONDS - 10,
) -> dict:
    """Returns an OpenAI-shaped response dict regardless of backend. Raises
    RequestTooLargeError (Groq 413, caller must shrink the request) or
    GroqError (other unrecoverable failure, either backend)."""
    if BACKEND == "ollama":
        return _call_ollama(messages, reasoning_effort, temperature, seed, max_tokens, timeout)
    return _call_groq_cloud(messages, reasoning_effort, temperature, seed, top_p, max_tokens, timeout)


def extract_message_text(response: dict) -> tuple[str, str | None]:
    """Returns (content, reasoning_or_None)."""
    msg = response["choices"][0]["message"]
    # .get(key, default) only falls back when the KEY is absent -- a
    # response with content explicitly null (e.g. reasoning ate the whole
    # output budget) still returns None here, which crashed every caller
    # that calls .splitlines() on it downstream.
    return msg.get("content") or "", msg.get("reasoning")


def call_budget_used(response: dict) -> dict:
    return response.get("usage", {})


if __name__ == "__main__":
    # smoke test
    print(f"backend: {BACKEND}, model: {MODEL}")
    resp = call_groq(
        [{"role": "user", "content": 'Reply with exactly this JSON and nothing else: {"ok": true}'}],
        reasoning_effort="low",
        max_tokens=200,
    )
    content, reasoning = extract_message_text(resp)
    print("content:", content)
    print("usage:", call_budget_used(resp))
