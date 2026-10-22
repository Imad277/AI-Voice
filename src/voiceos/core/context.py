"""Trusted, server-issued call context.

A ``CallContext`` is created only by trusted server code (dispatcher / authenticated
session setup). It is the sole source of tenant identity, principal, scopes and
integration references for a call. It is never built from model output, prompt
content, caller input or webhook payloads, and it is passed to the Tool Gateway
separately from the untrusted ``ToolRequest``.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from voiceos.core.tools import ToolName


@dataclass(frozen=True, slots=True)
class CallContext:
    tenant_id: UUID
    call_id: UUID
    agent_id: str
    agent_release_id: str
    principal: str  # server-issued principal reference, never a credential
    calendar_ref: str  # authorized calendar integration reference
    crm_ref: str  # authorized CRM integration reference
    scopes: frozenset[ToolName]  # tools this call may execute
