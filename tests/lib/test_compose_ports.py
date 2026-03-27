"""Tests for compose.py — port allocation, naming, and expose_all_ports."""

from generate_ledger.compose import ComposeConfig, gen_compose_data


class TestValidatorNaming:
    def test_single_digit_no_padding(self):
        cfg = ComposeConfig(num_validators=5)
        assert cfg.validator_label(0) == "val0"
        assert cfg.validator_label(4) == "val4"
        assert cfg.first_validator == "val0"

    def test_double_digit_zero_padded(self):
        cfg = ComposeConfig(num_validators=50)
        assert cfg.validator_label(0) == "val00"
        assert cfg.validator_label(9) == "val09"
        assert cfg.validator_label(49) == "val49"
        assert cfg.first_validator == "val00"

    def test_hundred_validators(self):
        cfg = ComposeConfig(num_validators=100)
        assert cfg.validator_label(0) == "val00"
        assert cfg.validator_label(99) == "val99"

    def test_triple_digit_zero_padded(self):
        cfg = ComposeConfig(num_validators=1000)
        assert cfg.validator_label(0) == "val000"
        assert cfg.validator_label(999) == "val999"

    def test_ten_validators_pads(self):
        cfg = ComposeConfig(num_validators=10)
        assert cfg.validator_label(0) == "val0"
        assert cfg.validator_label(9) == "val9"

    def test_eleven_validators_pads(self):
        cfg = ComposeConfig(num_validators=11)
        assert cfg.validator_label(0) == "val00"
        assert cfg.validator_label(10) == "val10"


class TestPortAllocation:
    def test_default_only_first_validator_has_ports(self):
        cfg = ComposeConfig(num_validators=5)
        data = gen_compose_data(cfg)
        services = data["services"]
        assert "ports" in services[cfg.first_validator]
        for i in range(1, 5):
            assert "ports" not in services[cfg.validator_label(i)]

    def test_expose_all_ports(self):
        cfg = ComposeConfig(num_validators=5, expose_all_ports=True)
        data = gen_compose_data(cfg)
        services = data["services"]
        for i in range(5):
            assert "ports" in services[cfg.validator_label(i)]

    def test_50_validators_no_port_collisions(self):
        cfg = ComposeConfig(num_validators=50, expose_all_ports=True)
        data = gen_compose_data(cfg)
        services = data["services"]

        all_host_ports = []
        for _name, svc in services.items():
            if "ports" not in svc:
                continue
            for mapping in svc["ports"]:
                host_port = int(str(mapping).split(":")[0])
                all_host_ports.append(host_port)

        assert len(all_host_ports) == len(set(all_host_ports)), (
            f"Port collision detected among {len(all_host_ports)} mappings"
        )

    def test_50_validators_port_formula(self):
        cfg = ComposeConfig(num_validators=50, expose_all_ports=True, num_hubs=1)
        data = gen_compose_data(cfg)
        services = data["services"]

        for i in range(50):
            name = cfg.validator_label(i)
            ports = services[name]["ports"]
            rpc_mapping = str(ports[0])
            ws_mapping = str(ports[1])
            expected_rpc = f"{cfg.rpc_port + i + cfg.num_hubs}:{cfg.rpc_port}"
            expected_ws = f"{cfg.ws_port + i + cfg.num_hubs}:{cfg.ws_port}"
            assert rpc_mapping == expected_rpc, f"{name}: RPC {rpc_mapping} != {expected_rpc}"
            assert ws_mapping == expected_ws, f"{name}: WS {ws_mapping} != {expected_ws}"

    def test_hub_ports_dont_collide_with_validators(self):
        cfg = ComposeConfig(num_validators=50, expose_all_ports=True, num_hubs=2)
        data = gen_compose_data(cfg)
        services = data["services"]

        all_host_ports = []
        for svc in services.values():
            if "ports" not in svc:
                continue
            for mapping in svc["ports"]:
                host_port = int(str(mapping).split(":")[0])
                all_host_ports.append(host_port)

        assert len(all_host_ports) == len(set(all_host_ports)), (
            f"Port collision between hubs and validators: {len(all_host_ports)} mappings, "
            f"{len(all_host_ports) - len(set(all_host_ports))} duplicates"
        )

    def test_compose_service_names_are_padded(self):
        cfg = ComposeConfig(num_validators=50, expose_all_ports=True)
        data = gen_compose_data(cfg)
        services = data["services"]
        assert "val00" in services
        assert "val49" in services
        assert "val0" not in services
