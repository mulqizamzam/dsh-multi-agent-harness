# tests/unit/test_ipc_authn.py
#
# Regression proof for the O3 IPC authn helper (F20):
#
#   verify_signature fed expected_token.lower() straight into
#   hmac.compare_digest. compare_digest raises TypeError for non-ASCII str
#   operands, so a non-ASCII presented token turned an ordinary auth failure
#   into an unhandled TypeError (INTERNAL_ERROR). It must return False.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas.ipc import sign_request, verify_signature

_SECRET = b"0" * 32
_METHOD = "registry_write"
_ID = "req-1"
_ISSUED_AT = "2026-08-30T21:36:46Z"
_NONCE = "nonce-1"
_PARAMS = {"path": "state/registry/x.json"}


def _token():
    return sign_request(_SECRET, _METHOD, _ID, _ISSUED_AT, _NONCE, _PARAMS)


def test_verify_signature_accepts_valid_token():
    tok = _token()
    assert verify_signature(_SECRET, tok, _METHOD, _ID, _ISSUED_AT, _NONCE,
                            _PARAMS) is True


def test_verify_signature_accepts_uppercase_hex_token():
    tok = _token().upper()
    assert verify_signature(_SECRET, tok, _METHOD, _ID, _ISSUED_AT, _NONCE,
                            _PARAMS) is True


def test_verify_signature_rejects_ascii_mismatch():
    assert verify_signature(_SECRET, "deadbeef", _METHOD, _ID, _ISSUED_AT,
                            _NONCE, _PARAMS) is False


def test_verify_signature_non_ascii_token_returns_false_not_raises():
    """Probe: a non-ASCII presented token must be a clean auth failure."""
    for bad in ("τóken", "tökén-nön-ascii", "ａｂｃ", "\u00e9",
                "\U0001F600" + "abc", "caf\u00e9-" + "a" * 64):
        assert verify_signature(_SECRET, bad, _METHOD, _ID, _ISSUED_AT,
                                _NONCE, _PARAMS) is False, bad


def test_verify_signature_non_ascii_token_wrong_secret_returns_false():
    """Even with a mismatching secret, a non-ASCII token must not raise."""
    bad = "\u00e9" * 64
    assert verify_signature(b"1" * 32, bad, _METHOD, _ID, _ISSUED_AT,
                            _NONCE, _PARAMS) is False


def test_verify_signature_empty_and_missing_token():
    assert verify_signature(_SECRET, "", _METHOD, _ID, _ISSUED_AT, _NONCE,
                            _PARAMS) is False
    assert verify_signature(_SECRET, None, _METHOD, _ID, _ISSUED_AT, _NONCE,
                            _PARAMS) is False
