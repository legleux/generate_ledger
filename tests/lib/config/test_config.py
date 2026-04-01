"""TDD tests for the layered TOML config compositor."""

import pytest

from generate_ledger.xrpld_cfg import (
    NodeRole,
    Section,
    ServerConfig,
    XrpldConfigSpec,
    XrpldNodeConfig,
    build_config,
    build_sections,
    deep_merge,
    gen_database_path,
    gen_debug_logfile,
    gen_features,
    gen_ips_fixed,
    gen_ledger_history,
    gen_node_db,
    gen_node_size,
    gen_port_peer,
    gen_port_rpc_admin_local,
    gen_port_ws_admin_local,
    gen_rpc_startup,
    gen_server,
    gen_validation_seed,
    gen_validators,
    gen_voting,
    load_layers,
    load_toml_file,
    render_sections,
    render_xrpld_cfg,
)

# ── deep_merge ──────────────────────────────────────────────────────


class TestDeepMerge:
    def test_scalars_override(self):
        assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_nested_dicts_recurse(self):
        base = {"server": {"port": 5005, "host": "localhost"}}
        override = {"server": {"port": 8080}}
        assert deep_merge(base, override) == {"server": {"port": 8080, "host": "localhost"}}

    def test_lists_override(self):
        base = {"nodes": ["a", "b"]}
        override = {"nodes": ["c"]}
        assert deep_merge(base, override) == {"nodes": ["c"]}

    def test_empty_override_is_noop(self):
        base = {"a": 1, "b": {"c": 2}}
        assert deep_merge(base, {}) == base

    def test_new_keys_added(self):
        assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_does_not_mutate_inputs(self):
        base = {"server": {"port": 5005}}
        override = {"server": {"port": 8080}}
        deep_merge(base, override)
        assert base == {"server": {"port": 5005}}


# ── load_toml_file ─────────────────────────────────────────────────


class TestLoadTomlFile:
    def test_valid_toml(self, tmp_path):
        f = tmp_path / "test.toml"
        f.write_text('[server]\nport = 5005\nhost = "localhost"\n')
        result = load_toml_file(f)
        assert result == {"server": {"port": 5005, "host": "localhost"}}

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_toml_file(tmp_path / "nope.toml")

    def test_empty_file_returns_empty_dict(self, tmp_path):
        f = tmp_path / "empty.toml"
        f.write_text("")
        assert load_toml_file(f) == {}


# ── load_layers ─────────────────────────────────────────────────────


class TestLoadLayers:
    def test_merges_in_order(self, tmp_path):
        base = tmp_path / "base.toml"
        base.write_text('[server]\nport = 5005\nnode_size = "medium"\n')

        override = tmp_path / "override.toml"
        override.write_text("[server]\nport = 8080\n")

        result = load_layers([base, override])
        assert result == {"server": {"port": 8080, "node_size": "medium"}}

    def test_single_layer(self, tmp_path):
        f = tmp_path / "only.toml"
        f.write_text("value = 42\n")
        assert load_layers([f]) == {"value": 42}

    def test_empty_list_returns_empty_dict(self):
        assert load_layers([]) == {}


# ── NodeRole ────────────────────────────────────────────────────────


class TestNodeRole:
    def test_enum_values(self):
        assert NodeRole.VALIDATOR == "validator"
        assert NodeRole.NODE == "node"

    def test_is_str_enum(self):
        assert isinstance(NodeRole.VALIDATOR, str)


# ── Pydantic models ────────────────────────────────────────────────


class TestServerConfig:
    def test_defaults(self):
        cfg = ServerConfig()
        assert cfg.node_size == "huge"
        assert cfg.peer_port == 2459
        assert cfg.rpc_admin_port == 5005
        assert cfg.ws_admin_port == 6006


class TestXrpldNodeConfig:
    def _validator_cfg(self, **overrides):
        defaults = {
            "role": NodeRole.VALIDATOR,
            "validator": {"enabled": True, "token": "[validation_seed]\nseed123"},
        }
        defaults.update(overrides)
        return XrpldNodeConfig.model_validate(defaults)

    def _node_cfg(self, **overrides):
        defaults = {"role": NodeRole.NODE}
        defaults.update(overrides)
        return XrpldNodeConfig.model_validate(defaults)

    def test_valid_validator(self):
        cfg = self._validator_cfg()
        assert cfg.role is NodeRole.VALIDATOR
        assert cfg.validator.enabled is True

    def test_valid_node(self):
        cfg = self._node_cfg()
        assert cfg.role is NodeRole.NODE
        assert cfg.validator.enabled is False

    def test_validator_requires_enabled(self):
        with pytest.raises(ValueError, match=r"validator\.enabled"):
            XrpldNodeConfig.model_validate(
                {
                    "role": "validator",
                    "validator": {"enabled": False},
                }
            )

    def test_validator_requires_token(self):
        with pytest.raises(ValueError, match=r"validator\.token"):
            XrpldNodeConfig.model_validate(
                {
                    "role": "validator",
                    "validator": {"enabled": True, "token": None},
                }
            )

    def test_node_cannot_enable_validator(self):
        with pytest.raises(ValueError, match="node role cannot enable validator"):
            XrpldNodeConfig.model_validate(
                {
                    "role": "node",
                    "validator": {"enabled": True, "token": "x"},
                }
            )


# ── Renderer ────────────────────────────────────────────────────────


class TestRenderXrpldCfg:
    def _make_validator(self, **overrides):
        defaults = {
            "role": NodeRole.VALIDATOR,
            "validator": {"enabled": True, "token": "[validation_seed]\nseed123"},
            "network": {
                "ips_fixed": ["val1 2459", "val2 2459"],
                "validator_pubkeys": ["nHUpubkey0", "nHUpubkey1"],
            },
        }
        defaults.update(overrides)
        return XrpldNodeConfig.model_validate(defaults)

    def _make_node(self, **overrides):
        defaults = {
            "role": NodeRole.NODE,
            "network": {
                "ips_fixed": ["val0 2459", "val1 2459"],
                "validator_pubkeys": ["nHUpubkey0", "nHUpubkey1"],
            },
        }
        defaults.update(overrides)
        return XrpldNodeConfig.model_validate(defaults)

    def test_produces_valid_sections(self):
        cfg = self._make_validator()
        rendered = render_xrpld_cfg(cfg)
        for section in ("[server]", "[node_db]", "[node_size]", "[database_path]", "[debug_logfile]"):
            assert section in rendered

    def test_validator_has_validation_seed(self):
        cfg = self._make_validator()
        rendered = render_xrpld_cfg(cfg)
        assert "[validation_seed]" in rendered
        assert "seed123" in rendered

    def test_node_lacks_validation_seed(self):
        cfg = self._make_node()
        rendered = render_xrpld_cfg(cfg)
        assert "[validation_seed]" not in rendered

    def test_validator_no_ledger_history_full(self):
        cfg = self._make_validator()
        rendered = render_xrpld_cfg(cfg)
        assert "[ledger_history]" not in rendered

    def test_node_has_ledger_history_full(self):
        cfg = self._make_node()
        rendered = render_xrpld_cfg(cfg)
        assert "[ledger_history]" in rendered
        assert "full" in rendered

    def test_voting_section_for_validator(self):
        cfg = self._make_validator()
        rendered = render_xrpld_cfg(cfg)
        assert "[voting]" in rendered
        assert "reference_fee = 10" in rendered

    def test_no_voting_section_for_node(self):
        cfg = self._make_node()
        rendered = render_xrpld_cfg(cfg)
        assert "[voting]" not in rendered

    def test_features_block(self):
        cfg = self._make_validator(features={"amendments": ["FixAmendment1", "FixAmendment2"]})
        rendered = render_xrpld_cfg(cfg)
        assert "[features]" in rendered
        assert "FixAmendment1" in rendered
        assert "FixAmendment2" in rendered

    def test_no_features_when_empty(self):
        cfg = self._make_validator()
        rendered = render_xrpld_cfg(cfg)
        assert "[features]" not in rendered

    def test_amendment_majority_time(self):
        cfg = self._make_validator(features={"amendments": ["Fix1"], "majority_time": "2 minutes"})
        rendered = render_xrpld_cfg(cfg)
        assert "[amendment_majority_time]" in rendered
        assert "2 minutes" in rendered

    def test_ips_fixed(self):
        cfg = self._make_validator()
        rendered = render_xrpld_cfg(cfg)
        assert "[ips_fixed]" in rendered
        assert "val1 2459" in rendered
        assert "val2 2459" in rendered

    def test_log_level(self):
        cfg = self._make_validator(logging={"level": "debug"})
        rendered = render_xrpld_cfg(cfg)
        assert '"severity": "debug"' in rendered

    def test_validator_pubkeys(self):
        cfg = self._make_validator()
        rendered = render_xrpld_cfg(cfg)
        assert "[validators]" in rendered
        assert "nHUpubkey0" in rendered
        assert "nHUpubkey1" in rendered


# ── Section generators ──────────────────────────────────────────────


def _validator_cfg(**overrides):
    defaults = {
        "role": NodeRole.VALIDATOR,
        "validator": {"enabled": True, "token": "[validation_seed]\nseed123"},
        "network": {
            "ips_fixed": ["val1 2459", "val2 2459"],
            "validator_pubkeys": ["nHUpubkey0", "nHUpubkey1"],
        },
    }
    defaults.update(overrides)
    return XrpldNodeConfig.model_validate(defaults)


def _node_cfg(**overrides):
    defaults = {
        "role": NodeRole.NODE,
        "network": {
            "ips_fixed": ["val0 2459", "val1 2459"],
            "validator_pubkeys": ["nHUpubkey0", "nHUpubkey1"],
        },
    }
    defaults.update(overrides)
    return XrpldNodeConfig.model_validate(defaults)


class TestSectionDataclass:
    def test_section_has_name_and_lines(self):
        s = Section("node_size", ["huge"])
        assert s.name == "node_size"
        assert s.lines == ["huge"]


class TestGenNodeSize:
    def test_returns_section(self):
        s = gen_node_size(_validator_cfg())
        assert s.name == "node_size"
        assert s.lines == ["huge"]


class TestGenServer:
    def test_includes_all_ports(self):
        s = gen_server(_validator_cfg())
        assert s.name == "server"
        assert "port_rpc_admin_local" in s.lines
        assert "port_peer" in s.lines
        assert "port_ws_admin_local" in s.lines


class TestGenPortRpcAdminLocal:
    def test_default_port(self):
        s = gen_port_rpc_admin_local(_validator_cfg())
        assert s.name == "port_rpc_admin_local"
        assert "port = 5005" in s.lines
        assert "protocol = http" in s.lines


class TestGenPortPeer:
    def test_default_port(self):
        s = gen_port_peer(_validator_cfg())
        assert s.name == "port_peer"
        assert "port = 2459" in s.lines
        assert "protocol = peer" in s.lines


class TestGenPortWsAdminLocal:
    def test_default_port(self):
        s = gen_port_ws_admin_local(_validator_cfg())
        assert s.name == "port_ws_admin_local"
        assert "port = 6006" in s.lines
        assert "protocol = ws" in s.lines
        assert "send_queue_limit = 500" in s.lines


class TestGenNodeDb:
    def test_returns_section(self):
        s = gen_node_db(_validator_cfg())
        assert s.name == "node_db"
        assert "type = NuDB" in s.lines


class TestGenLedgerHistory:
    def test_none_for_validator(self):
        assert gen_ledger_history(_validator_cfg()) is None

    def test_full_for_node(self):
        s = gen_ledger_history(_node_cfg())
        assert s is not None
        assert s.name == "ledger_history"
        assert s.lines == ["full"]


class TestGenDatabasePath:
    def test_returns_section(self):
        s = gen_database_path(_validator_cfg())
        assert s.name == "database_path"
        assert "/var/lib/xrpld/db" in s.lines


class TestGenDebugLogfile:
    def test_returns_section(self):
        s = gen_debug_logfile(_validator_cfg())
        assert s.name == "debug_logfile"


class TestGenRpcStartup:
    def test_log_level(self):
        s = gen_rpc_startup(_validator_cfg(logging={"level": "debug"}))
        assert s.name == "rpc_startup"
        assert '"severity": "debug"' in s.lines[0]


class TestGenIpsFixed:
    def test_returns_peers(self):
        s = gen_ips_fixed(_validator_cfg())
        assert s is not None
        assert s.name == "ips_fixed"
        assert "val1 2459" in s.lines

    def test_none_when_empty(self):
        cfg = _validator_cfg(network={"ips_fixed": [], "validator_pubkeys": ["pk"]})
        assert gen_ips_fixed(cfg) is None


class TestGenValidators:
    def test_returns_pubkeys(self):
        s = gen_validators(_validator_cfg())
        assert s is not None
        assert s.name == "validators"
        assert "nHUpubkey0" in s.lines

    def test_none_when_empty(self):
        cfg = _validator_cfg(network={"ips_fixed": ["val1 2459"], "validator_pubkeys": []})
        assert gen_validators(cfg) is None


class TestGenVoting:
    def test_present_for_validator(self):
        s = gen_voting(_validator_cfg())
        assert s is not None
        assert s.name == "voting"
        assert "reference_fee = 10" in s.lines

    def test_none_for_node(self):
        assert gen_voting(_node_cfg()) is None


class TestGenFeatures:
    def test_present_when_amendments(self):
        s = gen_features(_validator_cfg(features={"amendments": ["FixA", "FixB"]}))
        assert s is not None
        assert s.name == "features"
        assert "FixA" in s.lines
        assert "FixB" in s.lines

    def test_none_when_empty(self):
        assert gen_features(_validator_cfg()) is None


class TestGenValidationSeed:
    def test_present_for_validator(self):
        s = gen_validation_seed(_validator_cfg())
        assert s is not None
        assert s.name == "validation_seed"
        assert "seed123" in s.lines

    def test_none_for_node(self):
        assert gen_validation_seed(_node_cfg()) is None


class TestBuildSections:
    def test_returns_list_of_sections(self):
        sections = build_sections(_validator_cfg())
        assert all(isinstance(s, Section) for s in sections)
        names = [s.name for s in sections]
        assert "server" in names
        assert "node_size" in names
        assert "voting" in names

    def test_no_none_entries(self):
        sections = build_sections(_node_cfg())
        assert None not in sections


class TestRenderSections:
    def test_formats_sections(self):
        sections = [Section("node_size", ["huge"]), Section("peers_max", ["64"])]
        result = render_sections(sections)
        assert "[node_size]\nhuge\n\n[peers_max]\n64\n" == result


# ── XrpldConfigSpec ─────────────────────────────────────────────────

_counter = [0]


def _fake_keygen():
    i = _counter[0]
    pk = f"nHUfake{i:04d}"
    token = f"[validation_seed]\nfakeseed{i}"
    _counter[0] += 1
    return pk, token


class TestXrpldConfigSpec:
    def setup_method(self):
        _counter[0] = 0

    def _builder(self, tmp_path, **kw):
        defaults = {"num_validators": 3, "base_dir": tmp_path, "keygen": _fake_keygen}
        defaults.update(kw)
        return XrpldConfigSpec(**defaults)

    def test_creates_n_plus_1_nodes(self, tmp_path):
        result = self._builder(tmp_path).build()
        assert len(result.nodes) == 4  # 3 validators + 1 xrpld

    def test_validator_names_zero_padded(self, tmp_path):
        result = self._builder(tmp_path, num_validators=12).build()
        names = [n.name for n in result.nodes if n.is_validator]
        assert names[0] == "val00"
        assert names[9] == "val09"
        assert names[11] == "val11"

    def test_single_digit_no_padding(self, tmp_path):
        result = self._builder(tmp_path, num_validators=3).build()
        names = [n.name for n in result.nodes if n.is_validator]
        assert names == ["val0", "val1", "val2"]

    def test_ips_fixed_excludes_self(self, tmp_path):
        result = self._builder(tmp_path, num_validators=3).build()
        val0 = next(n for n in result.nodes if n.name == "val0")
        assert "val0 " not in val0.config_text.split("[ips_fixed]")[1].split("[")[0]
        assert "val1 2459" in val0.config_text
        assert "val2 2459" in val0.config_text

    def test_ips_fixed_node_includes_all(self, tmp_path):
        result = self._builder(tmp_path, num_validators=3).build()
        xrpld = next(n for n in result.nodes if n.name == "xrpld")
        ips_section = xrpld.config_text.split("[ips_fixed]")[1].split("[")[0]
        assert "val0 2459" in ips_section
        assert "val1 2459" in ips_section
        assert "val2 2459" in ips_section

    def test_all_nodes_share_pubkeys(self, tmp_path):
        result = self._builder(tmp_path, num_validators=2).build()
        for node in result.nodes:
            assert "nHUfake0000" in node.config_text
            assert "nHUfake0001" in node.config_text

    def test_write_creates_dirs(self, tmp_path):
        result = self._builder(tmp_path, num_validators=2).write()
        assert len(result.paths) == 3
        for p in result.paths:
            assert p.exists()
            assert p.name == "xrpld.cfg"

    def test_validator_has_voting_node_does_not(self, tmp_path):
        result = self._builder(tmp_path, num_validators=1).build()
        val = next(n for n in result.nodes if n.is_validator)
        xrpld = next(n for n in result.nodes if not n.is_validator)
        assert "[voting]" in val.config_text
        assert "[voting]" not in xrpld.config_text

    def test_features_passed_through(self, tmp_path):
        builder = self._builder(tmp_path, features=["FixAmm", "FixNFT"])
        result = builder.build()
        for node in result.nodes:
            assert "FixAmm" in node.config_text
            assert "FixNFT" in node.config_text

    def test_log_level(self, tmp_path):
        result = self._builder(tmp_path, log_level="trace").build()
        for node in result.nodes:
            assert '"severity": "trace"' in node.config_text

    def test_defaults_come_from_base_toml(self, tmp_path):
        """XrpldConfigSpec should read defaults from bundled base.toml, not hardcode them."""
        spec = self._builder(tmp_path)
        result = spec.build()
        # peer_port should match base.toml (2459), not some hardcoded value
        val0 = next(n for n in result.nodes if n.name == "val0")
        assert "val1 2459" in val0.config_text
        # node_size should match base.toml ("huge")
        assert "huge" in val0.config_text

    def test_custom_config_dir_overrides_defaults(self, tmp_path):
        """A custom config_dir with different base.toml should change rendered output."""
        cfg_dir = tmp_path / "custom_config"
        cfg_dir.mkdir()
        (cfg_dir / "base.toml").write_text(
            '[server]\nnode_size = "small"\npeer_port = 9999\n[logging]\nlevel = "warning"\n'
        )
        roles_dir = cfg_dir / "roles"
        roles_dir.mkdir()
        (roles_dir / "validator.toml").write_text("[validator]\nenabled = true\n")
        (roles_dir / "node.toml").write_text("")

        spec = XrpldConfigSpec(
            num_validators=1,
            base_dir=tmp_path / "out",
            keygen=_fake_keygen,
            config_dir=cfg_dir,
        )
        result = spec.build()
        val0 = next(n for n in result.nodes if n.is_validator)
        assert "small" in val0.config_text
        assert "9999" in val0.config_text
        assert '"severity": "warning"' in val0.config_text

    def test_bundled_base_toml_drives_all_rendered_values(self, tmp_path):
        """Every non-dynamic value in rendered output should trace back to TOML layers."""
        from generate_ledger.xrpld_cfg import _CONFIG_DIR, load_toml_file

        base = load_toml_file(_CONFIG_DIR / "base.toml")

        spec = self._builder(tmp_path, num_validators=1)
        result = spec.build()
        val0 = next(n for n in result.nodes if n.is_validator)
        xrpld = next(n for n in result.nodes if not n.is_validator)

        # Server values from base.toml, not hardcoded
        assert f"port = {base['server']['rpc_admin_port']}" in val0.config_text
        assert f"port = {base['server']['peer_port']}" in val0.config_text
        assert f"port = {base['server']['ws_admin_port']}" in val0.config_text
        assert base["server"]["node_size"] in val0.config_text

        # Storage from base.toml
        assert base["storage"]["db_path"] in val0.config_text
        assert base["storage"]["nudb_path"] in val0.config_text

        # Logging from base.toml
        assert f'"severity": "{base["logging"]["level"]}"' in val0.config_text

        # Same values on non-validator node
        assert base["server"]["node_size"] in xrpld.config_text
        assert f'"severity": "{base["logging"]["level"]}"' in xrpld.config_text

    def test_changing_base_toml_changes_output(self, tmp_path):
        """If we modify a value in our TOML layers, the output must change accordingly."""
        cfg_dir = tmp_path / "cfg"
        cfg_dir.mkdir()
        (cfg_dir / "base.toml").write_text(
            '[server]\nnode_size = "medium"\npeer_port = 7777\nrpc_admin_port = 1234\nws_admin_port = 5678\n'
            '[storage]\ndb_path = "/custom/db"\ndb_type = "RocksDB"\nnudb_path = "/custom/nudb"\n'
            '[logging]\nlevel = "debug"\nfile = "/custom/log.txt"\n'
        )
        roles_dir = cfg_dir / "roles"
        roles_dir.mkdir()
        (roles_dir / "validator.toml").write_text("[validator]\nenabled = true\n")
        (roles_dir / "node.toml").write_text("")

        spec = XrpldConfigSpec(
            num_validators=1,
            base_dir=tmp_path / "out",
            keygen=_fake_keygen,
            config_dir=cfg_dir,
        )
        result = spec.build()
        val0 = next(n for n in result.nodes if n.is_validator)

        assert "medium" in val0.config_text
        assert "port = 7777" in val0.config_text
        assert "port = 1234" in val0.config_text
        assert "port = 5678" in val0.config_text
        assert "/custom/db" in val0.config_text
        assert "RocksDB" in val0.config_text
        assert '"severity": "debug"' in val0.config_text
        assert "/custom/log.txt" in val0.config_text

    def test_cli_overrides_beat_toml_defaults(self, tmp_path):
        """Explicit overrides (like --log-level) must win over base.toml."""
        spec = self._builder(tmp_path, log_level="error", reference_fee=42)
        result = spec.build()
        val0 = next(n for n in result.nodes if n.is_validator)
        assert '"severity": "error"' in val0.config_text
        assert "reference_fee = 42" in val0.config_text

    def test_none_overrides_use_toml_defaults(self, tmp_path):
        """When overrides are None, TOML defaults should be used (not some hardcoded fallback)."""
        spec = XrpldConfigSpec(
            num_validators=1,
            base_dir=tmp_path,
            keygen=_fake_keygen,
            log_level=None,
            reference_fee=None,
        )
        result = spec.build()
        val0 = next(n for n in result.nodes if n.is_validator)
        # Should use base.toml's level ("info") and default voting fee (10)
        assert '"severity": "info"' in val0.config_text
        assert "reference_fee = 10" in val0.config_text


# ── build_config (TOML layers) ─────────────────────────────────────


class TestBuildConfig:
    def _write_layers(self, tmp_path):
        """Create a minimal TOML layer set in tmp_path."""
        base = tmp_path / "base.toml"
        base.write_text('[server]\nnode_size = "huge"\npeer_port = 2459\n[logging]\nlevel = "info"\n')
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()

        (roles_dir / "validator.toml").write_text(
            '[validator]\nenabled = true\ntoken = "[validation_seed]\\nseed123"\n'
        )
        (roles_dir / "node.toml").write_text("")

        envs_dir = tmp_path / "envs"
        envs_dir.mkdir()
        (envs_dir / "testnet.toml").write_text('[logging]\nlevel = "trace"\n')
        return tmp_path

    def test_loads_base_and_role(self, tmp_path):
        config_dir = self._write_layers(tmp_path)
        cfg = build_config(config_dir, role="validator")
        assert cfg.role is NodeRole.VALIDATOR
        assert cfg.validator.enabled is True
        assert cfg.server.node_size == "huge"

    def test_env_override(self, tmp_path):
        config_dir = self._write_layers(tmp_path)
        cfg = build_config(config_dir, env="testnet", role="node")
        assert cfg.logging.level == "trace"

    def test_missing_layer_raises(self, tmp_path):
        config_dir = self._write_layers(tmp_path)
        with pytest.raises(FileNotFoundError):
            build_config(config_dir, env="production", role="node")


class TestNetworkConfigFields:
    def test_defaults(self):
        from generate_ledger.xrpld_cfg import NetworkConfig

        cfg = NetworkConfig()
        assert cfg.chain == "main"
        assert cfg.peers_max == 64

    def test_mainnet_env_overrides_peers_max(self, tmp_path):
        base = tmp_path / "base.toml"
        base.write_text('[network]\nchain = "main"\npeers_max = 64\n')
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        (roles_dir / "node.toml").write_text("")
        envs_dir = tmp_path / "envs"
        envs_dir.mkdir()
        (envs_dir / "mainnet.toml").write_text("[network]\npeers_max = 128\n")

        cfg = build_config(tmp_path, env="mainnet", role="node")
        assert cfg.network.peers_max == 128
        assert cfg.network.chain == "main"
