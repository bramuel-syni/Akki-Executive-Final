"""Solva v2 Slice 1 — Feature flag tests.

Locks the truth table:
  env=false, account=None  →  False
  env=false, account=True  →  True
  env=true,  account=None  →  True
  env=true,  account=False →  False
"""
from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


from services.solva_v2.feature_flag import solva_v2_enabled_for  # noqa: E402


def test_env_false_account_none_returns_false(monkeypatch):
    monkeypatch.setenv("SOLVA_V2_ENABLED", "false")
    assert solva_v2_enabled_for(None) is False
    assert solva_v2_enabled_for({}) is False


def test_env_false_account_opt_in_returns_true(monkeypatch):
    monkeypatch.setenv("SOLVA_V2_ENABLED", "false")
    assert solva_v2_enabled_for({"feature_flags": {"solva_v2": True}}) is True


def test_env_true_account_none_returns_true(monkeypatch):
    monkeypatch.setenv("SOLVA_V2_ENABLED", "true")
    assert solva_v2_enabled_for(None) is True
    assert solva_v2_enabled_for({}) is True


def test_env_true_account_opt_out_returns_false(monkeypatch):
    """Per-account kill switch must override the env."""
    monkeypatch.setenv("SOLVA_V2_ENABLED", "true")
    assert solva_v2_enabled_for({"feature_flags": {"solva_v2": False}}) is False


def test_truthy_env_tokens(monkeypatch):
    for token in ("true", "1", "yes", "y", "ON"):
        monkeypatch.setenv("SOLVA_V2_ENABLED", token)
        assert solva_v2_enabled_for(None) is True, f"Token {token!r} must enable v2"


def test_falsy_env_tokens(monkeypatch):
    for token in ("false", "0", "no", "n", "OFF", ""):
        monkeypatch.setenv("SOLVA_V2_ENABLED", token)
        assert solva_v2_enabled_for(None) is False, f"Token {token!r} must NOT enable v2"


def test_string_form_account_override(monkeypatch):
    """Per-account flag stored as string is also tolerated."""
    monkeypatch.setenv("SOLVA_V2_ENABLED", "false")
    assert solva_v2_enabled_for({"feature_flags": {"solva_v2": "true"}}) is True
    assert solva_v2_enabled_for({"feature_flags": {"solva_v2": "yes"}}) is True
