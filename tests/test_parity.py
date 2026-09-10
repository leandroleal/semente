"""A-P parity harness — the same native tool must behave identically on every
engine: same schema, same text result, same media artifacts.

The shared tool seam (``backends/toolkit.py``) is the canonical path for ADK
and bare; the agno backend converts a native Tool to an agno Function. These
golden tests pin the two paths to the same output.
"""

from semente.backends.agno import _to_agno_function
from semente.backends.toolkit import StateContext, new_media_bag, run_tool, tool_schema
from semente.tools import ToolResult, Image, tool


@tool(description="Generate a property image")
def generate_image(run_context, feature_id: str) -> ToolResult:
    return ToolResult(
        content=f"image for {feature_id}",
        images=[Image(content=b"\x89PNG", mime_type="image/png")],
    )


def _passthrough_hook(run_context, function_call, arguments):
    return function_call(**arguments)


@tool(description="Add with a hook", tool_hooks=[_passthrough_hook])
def hooked_add(run_context, a: float, b: float) -> ToolResult:
    return ToolResult(content=str(a + b))


def test_schema_parity():
    """agno Function schema == shared tool_schema for the same tool."""
    agno_params = _to_agno_function(generate_image).parameters
    seam_params = tool_schema(generate_image)["parameters"]
    assert agno_params == seam_params


def test_media_result_parity():
    """agno entrypoint and the shared seam produce the same text + media."""
    ctx = StateContext({"all_properties": []})

    # agno path: entrypoint converts Semente ToolResult -> agno ToolResult.
    agno_result = _to_agno_function(generate_image).entrypoint(
        run_context=ctx, feature_id="f1"
    )
    assert agno_result.content == "image for f1"
    assert len(agno_result.images) == 1

    # shared seam (ADK/bare): text returned, media stashed in the bag.
    bag = new_media_bag()
    text = run_tool(generate_image, {"feature_id": "f1"}, ctx, bag)
    assert text == "image for f1"
    assert len(bag["images"]) == 1
    assert bag["images"][0].mime_type == "image/png"


def test_hook_result_parity():
    """A tool with a hook produces the same result on both paths."""
    ctx = StateContext({})

    agno_result = _to_agno_function(hooked_add).entrypoint(run_context=ctx, a=1.0, b=2.0)
    assert agno_result.content == "3.0"

    bag = new_media_bag()
    text = run_tool(hooked_add, {"a": 1.0, "b": 2.0}, ctx, bag)
    assert text == "3.0"


if __name__ == "__main__":
    test_schema_parity()
    test_media_result_parity()
    test_hook_result_parity()
    print("A-P parity tests OK")
