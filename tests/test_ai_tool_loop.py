"""End-to-end check of the Groq tool-calling loop.

Groq is stubbed; everything below it (registry, tool dispatch, message
threading) is the real implementation.
"""

import asyncio
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ai_loop.db")

from app.services.ai_services import (  # noqa: E402
    AIService,
    _parse_arguments,
)
from app.services.tools import ToolRegistry, ToolSpec  # noqa: E402


def _message(content=None, tool_calls=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=tool_calls,
                )
            )
        ]
    )


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class FakeGroq:
    """Replays a scripted list of Groq responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    async def _create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


class ToolLoopTest(unittest.TestCase):
    def setUp(self):
        self.service = AIService.__new__(AIService)
        self.calls = []

        async def gmail_search(arguments):
            self.calls.append(arguments)
            return {
                "count": 1,
                "messages": [
                    {"subject": "Your card statement", "from": "bank"}
                ],
            }

        self.registry = ToolRegistry(
            [
                ToolSpec(
                    name="gmail_search_messages",
                    description="Search Gmail",
                    parameters={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                        },
                    },
                    handler=gmail_search,
                )
            ]
        )

    def _run(self, responses, tools_enabled=True):
        self.service.client = FakeGroq(responses)

        answer = asyncio.run(
            self.service._run_completion_loop(
                model="test-model",
                messages=[{"role": "user", "content": "hi"}],
                registry=self.registry,
                tools_enabled=tools_enabled,
            )
        )

        return answer, self.service.client

    def test_tool_result_is_fed_back_to_the_model(self):
        answer, client = self._run(
            [
                _message(
                    tool_calls=[
                        _tool_call(
                            "call-1",
                            "gmail_search_messages",
                            '{"query": "from:bank"}',
                        )
                    ]
                ),
                _message(content="Your card statement arrived."),
            ]
        )

        self.assertEqual(answer, "Your card statement arrived.")
        self.assertEqual(self.calls, [{"query": "from:bank"}])

        follow_up_messages = client.requests[1]["messages"]
        tool_message = follow_up_messages[-1]

        self.assertEqual(tool_message["role"], "tool")
        self.assertEqual(tool_message["tool_call_id"], "call-1")
        self.assertIn(
            "Your card statement",
            json.loads(tool_message["content"])["messages"][0][
                "subject"
            ],
        )

    def test_parallel_tool_calls_are_all_answered(self):
        answer, client = self._run(
            [
                _message(
                    tool_calls=[
                        _tool_call(
                            "call-1",
                            "gmail_search_messages",
                            '{"query": "a"}',
                        ),
                        _tool_call(
                            "call-2",
                            "gmail_search_messages",
                            '{"query": "b"}',
                        ),
                    ]
                ),
                _message(content="done"),
            ]
        )

        self.assertEqual(answer, "done")
        self.assertEqual(
            [call["query"] for call in self.calls], ["a", "b"]
        )

        tool_ids = [
            message["tool_call_id"]
            for message in client.requests[1]["messages"]
            if message.get("role") == "tool"
        ]

        self.assertEqual(tool_ids, ["call-1", "call-2"])

    def test_plain_answer_skips_tools(self):
        answer, client = self._run([_message(content="Hello!")])

        self.assertEqual(answer, "Hello!")
        self.assertEqual(len(client.requests), 1)

    def test_tools_are_not_sent_for_vision_requests(self):
        _answer, client = self._run(
            [_message(content="A chart.")],
            tools_enabled=False,
        )

        self.assertNotIn("tools", client.requests[0])

    def test_empty_response_falls_back_to_a_prompt(self):
        answer, _client = self._run([_message(content="")])

        self.assertIn("rephrase", answer)

    def test_loop_stops_at_the_iteration_limit(self):
        responses = [
            _message(
                tool_calls=[
                    _tool_call(
                        f"call-{index}",
                        "gmail_search_messages",
                        "{}",
                    )
                ]
            )
            for index in range(20)
        ]

        answer, client = self._run(responses)

        self.assertIn("narrow the question", answer)
        self.assertLessEqual(len(client.requests), 20)


class ParseArgumentsTest(unittest.TestCase):
    def test_valid_json(self):
        self.assertEqual(
            _parse_arguments('{"a": 1}'), {"a": 1}
        )

    def test_malformed_json_is_ignored(self):
        self.assertEqual(_parse_arguments("{not json"), {})

    def test_empty_and_non_object_payloads(self):
        self.assertEqual(_parse_arguments(""), {})
        self.assertEqual(_parse_arguments("[1, 2]"), {})


if __name__ == "__main__":
    unittest.main()
