"""Tests for the parts of Jarvis that must not misbehave: the approval gate,
the path guard, tool dispatch, and the agent loop.

Run with:  python -m unittest discover tests
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis_ai.agent import Agent  # noqa: E402
from jarvis_ai.config import Settings  # noqa: E402
from jarvis_ai.permissions import Approver, Denied, Policy, Risk  # noqa: E402
from jarvis_ai.registry import ToolContext, ToolError  # noqa: E402
from jarvis_ai.tools import REGISTRY  # noqa: E402


def make_context(tmp: Path, **approver_kwargs) -> ToolContext:
    settings = Settings()
    settings.writable_roots = [tmp]
    settings.data_dir = tmp / ".jarvis"
    approver_kwargs.setdefault("policy", Policy.AUTO_EDIT)
    return ToolContext(settings=settings, approver=Approver(**approver_kwargs))


class ApprovalGateTests(unittest.TestCase):
    def test_reads_never_prompt(self):
        approver = Approver(policy=Policy.ASK, confirm=lambda *a: self.fail("should not ask"))
        approver.check("list_directory", "list ~", Risk.READ)  # must not raise

    def test_writes_prompt_under_ask_policy(self):
        asked = []
        approver = Approver(
            policy=Policy.ASK,
            confirm=lambda name, desc, risk: asked.append((name, risk)) or True,
        )
        approver.check("write_file", "write a file", Risk.WRITE)
        self.assertEqual(asked, [("write_file", Risk.WRITE)])

    def test_declining_raises_denied(self):
        approver = Approver(policy=Policy.ASK, confirm=lambda *a: False)
        with self.assertRaises(Denied):
            approver.check("delete_path", "delete everything", Risk.SYSTEM)

    def test_auto_edit_still_gates_system_actions(self):
        approver = Approver(policy=Policy.AUTO_EDIT, confirm=lambda *a: False)
        approver.check("write_file", "write a file", Risk.WRITE)  # allowed
        with self.assertRaises(Denied):
            approver.check("run_command", "rm -rf /", Risk.SYSTEM)

    def test_read_only_refuses_without_asking(self):
        approver = Approver(policy=Policy.READ_ONLY, confirm=lambda *a: True)
        with self.assertRaises(Denied):
            approver.check("write_file", "write a file", Risk.WRITE)

    def test_yolo_approves_everything(self):
        approver = Approver(policy=Policy.YOLO)
        approver.check("run_command", "anything", Risk.SYSTEM)  # must not raise

    def test_will_prompt_matches_what_check_does(self):
        approver = Approver(policy=Policy.ASK, confirm=lambda *a: True)
        self.assertFalse(approver.will_prompt(Risk.READ))
        self.assertTrue(approver.will_prompt(Risk.WRITE))
        self.assertFalse(Approver(policy=Policy.YOLO).will_prompt(Risk.SYSTEM))
        self.assertFalse(Approver(policy=Policy.READ_ONLY).will_prompt(Risk.WRITE))

    def test_no_confirm_callback_means_denied(self):
        """A non-interactive session must fail closed, not run the action."""
        with self.assertRaises(Denied):
            Approver(policy=Policy.ASK).check("write_file", "write", Risk.WRITE)


class PathGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = Settings()
        self.settings.writable_roots = [self.tmp]

    def test_paths_inside_root_are_writable(self):
        self.assertTrue(self.settings.is_writable(self.tmp / "deep" / "file.txt"))

    def test_paths_outside_root_are_not(self):
        self.assertFalse(self.settings.is_writable(Path("/etc/passwd")))

    def test_parent_traversal_does_not_escape(self):
        escaped = self.settings.resolve(str(self.tmp / ".." / ".." / "etc" / "passwd"))
        self.assertFalse(self.settings.is_writable(escaped))

    def test_credential_paths_are_flagged_sensitive(self):
        for candidate in ("~/.ssh/id_rsa", "~/.aws/credentials", "~/project/.env"):
            self.assertTrue(self.settings.is_sensitive(self.settings.resolve(candidate)), candidate)

    def test_ordinary_files_are_not_sensitive(self):
        self.assertFalse(self.settings.is_sensitive(self.settings.resolve("~/notes.txt")))


class RegistryTests(unittest.TestCase):
    def test_every_tool_has_a_usable_schema(self):
        for spec in REGISTRY.specs():
            self.assertTrue(spec["description"].strip(), spec["name"])
            schema = spec["input_schema"]
            self.assertEqual(schema["type"], "object")
            self.assertFalse(schema["additionalProperties"])
            for name, prop in schema["properties"].items():
                self.assertIn("type", prop, f"{spec['name']}.{name}")

    def test_previews_render_for_every_tool(self):
        """The approval prompt must never fall back to a raw repr."""
        for tool in REGISTRY.tools.values():
            args = {name: "x" for name in tool.schema["required"]}
            self.assertIsInstance(tool.describe(args), str)

    def test_unknown_tool_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ToolError):
                REGISTRY.call("no_such_tool", {}, make_context(Path(tmp)))

    def test_unknown_argument_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ToolError):
                REGISTRY.call("list_directory", {"nonsense": 1}, make_context(Path(tmp)))

    def test_missing_required_argument_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ToolError):
                REGISTRY.call("read_file", {}, make_context(Path(tmp)))


class FilesystemToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ctx = make_context(self.tmp)

    def call(self, name, **args):
        return REGISTRY.call(name, args, self.ctx)

    def test_write_then_read_round_trip(self):
        target = self.tmp / "note.txt"
        self.call("write_file", path=str(target), content="hello device")
        self.assertIn("hello device", self.call("read_file", path=str(target)))

    def test_append_adds_rather_than_replaces(self):
        target = self.tmp / "log.txt"
        self.call("write_file", path=str(target), content="one\n")
        self.call("write_file", path=str(target), content="two\n", append=True)
        self.assertEqual(target.read_text(), "one\ntwo\n")

    def test_write_outside_writable_root_is_refused(self):
        with self.assertRaises(ToolError) as caught:
            self.call("write_file", path="/etc/jarvis-should-not-exist", content="x")
        self.assertIn("outside the writable roots", str(caught.exception))

    def test_find_files_matches_by_glob(self):
        (self.tmp / "a.pdf").write_text("x")
        (self.tmp / "b.txt").write_text("x")
        output = self.call("find_files", pattern="*.pdf", path=str(self.tmp))
        self.assertIn("a.pdf", output)
        self.assertNotIn("b.txt", output)

    def test_search_in_files_finds_matching_lines(self):
        (self.tmp / "src.py").write_text("alpha\nbeta gamma\n")
        output = self.call("search_in_files", query="BETA", path=str(self.tmp))
        self.assertIn("beta gamma", output)

    def test_move_refuses_to_clobber_an_existing_file(self):
        (self.tmp / "a").write_text("a")
        (self.tmp / "b").write_text("b")
        with self.assertRaises(ToolError):
            self.call("move_path", source=str(self.tmp / "a"), destination=str(self.tmp / "b"))

    def test_reading_a_credential_file_requires_confirmation(self):
        secret = self.tmp / ".ssh" / "id_rsa"
        secret.parent.mkdir()
        secret.write_text("PRIVATE KEY")
        ctx = make_context(self.tmp, policy=Policy.ASK, confirm=lambda *a: False)
        with self.assertRaises(Denied):
            REGISTRY.call("read_file", {"path": str(secret)}, ctx)

    def test_dry_run_reports_without_touching_disk(self):
        ctx = make_context(self.tmp, policy=Policy.YOLO, dry_run=True)
        target = self.tmp / "never.txt"
        output = REGISTRY.call("write_file", {"path": str(target), "content": "x"}, ctx)
        self.assertIn("dry run", output)
        self.assertFalse(target.exists())

    def test_dry_run_still_allows_reads(self):
        (self.tmp / "r.txt").write_text("visible")
        ctx = make_context(self.tmp, policy=Policy.YOLO, dry_run=True)
        self.assertIn("visible", REGISTRY.call("read_file", {"path": str(self.tmp / "r.txt")}, ctx))


# -- agent loop, driven by a stub client ---------------------------------


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_block(tool_id, name, args):
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=args)


def response(content, stop_reason="end_turn"):
    return SimpleNamespace(content=content, stop_reason=stop_reason, stop_details=None)


class StubClient:
    """Replays a scripted list of responses and records what it was sent."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return self._responses.pop(0)


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = Settings()
        self.settings.writable_roots = [self.tmp]
        self.settings.data_dir = self.tmp / ".jarvis"

    def make_agent(self, responses, **approver_kwargs):
        approver_kwargs.setdefault("policy", Policy.YOLO)
        return Agent(
            client=StubClient(responses),
            settings=self.settings,
            approver=Approver(**approver_kwargs),
        )

    def test_plain_answer_needs_no_tools(self):
        agent = self.make_agent([response([text_block("It is Tuesday.")])])
        self.assertEqual(agent.send("what day is it"), "It is Tuesday.")

    def test_tool_call_runs_and_loops_back(self):
        target = self.tmp / "todo.txt"
        agent = self.make_agent(
            [
                response(
                    [tool_block("t1", "write_file", {"path": str(target), "content": "buy milk"})],
                    stop_reason="tool_use",
                ),
                response([text_block("Written.")]),
            ]
        )
        self.assertEqual(agent.send("write a todo"), "Written.")
        self.assertEqual(target.read_text(), "buy milk")

        # The tool result must go back as a user message holding a tool_result block.
        result_message = agent.messages[2]
        self.assertEqual(result_message["role"], "user")
        self.assertEqual(result_message["content"][0]["type"], "tool_result")
        self.assertFalse(result_message["content"][0]["is_error"])

    def test_parallel_tool_calls_return_in_one_message(self):
        agent = self.make_agent(
            [
                response(
                    [
                        tool_block("t1", "write_file", {"path": str(self.tmp / "a"), "content": "a"}),
                        tool_block("t2", "write_file", {"path": str(self.tmp / "b"), "content": "b"}),
                    ],
                    stop_reason="tool_use",
                ),
                response([text_block("Both written.")]),
            ]
        )
        agent.send("write two files")
        results = agent.messages[2]["content"]
        self.assertEqual([block["tool_use_id"] for block in results], ["t1", "t2"])

    def test_denied_tool_reports_back_as_an_error_not_a_crash(self):
        target = self.tmp / "nope.txt"
        agent = self.make_agent(
            [
                response(
                    [tool_block("t1", "write_file", {"path": str(target), "content": "x"})],
                    stop_reason="tool_use",
                ),
                response([text_block("Understood, leaving it alone.")]),
            ],
            policy=Policy.ASK,
            confirm=lambda *a: False,
        )
        self.assertEqual(agent.send("write it"), "Understood, leaving it alone.")
        self.assertFalse(target.exists())

        result = agent.messages[2]["content"][0]
        self.assertTrue(result["is_error"])
        self.assertIn("declined", result["content"])

    def test_failing_tool_is_reported_to_claude(self):
        agent = self.make_agent(
            [
                response(
                    [tool_block("t1", "read_file", {"path": str(self.tmp / "missing")})],
                    stop_reason="tool_use",
                ),
                response([text_block("That file does not exist.")]),
            ]
        )
        agent.send("read the missing file")
        self.assertTrue(agent.messages[2]["content"][0]["is_error"])

    def test_pause_turn_is_resumed(self):
        agent = self.make_agent(
            [
                response([text_block("searching")], stop_reason="pause_turn"),
                response([text_block("Here is what I found.")]),
            ]
        )
        self.assertEqual(agent.send("search the web"), "Here is what I found.")

    def test_runaway_loop_is_capped(self):
        self.settings.max_iterations = 3
        agent = self.make_agent(
            [
                response(
                    [tool_block(f"t{i}", "current_datetime", {})],
                    stop_reason="tool_use",
                )
                for i in range(3)
            ]
        )
        self.assertIn("too many steps", agent.send("loop forever"))

    def test_request_carries_tools_and_a_cached_system_prompt(self):
        agent = self.make_agent([response([text_block("hi")])])
        agent.send("hello")
        request = agent.client.requests[0]
        self.assertEqual(request["model"], self.settings.model)
        self.assertEqual(request["system"][0]["cache_control"], {"type": "ephemeral"})
        names = [tool.get("name") for tool in request["tools"]]
        self.assertIn("run_command", names)
        self.assertIn("web_search", names)

    def test_remembered_facts_reach_the_system_prompt(self):
        ctx = ToolContext(settings=self.settings, approver=Approver(policy=Policy.YOLO))
        REGISTRY.call("remember", {"fact": "The user prefers dark mode."}, ctx)

        agent = self.make_agent([response([text_block("ok")])])
        agent.send("hello")
        self.assertIn("dark mode", agent.client.requests[0]["system"][0]["text"])


if __name__ == "__main__":
    unittest.main()
