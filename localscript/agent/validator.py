"""luacheck-based Lua static analysis."""

import os
import re
import subprocess
import tempfile


def run_luacheck(lua_code: str) -> list[str]:
    """Run luacheck on lua_code and return a list of error/warning strings.

    Each entry is formatted as "Line N: (CODE) message".
    An empty list means the code passed cleanly.

    Raises:
        FileNotFoundError: If luacheck is not installed / not on PATH.
    """
    # Write code to a temp file — luacheck needs a file path.
    with tempfile.NamedTemporaryFile(
        suffix=".lua", mode="w", encoding="utf-8", delete=False
    ) as f:
        f.write(lua_code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [
                "luacheck",
                tmp_path,
                "--config", _find_luacheckrc(),
                "--formatter", "plain",
                "--no-color",
            ],
            capture_output=True,
            text=True,
        )
        return _parse_output(result.stdout, tmp_path)

    except FileNotFoundError:
        raise FileNotFoundError(
            "luacheck not found on PATH.\n"
            "  macOS:  brew install luacheck\n"
            "  Ubuntu: sudo luarocks install luacheck"
        )
    finally:
        os.unlink(tmp_path)


def _find_luacheckrc() -> str:
    """Return the path to .luacheckrc, searching upward from this file."""
    candidate = os.path.join(os.path.dirname(__file__), "..", "..", ".luacheckrc")
    resolved = os.path.normpath(os.path.abspath(candidate))
    if os.path.exists(resolved):
        return resolved
    # Fallback: let luacheck find it itself via its default search
    return ".luacheckrc"


def _parse_output(output: str, tmp_path: str) -> list[str]:
    """Parse luacheck plain-formatter output into clean error strings."""
    errors: list[str] = []
    escaped = re.escape(tmp_path)
    pattern = re.compile(rf"^{escaped}:(\d+):\d+:\s+(.+)$")

    for line in output.splitlines():
        m = pattern.match(line.strip())
        if m:
            errors.append(f"Line {m.group(1)}: {m.group(2)}")

    return errors
