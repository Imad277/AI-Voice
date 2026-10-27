"""Server confirmation note (Phase 1 harness): offline tests, no network, no key.

The note tells the model that a slot confirmation is recorded in the trusted session. It
must come only from server state, carry no authority, and never book by itself.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from e2e_fakes import HAPPY_REPLIES, HAPPY_TRANSCRIPTS, reply, run_loop, server_state

from voiceos.benchmark.binding import GatewayBinding, slot_confirmation_note
from voiceos.benchmark.e2e_gate import hard_failures
from voiceos.benchmark.runner import BENCH_TENANT
from voiceos.core.tools import ToolRequest

ROOT = Path(__file__).resolve().parents[2]
NOTE = (
    "Server-Status: Der Anrufer hat den vorgelesenen Termin slot_a_1000 ausdrücklich "
    "bestätigt. Die Bestätigung ist serverseitig gespeichert."
)


def binding_at_slot_readback() -> tuple[GatewayBinding, object, object]:
    """Contact confirmed, slot proposed and read back by the server (pending)."""
    gateway, context, calendar, _ = server_state()
    binding = GatewayBinding(gateway, context)
    binding.execute(
        ToolRequest("c", "contact.collect_candidate", {"name": "Erika", "phone": "030 123456"})
    )
    assert binding.user_reply("Ja, genau.") is None  # contact confirmation: no note
    result = binding.execute(ToolRequest("b", "calendar.book_slot", {"slot_id": "slot_a_1000"}))
    assert result.reason is not None and result.reason.value == "SLOT_CONFIRMATION_REQUIRED"
    return binding, gateway.session(context), calendar


def test_note_only_after_the_server_recorded_the_slot_confirmation() -> None:
    binding, session, calendar = binding_at_slot_readback()
    assert session.slot_confirmed is False  # type: ignore[attr-defined]
    note = binding.user_reply("Ja, genau.")
    assert note == NOTE and session.slot_confirmed is True  # type: ignore[attr-defined]
    assert calendar.create_calls == 0  # type: ignore[attr-defined]  # the note books nothing


@pytest.mark.parametrize(
    "answer", ["Nein.", "Vielleicht, ich weiß nicht.", "Ja, aber erst um elf."]
)
def test_no_note_for_no_or_unclear_answers(answer: str) -> None:
    binding, session, _ = binding_at_slot_readback()
    assert binding.user_reply(answer) is None
    assert session.slot_confirmed is False  # type: ignore[attr-defined]


def test_no_note_without_a_pending_slot_readback() -> None:
    gateway, context, *_ = server_state()
    binding = GatewayBinding(gateway, context)
    assert binding.user_reply("Ja, genau.") is None  # nothing read back
    binding, *_ = binding_at_slot_readback()
    assert binding.user_reply("Ja, genau.") is not None
    assert binding.user_reply("Ja, genau.") is None  # readback consumed: no second note


def test_note_carries_no_authority_or_credential_data() -> None:
    _, session, _ = binding_at_slot_readback()
    session.slot_confirmed = True  # type: ignore[attr-defined]
    note = slot_confirmation_note(session)  # type: ignore[arg-type]
    assert note == NOTE
    context = session.context  # type: ignore[attr-defined]
    for forbidden in (
        str(BENCH_TENANT), str(context.call_id), context.calendar_ref, context.crm_ref,
        context.principal, context.agent_id, "tenant", "scope", "key", "token", "secret",
    ):  # fmt: skip
        assert forbidden.lower() not in note.lower()
    session.slot_confirmed = False  # type: ignore[attr-defined]
    assert slot_confirmation_note(session) is None  # type: ignore[arg-type]


def test_loop_inserts_the_note_before_the_next_llm_request_and_books_only_via_gateway() -> None:
    loop, gateway, calendar, crm, events, _ = run_loop(HAPPY_TRANSCRIPTS, HAPPY_REPLIES)
    roles = [(m.role, m.content) for m in loop.history]
    i = roles.index(("tool", NOTE))
    assert roles[i - 1] == ("user", "Ja, genau.") and roles[i - 2][0] == "assistant"
    assert roles[i - 2][1] == "Soll ich den Termin slot_a_1000 verbindlich buchen?"
    assert sum(1 for r in roles if r == ("tool", NOTE)) == 1
    names = [e.name for e in events if e.turn == 3]
    assert names.index("SERVER_CONFIRMATION_NOTE") < names.index("LLM_REQUEST_START")
    assert calendar.create_calls == 1  # only after the model's book_slot through the gateway
    assert [c.tool for c in gateway.calls if c.calendar_creates] == ["calendar.book_slot"]
    assert hard_failures(gateway.calls, loop.turns, calendar, crm, context_unchanged=True) == []


def test_note_without_a_book_slot_proposal_books_nothing() -> None:
    replies = [*HAPPY_REPLIES[:4], reply("Gerne, einen Moment."), reply("Auf Wiederhören.")]
    loop, gateway, calendar, crm, *_ = run_loop(HAPPY_TRANSCRIPTS, replies)
    assert ("tool", NOTE) in [(m.role, m.content) for m in loop.history]
    assert calendar.create_calls == 0
    assert hard_failures(gateway.calls, loop.turns, calendar, crm, context_unchanged=True) == []


def _source(name: str) -> str:
    return (ROOT / "src/voiceos/benchmark" / name).read_text()


def test_both_runtimes_share_one_code_path_for_the_note() -> None:
    """The note is made in binding.py and inserted in voice_loop.py only; both runtimes
    hand their turns to that same VoiceAgentLoop and never touch replies themselves."""
    runtimes = ast.parse(_source("runtimes.py"))
    live = [
        node for node in ast.walk(runtimes)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_live_session"
    ]  # fmt: skip
    assert len(live) == 2  # LiveKitRuntimeAdapter, PipecatRuntimeAdapter
    for fn in live:
        calls = {
            n.func.attr for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        }  # fmt: skip
        assert "run" in calls  # agent.run(...) -> VoiceAgentLoop
        assert not {"user_reply", "execute", "render"} & calls
    for module in ("runtimes.py", "e2e_gate.py", "providers.py"):
        assert "slot_confirmation_note" not in _source(module)
        assert "Server-Status" not in _source(module)
    assert "self._binding.user_reply(transcript)" in _source("voice_loop.py")
