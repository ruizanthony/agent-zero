from pathlib import Path
import sys
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_message_queue_imports_without_runtime_agentcontext_import():
    from helpers import message_queue

    assert message_queue.QUEUE_KEY == "message_queue"


class _FakeContext:
    def __init__(self):
        self.data = {}
        self.output_data = {}

    def get_data(self, key):
        return self.data.get(key)

    def set_data(self, key, value):
        self.data[key] = value

    def set_output_data(self, key, value):
        self.output_data[key] = value


def test_message_queue_add_syncs_frontend_output_data():
    from helpers import message_queue as mq

    ctx = cast(Any, _FakeContext())
    text = "x" * 105

    item = mq.add(
        ctx,
        text,
        attachments=["file.txt", "/tmp/report.pdf"],
        item_id="item-1",
    )

    assert item["attachments"] == ["/a0/usr/uploads/file.txt", "/tmp/report.pdf"]
    assert ctx.output_data[mq.QUEUE_KEY] == [
        {
            "id": "item-1",
            "seq": 1,
            "text": "x" * 100 + "...",
            "attachments": ["file.txt", "report.pdf"],
            "attachment_count": 2,
        }
    ]
