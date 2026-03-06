from generate_ledger.compose import ComposeConfig, gen_compose_data, write_compose_file


def test_gen_compose_data():
    cfg = ComposeConfig()
    # Well that's not a very thorough test
    compose_data = gen_compose_data(config=cfg)
    assert isinstance(compose_data, dict)


def test_write_compose_file(tmp_path):
    cfg = ComposeConfig()
    output_file = tmp_path / "docker-compose.yml"
    written = write_compose_file(output_file=output_file, config=cfg)
    assert written.exists()


def test_write_compose_file_anywhere(tmp_path):
    cfg = ComposeConfig()
    output_file = tmp_path / "docker-compose.yml"
    written = write_compose_file(output_file=output_file, config=cfg)
    assert written.exists()


def test_gen_compose_data1(config):
    data = gen_compose_data(config=config)  # no manual ComposeConfig() here
    assert isinstance(data, dict)
    assert "services" in data


def test_write_compose_file_default_writes_into_tmp(tmp_path):
    # write_compose_file() calls ComposeConfig() internally → sandboxed by autouse
    p = write_compose_file()
    assert p.exists()
    assert p.parent == tmp_path  # lands in the temp dir from the autouse fixture


def test_env_overrides_config_base_dir(tmp_path, monkeypatch):
    # Arrange: point GL_BASE_DIR at a custom dir
    custom = tmp_path / "ENV_BASE"
    monkeypatch.setenv("GL_BASE_DIR", str(custom))

    # Act: build a fresh config AFTER setting env
    from generate_ledger.compose import ComposeConfig

    cfg = ComposeConfig()  # ignore .env for deterministic tests

    # Assert: env wins over defaults
    assert cfg.base_dir == custom
    assert cfg.compose_yml == custom / "docker-compose.yml"


def test_env_overrides_write_target(tmp_path, monkeypatch):
    # Arrange: point GL_BASE_DIR at a custom dir
    custom = tmp_path / "ENV_BASE"
    monkeypatch.setenv("GL_BASE_DIR", str(custom))

    # Act: call the function that creates the config internally
    from generate_ledger.compose import write_compose_file

    out = write_compose_file()  # uses ComposeConfig() inside

    # Assert: it wrote into the env-selected directory
    assert out.parent == custom
    assert out.name == "docker-compose.yml"
    assert out.exists()
