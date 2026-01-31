import tempfile

from concierge.inbox import Inbox
from concierge.models import Message


def test_append_and_read():
    with tempfile.TemporaryDirectory() as tmpdir:
        inbox = Inbox(directory=tmpdir)
        m1 = Message(text="buy milk")
        m2 = Message(text="call dentist")
        inbox.append(m1)
        inbox.append(m2)

        messages = inbox.read_all()
        assert len(messages) == 2
        texts = {m.text for m in messages}
        assert texts == {"buy milk", "call dentist"}


def test_empty_inbox():
    with tempfile.TemporaryDirectory() as tmpdir:
        inbox = Inbox(directory=tmpdir)
        assert inbox.read_all() == []


def test_message_has_id():
    m = Message(text="test")
    assert len(m.id) == 12
