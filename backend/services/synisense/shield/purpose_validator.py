"""Synisense Shield — purpose allow-list validator.

Phase A behaviour:

- Exact match against `ALLOWED_PURPOSES`.
- Wildcard match against any entry ending in `.*` (matches any depth).
- Internal-prefix purposes (`synisense.*`) are 422-rejected for external
  HTTP callers, accepted only when `internal_caller=True`.

Returns silently on success; raises `PurposeInvalid` (→ 422) on failure.
"""
from __future__ import annotations

from typing import Iterable

from services.synisense.config import ALLOWED_PURPOSES, INTERNAL_ONLY_PURPOSE_PREFIXES
from services.synisense.exceptions import PurposeInvalid


def validate_purpose(
    purpose: str,
    *,
    internal_caller: bool = False,
    allow_list: Iterable[str] | None = None,
) -> None:
    """Allow-list check. Raises `PurposeInvalid` on rejection.

    `allow_list` is an injection seam for tests; defaults to the
    module-level `ALLOWED_PURPOSES`.
    """
    if not purpose or not isinstance(purpose, str):
        raise PurposeInvalid("purpose missing or not a string")
    purpose = purpose.strip()
    if not purpose:
        raise PurposeInvalid("purpose is empty")

    # Internal purposes — gate.
    if not internal_caller:
        for prefix in INTERNAL_ONLY_PURPOSE_PREFIXES:
            if purpose.startswith(prefix):
                raise PurposeInvalid(
                    f"purpose '{purpose}' is internal-only and cannot be invoked "
                    "from an external HTTP caller"
                )

    catalogue = set(allow_list) if allow_list is not None else ALLOWED_PURPOSES
    if purpose in catalogue:
        return

    # Wildcard check (entries ending in `.*` match any namespace below).
    for entry in catalogue:
        if entry.endswith(".*"):
            stem = entry[:-2]  # drop trailing `.*`
            if purpose == stem or purpose.startswith(stem + "."):
                return

    raise PurposeInvalid(
        f"purpose '{purpose}' is not in the allow-list. Phase A allow-list: "
        f"{sorted(catalogue)}"
    )
