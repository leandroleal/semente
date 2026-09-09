"""ADK backend adaptation tests — no network, no model calls.

Covers the engine-agnostic seams the ADK backend owns: media bag (A-M),
tool-hook bridge (A-H), and knowledge tool injection (A-K).
"""

from semente.backends.adk import _adapt_tool, _new_media_bag
from semente.tools import tool
from semente.tools.types import Image, ToolResult


def test_media_bag_stashes_media_and_returns_text():
    def make_map(feature_id: str) -> ToolResult:
        return ToolResult(
            content="map ready",
            images=[Image(content=b"PNGDATA", mime_type="image/png")],
        )

    bag = _new_media_bag()
    adapted = _adapt_tool(make_map, bag)
    out = adapted("f1")

    assert out == "map ready"
    assert len(bag["images"]) == 1
    assert bag["images"][0].mime_type == "image/png"
    assert bag["videos"] == [] and bag["audios"] == [] and bag["files"] == []


def test_media_bag_passes_plain_strings_through():
    def echo(text: str) -> str:
        return text

    bag = _new_media_bag()
    adapted = _adapt_tool(echo, bag)
    assert adapted("hi") == "hi"
    assert bag == {"images": [], "videos": [], "audios": [], "files": []}


def _gate_hook(run_context, function_call, arguments):
    """Mimics validate_selected_property_hook: short-circuit when no property."""
    ss = run_context.session_state
    if ss and "all_properties" in ss:
        return function_call(**arguments)
    return "NO_PROPERTY"


def _make_gated_tool():
    @tool(tool_hooks=[_gate_hook])
    def make_map(run_context, feature_id: str) -> ToolResult:
        return ToolResult(
            content=f"map for {feature_id}",
            images=[Image(content=b"X", mime_type="image/png")],
        )

    return make_map


class _FakeToolContext:
    def __init__(self, state):
        self.state = state
        self.user_id = "u"


def test_hook_short_circuits_without_property():
    bag = _new_media_bag()
    adapted = _adapt_tool(_make_gated_tool(), bag)
    out = adapted(feature_id="f1", tool_context=_FakeToolContext({}))
    assert out == "NO_PROPERTY"
    assert bag["images"] == []


def test_hook_continues_chain_with_property():
    bag = _new_media_bag()
    adapted = _adapt_tool(_make_gated_tool(), bag)
    out = adapted(feature_id="f1", tool_context=_FakeToolContext({"all_properties": [1]}))
    assert out == "map for f1"
    assert len(bag["images"]) == 1


def test_hook_schema_strips_run_context():
    import inspect

    adapted = _adapt_tool(_make_gated_tool(), _new_media_bag())
    params = list(inspect.signature(adapted).parameters)
    assert params == ["feature_id"]


if __name__ == "__main__":
    test_media_bag_stashes_media_and_returns_text()
    test_media_bag_passes_plain_strings_through()
    test_hook_short_circuits_without_property()
    test_hook_continues_chain_with_property()
    test_hook_schema_strips_run_context()
    print("ADK backend tests OK")
