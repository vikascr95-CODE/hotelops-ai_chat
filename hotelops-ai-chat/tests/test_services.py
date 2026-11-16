import pytest
from app.orchestrator.schemas import GuestIntent, ExtractionResult
from app.orchestrator.routing import route_intent
from app.workflows.idempotency import message_key

def test_multi_intent_schema_accepts_independent_tasks():
    result = ExtractionResult(reply="I recorded both requests.", tasks=[
        GuestIntent(title="Send two towels", description="Two extra towels", intent_type="housekeeping"),
        GuestIntent(title="Repair air conditioning", description="AC is not cooling", intent_type="maintenance"),
    ])
    assert len(result.tasks) == 2
    assert [route_intent(task) for task in result.tasks] == ["Housekeeping", "Maintenance"]

def test_unknown_department_is_rejected():
    with pytest.raises(Exception):
        GuestIntent(title="Do something", description="A request", intent_type="unknown")

def test_idempotency_key_is_stable_for_retry():
    first = message_key("conversation-1", "Need towels")
    retry = message_key("conversation-1", "Need towels")
    assert first == retry

def test_different_messages_have_different_keys():
    assert message_key("c1", "Need towels") != message_key("c1", "Fix AC")
