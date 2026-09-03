# orchestrator.execution.recovery_runtime — Full-cycle recovery driver
#
# Phase 5 / Session C (G11 — LIVE RECOVERY CLOSURE)
#
# A standalone runtime recovery driver that composes the existing
# RecoveryController (control/recovery.py) + ExecutionEngine into a full-cycle
# recovery-to-COMPLETE path. Does NOT duplicate either module.
#
# Full cycle:
#   execution failure → PRESERVE → DIAGNOSE → RECOVER/REPLAN
#   → AUTHORITY RECHECK → EXECUTE → VERIFY → COMPLETE
#   → on any denial: FAILED / ESCALATED (fail-closed)
#
# REUSE (no duplication):
#   - RecoveryRecord / RecoveryController: control/recovery.py
#   - ExecutionEngine / ExecutionRequest: orchestrator/execution/engine.py
#   - Authority / execution gate: control/authority.py, control/execution_gate.py
#   - Verification: control/verification.py (via the engine)

from .driver import RecoveryRunResult, RecoveryRuntimeError, run_recovery_cycle

__all__ = [
    "RecoveryRunResult",
    "RecoveryRuntimeError",
    "run_recovery_cycle",
]
