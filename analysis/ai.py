"""Optional AI interpretation of results that engine.py has already computed.

The model never sees the raw CSV and is never asked to calculate anything. It
receives the JSON output of a deterministic analysis and is instructed to
interpret only those numbers. If the `anthropic` package or credentials are
missing, the site works without this layer.
"""
from __future__ import annotations

import json
import os

MODEL = os.environ.get("TURNOUT_AI_MODEL", "claude-opus-5-5")

SYSTEM = """You interpret statistical results for a website about 2022 U.S. midterm turnout by state (51 jurisdictions; columns: turnout, VEP, VAP, % non-citizen, prison/probation/parole counts; Census region is an external label).

Rules:
- Use ONLY numbers that appear in the RESULTS JSON. Never compute, estimate, or invent a statistic. If a number you would want is not there, say it was not computed and name the analysis that would produce it.
- Never claim you ran an analysis. The analyses that were run are listed in `analyses_run`.
- Correlation is not causation. These are 51 aggregate units in one election; avoid individual-level claims.
- Structure the answer in three short labelled parts: "Observed" (what the computed numbers show), "Interpretation" (what they plausibly mean, with uncertainty), "Speculation / next analyses" (hypotheses beyond the data, and specific follow-up analyses the site can run: control for a variable, exclude a state, switch to VAP outcome, leave-one-out, permutation test, within-region correlation, specification curve).
- Be concise: under 220 words. Plain text, no markdown headers."""


def status() -> dict:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return dict(available=False, reason="Python package 'anthropic' is not installed (pip install anthropic).")
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return dict(available=False, reason="Set ANTHROPIC_API_KEY on the server to enable AI interpretation.")
    return dict(available=True, model=MODEL)


def interpret(question: str, results: dict) -> dict:
    s = status()
    if not s["available"]:
        return dict(ok=False, error=s["reason"])
    import anthropic

    client = anthropic.Anthropic()
    payload = json.dumps(results, default=str)[:60000]
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": f"QUESTION: {question}\n\nRESULTS JSON:\n{payload}"}],
        )
    except anthropic.AuthenticationError:
        return dict(ok=False, error="The API key was rejected.")
    except anthropic.RateLimitError:
        return dict(ok=False, error="Rate limited by the AI service; try again shortly.")
    except anthropic.APIStatusError as e:
        return dict(ok=False, error=f"AI service error ({e.status_code}).")
    except anthropic.APIConnectionError:
        return dict(ok=False, error="Could not reach the AI service.")
    if resp.stop_reason == "refusal":
        return dict(ok=False, error="The AI service declined this request.")
    text = "".join(b.text for b in resp.content if b.type == "text")
    return dict(ok=True, text=text, model=resp.model)
