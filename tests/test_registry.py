"""Engine resolution: explicit arg > manifest pin (set_engine) > env var > agno.

Regression: sub-agents call get_backend() with no argument at module import
time — they must resolve to the manifest's engine, not silently fall back to
agno (the 'engine: bare still runs agno' bug).
"""

import os

from semente.backends import registry


def test_resolution_precedence():
    from semente.backends.agno import AgnoBackend
    from semente.backends.bare import BareBackend

    # 1. Explicit argument wins over everything.
    assert isinstance(registry.get_backend("agno"), AgnoBackend)

    # 2. Pinned manifest engine is used by no-arg callers (sub-agents).
    registry.set_engine("bare")
    assert isinstance(registry.get_backend(), BareBackend)

    # 3. Explicit argument still beats the pin.
    assert isinstance(registry.get_backend("agno"), AgnoBackend)

    # 4. Unpinning falls back to the env var, then agno.
    registry.set_engine(None)
    os.environ["SEMENTE_ENGINE"] = "bare"
    assert isinstance(registry.get_backend(), BareBackend)
    del os.environ["SEMENTE_ENGINE"]
    assert isinstance(registry.get_backend(), AgnoBackend)


def test_manifest_engine_absent_is_none():
    """No engine key -> None (so the env var override actually works)."""
    import tempfile
    from pathlib import Path

    from semente.manifest import Manifest

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write("name: test-app\n")
        path = f.name
    try:
        m = Manifest.load(path)
        assert m.engine is None
    finally:
        Path(path).unlink()


if __name__ == "__main__":
    test_resolution_precedence()
    test_manifest_engine_absent_is_none()
    print("Registry resolution tests OK")