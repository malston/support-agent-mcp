"""Load and validate the committed .mcp.json.

The file is project scope (committed, shared via git) and declares which env keys
the server needs -- never their values. Secrets are injected at load time from the
environment via ${VAR} (and the documented ${VAR:-default} form, deliberately
unused for secrets: a default credential is a hardcoded credential).

`find_hardcoded_secrets` is the guard. Its scope is deliberately narrow: it checks
that every secret-bearing key in a server's `env` block is a *bare* ${VAR}
reference (no literal, no ${VAR:-default}). It is a config-hygiene assertion for the
declared env keys -- not a general entropy-based secret detector, and it does not
scan `command`/`args`. Within that scope it makes a hardcoded env credential fail a
test rather than reach git history.
"""

import json
import re
from pathlib import Path

VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}")
# A *bare* reference -- ${VAR} with NO default. A default on a secret-bearing key
# is itself a hardcoded credential, so secret values must be bare references.
BARE_VAR_PATTERN = re.compile(r"\$\{[A-Z_][A-Z0-9_]*\}")

_SECRET_HINTS = ("key", "secret", "token", "password", "passwd", "url", "dsn", "credential")


def mcp_config_path() -> Path:
    # src/support_agent/config.py -> parents[2] is the example root.
    return Path(__file__).resolve().parents[2] / ".mcp.json"


def load_mcp_config(path: Path | None = None) -> dict:
    target = path or mcp_config_path()
    return json.loads(target.read_text())


def _walk_strings(node: object):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_strings(item)


def env_var_refs(config: dict) -> set[str]:
    refs: set[str] = set()
    for text in _walk_strings(config):
        for match in VAR_PATTERN.finditer(text):
            refs.add(match.group(1))
    return refs


def _is_bare_var_ref(value: object) -> bool:
    """True only for ${VAR} with no default -- the one safe form for a secret."""
    return isinstance(value, str) and BARE_VAR_PATTERN.fullmatch(value) is not None


def find_hardcoded_secrets(config: dict) -> list[str]:
    """Return dotted paths to secret-bearing env values that leak a credential.

    A secret-bearing key is safe ONLY when its value is a bare ${VAR}. A literal,
    or a ${VAR:-default} (the default is a hardcoded credential), is flagged.
    """
    findings: list[str] = []
    for server, conf in config.get("mcpServers", {}).items():
        for key, value in conf.get("env", {}).items():
            if any(hint in key.lower() for hint in _SECRET_HINTS) and not _is_bare_var_ref(value):
                findings.append(f"{server}.env.{key}")
    return findings


def expand_env(config: dict, env: dict[str, str]) -> dict:
    """Return a copy with ${VAR} / ${VAR:-default} expanded from `env`."""

    def sub(text: str) -> str:
        def repl(match: re.Match) -> str:
            name, default = match.group(1), match.group(2)
            if name in env:
                return env[name]
            if default is not None:
                return default
            raise KeyError(f"{name} is not set and has no default")

        return VAR_PATTERN.sub(repl, text)

    def walk(node: object) -> object:
        if isinstance(node, str):
            return sub(node)
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk(config)
