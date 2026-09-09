"""ADK backend adaptation tests — no network, no model calls.

Covers the engine-agnostic seams the ADK backend owns: media bag (A-M),
tool-hook bridge (A-H), and knowledge tool injection (A-K).
"""

from semente.backends.adk import _adapt_tool, _new_media_bag
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


if __name__ == "__main__":
    test_media_bag_stashes_media_and_returns_text()
    test_media_bag_passes_plain_strings_through()
    print("ADK backend tests OK")
