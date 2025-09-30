from generate_ledger.ledger import LedgerConfig, write_ledger_file, gen_ledger_state
from pathlib import Path
from gl.amendments import get_amendments


def test_read_amendments_from_default_file(amendments):
    cfg = LedgerConfig()
    am_s = cfg.amendment_source
    a = get_amendments()
    pass


def test_read_amendments_from_network():
    pass

def test_generate_ledger_accounts_data():
    cfg = LedgerConfig()
    ledger_state_data = gen_ledger_state(config=cfg)
    lsd_keys = ['accepted', 'accountState', 'closed', 'close_time_resolution', 'ledger_index', 'seqNum', 'totalCoins', 'total_coins']
    assert all(k in lsd_keys for k in list(ledger_state_data["ledger"].keys())), "yp"

def test_write_ledger_file(tmp_path):
    cfg = LedgerConfig()
    output_file = tmp_path / "ledger.json"
    written = write_ledger_file(output_file=output_file, config=cfg)
    assert written.exists()

def test_write_ledger_file_uses_ledger_config_by_default(tmp_path):
    written = write_ledger_file()
    assert written.exists()

def test_write_ledger_file_anywhere(tmp_path):
    cfg = LedgerConfig()
    output_file = tmp_path / "some_random_dir/my_ledger.json"
    written = write_ledger_file(output_file=output_file, config=cfg)
    assert written.exists()
    assert written.parent.name == output_file.parent.name

def test_env_overrides_config_base_dir(tmp_path, monkeypatch):
    # Arrange: point GL_BASE_DIR at a custom dir
    custom = tmp_path / "ENV_BASE"
    monkeypatch.setenv("GL_BASE_DIR", str(custom))

    # Act: build a fresh config AFTER setting env
    from generate_ledger.ledger import LedgerConfig
    cfg = LedgerConfig()  # ignore .env for deterministic tests

    # Assert: env wins over defaults
    assert cfg.base_dir == custom
    assert cfg.ledger_json == custom / "ledger.json"

def test_env_overrides_write_target(tmp_path, monkeypatch):
    # Arrange: point GL_BASE_DIR at a custom dir
    custom = tmp_path / "ENV_BASE"
    monkeypatch.setenv("GL_BASE_DIR", str(custom))

    # Act: call the function that creates the config internally
    from generate_ledger.ledger import write_ledger_file
    out = write_ledger_file()  # uses LedgerConfig() inside

    # Assert: it wrote into the env-selected directory
    assert out.parent == custom
    assert out.name == "ledger.json"
    assert out.exists()
