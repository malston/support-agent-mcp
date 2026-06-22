"""Deliverable 5: committed .mcp.json carries structure, not secrets.

Project scope (committed, shared via git); every secret comes from the
environment via ${VAR} expansion. The tests run against the REAL committed file
-- they are an artifact check, not a fixture check.
"""

from support_agent.config import (
    env_var_refs,
    expand_env,
    find_hardcoded_secrets,
    load_mcp_config,
    mcp_config_path,
)

EXPECTED_VARS = {
    "SUPPORT_ORDERS_API_KEY",
    "SUPPORT_ORDERS_DB_URL",
    "SUPPORT_REFUND_SIGNING_SECRET",
}


def test_config_is_a_committed_project_scope_file():
    path = mcp_config_path()
    assert path.name == ".mcp.json"
    assert path.exists()


def test_every_secret_uses_var_expansion():
    cfg = load_mcp_config()
    assert env_var_refs(cfg) == EXPECTED_VARS


def test_committed_config_leaks_zero_secrets():
    assert find_hardcoded_secrets(load_mcp_config()) == []


def test_expansion_pulls_values_from_the_environment():
    expanded = expand_env(
        load_mcp_config(),
        {
            "SUPPORT_ORDERS_API_KEY": "sk-test",
            "SUPPORT_ORDERS_DB_URL": "postgres://u:p@host/db",
            "SUPPORT_REFUND_SIGNING_SECRET": "shh",
        },
    )
    env = expanded["mcpServers"]["support-agent"]["env"]
    assert env["ORDERS_API_KEY"] == "sk-test"
    assert "${" not in env["ORDERS_DB_URL"]


def test_scanner_catches_a_hardcoded_secret_distractor():
    # The distractor: a config that hardcodes a credential instead of ${VAR}.
    bad = {"mcpServers": {"support-agent": {"env": {"ORDERS_API_KEY": "sk-live-abc123"}}}}
    assert find_hardcoded_secrets(bad) == ["support-agent.env.ORDERS_API_KEY"]


def test_scanner_catches_a_default_secret():
    # A ${VAR:-default} default IS a hardcoded credential on a secret key.
    env = {"ORDERS_API_KEY": "${ORDERS_API_KEY:-sk-default}"}
    bad = {"mcpServers": {"support-agent": {"env": env}}}
    assert find_hardcoded_secrets(bad) == ["support-agent.env.ORDERS_API_KEY"]


def test_bare_var_ref_on_a_secret_key_is_allowed():
    ok = {"mcpServers": {"support-agent": {"env": {"ORDERS_API_KEY": "${ORDERS_API_KEY}"}}}}
    assert find_hardcoded_secrets(ok) == []


def test_expand_env_missing_var_with_no_default_raises():
    import pytest

    cfg = {"mcpServers": {"s": {"env": {"K": "${NEEDED}"}}}}
    with pytest.raises(KeyError):
        expand_env(cfg, {})


def test_expand_env_uses_the_default_when_var_is_absent():
    cfg = {"mcpServers": {"s": {"env": {"K": "${OPTIONAL:-fallback}"}}}}
    expanded = expand_env(cfg, {})
    assert expanded["mcpServers"]["s"]["env"]["K"] == "fallback"
