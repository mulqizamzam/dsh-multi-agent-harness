# orchestrator.foundation.messaging — Agent messaging rules (Phase 1D)
#
# V1 rules (contract §9):
#   - direct specialist-to-specialist delegation is DENY BY DEFAULT
#   - meaningful delegation flows through the Orchestrator
#   - messages carry data/recommendations/results — NEVER authority
#   - an authority assertion inside a message is IGNORED and audited
#     (AUTH-INV-13, THREAT-020)

from __future__ import annotations

from dataclasses import dataclass, field
from .contracts import SPECIALIST_ROLES, ORCHESTRATOR


class MessagingError(ValueError):
    pass


@dataclass(frozen=True)
class Message:
    sender: str
    recipient: str
    kind: str                       # data | result | request | notice
    payload: dict = field(default_factory=dict)
    authority_assertions: dict = field(default_factory=dict)  # ignored

    def __post_init__(self):
        if self.sender not in (ORCHESTRATOR,) + SPECIALIST_ROLES:
            raise MessagingError(f"unknown sender {self.sender!r}")
        if self.recipient not in (ORCHESTRATOR,) + SPECIALIST_ROLES:
            raise MessagingError(f"unknown recipient {self.recipient!r}")

    def assert_authority(self) -> None:
        """V1: meaningful delegation must flow through the orchestrator.
        specialist→specialist delegation is DENY BY DEFAULT."""
        if self.sender != ORCHESTRATOR and self.recipient != ORCHESTRATOR:
            raise MessagingError(
                "specialist-to-specialist delegation DENY BY DEFAULT (V1)")

    def authority_ignored(self) -> bool:
        """Messages cannot create authority; any assertion is data to ignore."""
        return bool(self.authority_assertions)
