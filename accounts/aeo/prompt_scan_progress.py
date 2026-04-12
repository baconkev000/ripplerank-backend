"""
Monitored prompt scan progress for AEO prompt coverage (counts + semantics).

Used by ``accounts.views._build_aeo_prompt_coverage_payload`` so tests can import
without loading the full views module (e.g. optional ``stripe`` dependency).
"""

from __future__ import annotations

from typing import Any, Callable


def monitored_prompt_keys_in_order(selected_aeo_prompts: list | None) -> list[str]:
    """Stable list of monitored prompt strings, deduped, order preserved."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in selected_aeo_prompts or []:
        k = str(raw).strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def prompt_scan_completed_count(
    monitored_keys: list[str],
    by_prompt: dict[str, list],
    latest_snapshot_per_platform: Callable[[list], dict[str, Any]],
) -> int:
    """
    Count monitored prompts that are fully scanned for progress UX.

    A prompt counts as **finished** only when the latest stored response for **each** of
    OpenAI, Gemini, and Perplexity has at least one extraction snapshot. This matches the
    stricter leg of ``_aeo_profile_visibility_pending`` (responses waiting for extraction)
    and is stricter than per-cell ``has_data`` in the coverage JSON (which can be true when
    a raw response exists). Pipeline runs still in ``PENDING``/``RUNNING`` or extraction
    stages are surfaced separately via ``visibility_pending`` on the API payload.
    """
    completed = 0
    for key in monitored_keys:
        rows = by_prompt.get(key, [])
        plat_latest = latest_snapshot_per_platform(rows)
        ok = True
        for plat in ("openai", "gemini", "perplexity"):
            if plat not in plat_latest:
                ok = False
                break
            resp = plat_latest[plat]
            if not resp.extraction_snapshots.exists():
                ok = False
                break
        if ok:
            completed += 1
    return completed
