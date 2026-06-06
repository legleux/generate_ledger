"""Smoke test for the documented quickstart default network boot."""

import subprocess
import uuid

import pytest

from tests.smoke._helpers import KEEP_NETWORK

pytestmark = pytest.mark.smoke


def test_quickstart_default_val0_loads_ledger(tmp_path):
    """Bare ``gen`` output should at least boot val0 with its generated ledger."""
    output_dir = tmp_path / "quickstart"
    compose_project = f"quickstart_boot_{uuid.uuid4().hex[:8]}"
    compose_file = output_dir / "docker-compose.yml"
    compose_cmd = ["docker", "compose", "-f", str(compose_file), "-p", compose_project]

    subprocess.run(["uv", "run", "gen", "--output-dir", str(output_dir)], check=True, timeout=60)

    assert (output_dir / "ledger.json").exists()
    assert compose_file.exists()

    try:
        result = subprocess.run(
            [*compose_cmd, "up", "-d", "--wait", "--wait-timeout", "45", "val0"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if result.returncode != 0:
            logs = subprocess.run(
                [*compose_cmd, "logs", "--tail=40", "val0"], capture_output=True, text=True, check=False
            )
            pytest.fail(
                f"val0 did not become healthy from the generated quickstart compose file.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}\n"
                f"logs:\n{logs.stdout}\n{logs.stderr}"
            )
    finally:
        if KEEP_NETWORK:
            print("\nSMOKE_KEEP_NETWORK=1: leaving quickstart compose project running.")
            print(f"To tear down: docker compose -f {compose_file} -p {compose_project} down -v")
        else:
            subprocess.run([*compose_cmd, "down", "-v"], check=False, timeout=20)
