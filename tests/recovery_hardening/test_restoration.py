# tests/recovery_hardening/test_restoration.py — Restoration verification

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from control.recovery_hardening.restoration import (
    RestorationVerificationError, file_sha256, verify_restoration_hashes,
    capture_restoration_state,
)


def test_file_sha256_present(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("hello")
    h = file_sha256(str(p))
    assert h and len(h) == 64


def test_file_sha256_absent(tmp_path):
    assert file_sha256(str(tmp_path / "missing.txt")) is None


def test_verify_restoration_match(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("hello")
    before = capture_restoration_state(["a.txt"], base=str(tmp_path))
    after = capture_restoration_state(["a.txt"], base=str(tmp_path))
    verify_restoration_hashes(before, after, task_id="t")  # no raise


def test_verify_restoration_mismatch(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("hello")
    before = capture_restoration_state(["a.txt"], base=str(tmp_path))
    p.write_text("tampered")
    after = capture_restoration_state(["a.txt"], base=str(tmp_path))
    with pytest.raises(RestorationVerificationError):
        verify_restoration_hashes(before, after, task_id="t")


def test_verify_restoration_missing_after(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("hello")
    before = capture_restoration_state(["a.txt"], base=str(tmp_path))
    p.unlink()
    after = capture_restoration_state(["a.txt"], base=str(tmp_path))
    with pytest.raises(RestorationVerificationError):
        verify_restoration_hashes(before, after, task_id="t")


def test_capture_restoration_state_empty():
    assert capture_restoration_state([]) == {}