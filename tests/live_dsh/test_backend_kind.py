# tests/live_dsh/test_backend_kind.py — FAKE vs REAL vs UNAVAILABLE discrimination
#
# The harness MUST explicitly distinguish the deterministic backend from the
# actual mounted DSH subagent instances, and must NEVER assume a live bridge
# exists.

import os
import pytest

from .backend_kind import (
    BackendKind, probe_backend_kind, is_real_bridge_available,
    require_real_bridge,
)
from .discovery import DISCOVERY_MARKER_ENV


class TestBackendKindProbe:
    def test_unavailable_without_marker(self):
        """Without the D4/D7 mount marker, the REAL bridge is UNAVAILABLE."""
        saved = os.environ.pop(DISCOVERY_MARKER_ENV, None)
        try:
            assert probe_backend_kind() == BackendKind.UNAVAILABLE
            assert not is_real_bridge_available()
        finally:
            if saved is not None:
                os.environ[DISCOVERY_MARKER_ENV] = saved

    def test_real_with_marker(self):
        """With the mount marker set, the REAL bridge is reported available."""
        os.environ[DISCOVERY_MARKER_ENV] = "1"
        try:
            assert probe_backend_kind() == BackendKind.REAL
            assert is_real_bridge_available()
        finally:
            os.environ.pop(DISCOVERY_MARKER_ENV, None)

    def test_require_real_bridge_refuses_without_marker(self):
        """require_real_bridge fails closed without the marker (never a silent
        fallback to the fake backend)."""
        saved = os.environ.pop(DISCOVERY_MARKER_ENV, None)
        try:
            with pytest.raises(RuntimeError, match="not available"):
                require_real_bridge()
        finally:
            if saved is not None:
                os.environ[DISCOVERY_MARKER_ENV] = saved

    def test_fake_kind_is_enum_stable(self):
        """The FAKE kind label is stable and distinct from REAL."""
        assert BackendKind.FAKE.value == "fake"
        assert BackendKind.REAL.value == "real-dsh"
        assert BackendKind.FAKE != BackendKind.REAL
        assert BackendKind.REAL != BackendKind.UNAVAILABLE


class TestNoSilentFallback:
    def test_real_backend_refuses_unmounted(self, recording_bridge):
        """A RealDSHBackend with require_marker=True refuses an unmounted
        dispatch instead of silently running the fake path."""
        from .real_backend import RealDSHBackend, BridgeNotAvailable
        dispatch, _ = recording_bridge
        backend = RealDSHBackend(dispatch, require_marker=True)
        from .conftest import make_task, make_delegation
        from .adapters import build_role_adapter
        task = make_task(role="cto")
        delegation = make_delegation()
        adapter = build_role_adapter("cto")
        with pytest.raises(BridgeNotAvailable):
            backend.start(adapter.instance, {"task_id": task.task_id,
                                             "objective": task.objective,
                                             "assigned_role": task.assigned_role})
