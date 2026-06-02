"""P-Cleanup B — Greeting first-name extraction.

`frontend/src/pages/ContextPortfolio.jsx:464` derives the first name
shown in the H1 greeting. Spec contract (verbatim from dispatch):

    name="Sam Patel"  → "Good ___, Sam."
    name="Yuki"        → "Good ___, Yuki."
    name=null|""|"   " → "Good ___, there."

Pre-fix:
    const firstName = (account?.name || "there").split(" ")[0];

Whitespace-only names tripped the truthy branch and produced an
empty first-token, rendering "Good morning, ." This source-strict
test asserts the corrected line is present and exercises the
extraction algorithm against the documented fixtures.

The frontend's JSX engine is not in scope (no Jest); we replicate
the small extraction function in Python and assert the documented
behavior against the dispatch's three fixtures + the whitespace
edge-case. The same logic IS present in the JSX source — locked by
a source-strict regex match below.
"""
from __future__ import annotations

import re

import pytest
import pytest_asyncio
from httpx import ASGITransport

import server  # noqa: F401
from server import app


@pytest_asyncio.fixture(scope="module")
async def transport():
    yield ASGITransport(app=app)


# Mirror of the JSX algorithm — keep semantically identical.
def _first_name(account_name):
    raw = (account_name or "").strip()
    if not raw:
        return "there"
    return re.split(r"\s+", raw)[0]


@pytest.mark.parametrize("name,expected", [
    ("Sam Patel",  "Sam"),
    ("Yuki",       "Yuki"),
    (None,         "there"),
    ("",           "there"),
    ("   ",        "there"),
    ("  Sam   Patel  ", "Sam"),
    ("Ọmọ́nẹ́",   "Ọmọ́nẹ́"),     # non-ASCII single token preserved
    ("Anne Marie Smith", "Anne"),
])
def test_first_name_contract(transport, name, expected):
    assert _first_name(name) == expected


def test_jsx_source_carries_canonical_extraction_line(transport):
    """Source-strict guard against drift."""
    src = open(
        "/app/frontend/src/pages/ContextPortfolio.jsx", encoding="utf-8"
    ).read()
    # The exact canonical pair of lines after P-Cleanup B.
    assert 'const rawName = (account?.name || "").trim();' in src, src.count("rawName")
    assert 'const firstName = rawName ? rawName.split(/\\s+/)[0] : "there";' in src
