from enum import Enum
from pathlib import Path
from typing import Optional
import typer

from generate_ledger.rippled_cfg import (
    RippledConfigSpec,
    keygen_xrpl,
    keygen_docker,
)

app = typer.Typer(help="Generate rippled.cfg files for validators + a non-validator node.")

class KeygenMode(str, Enum):
    xrpl = "xrpl"
    docker = "docker"

_BUNDLED_TEMPLATE = Path(__file__).parent.parent / "rippled.cfg"

def _pick_keygen(mode: KeygenMode):
    return keygen_xrpl if mode == KeygenMode.xrpl else keygen_docker


def _load_features(features_from: str | None) -> list[str] | None:
    """Resolve --features-from to a list of amendment names.

    Accepts "release", "develop", a path to a JSON file, or None.
    """
    if features_from is None:
        return None
    from generate_ledger.amendments import get_amendments_for_profile
    if features_from in ("release", "develop"):
        amendments = get_amendments_for_profile(profile=features_from)
        return [a.name for a in amendments if a.enabled]
    # Treat as a JSON file path
    path = Path(features_from)
    if not path.is_file():
        raise typer.BadParameter(f"features-from: not a file: {path}")
    amendments = get_amendments_for_profile(profile="custom", source=path)
    return [a.name for a in amendments if a.enabled]


@app.command("write")
def write(
    template_path: Path = typer.Option(
        _BUNDLED_TEMPLATE,
        "--template-path",
        "-t",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to base rippled.cfg template.",
    ),
    base_dir: Path = typer.Option(
        Path("testnet/volumes"),
        "--base-dir",
        "-b",
        envvar="GL_BASE_DIR",
        help="Where node directories will be written (one subdir per node).",
    ),
    validators: int = typer.Option(
        5, "--validators", "-v", min=0, help="Number of validator nodes."
    ),
    validator_name: str = typer.Option(
        "val", "--validator-name", help="Prefix for validator node dirs (val0..)."
    ),
    rippled_name: str = typer.Option(
        "rippled", "--rippled-name", help="Name for the non-validator node dir."
    ),
    peer_port: int = typer.Option(
        51235, "--peer-port", help="Port used in [ips_fixed] entries."
    ),
    reference_fee: int = typer.Option(
        10, "--reference-fee", help="Voting: reference_fee (drops)."
    ),
    account_reserve: int = typer.Option(
        int(0.2 * 1e6), "--account-reserve", help="Voting: account_reserve (drops)."
    ),
    owner_reserve: int = typer.Option(
        int(1.0 * 1e6), "--owner-reserve", help="Voting: owner_reserve (drops)."
    ),
    keygen: KeygenMode = typer.Option(
        KeygenMode.xrpl, "--keygen", case_sensitive=False, help="Key generation backend."
    ),
    features_from: Optional[str] = typer.Option(
        None, "--features-from",
        help="Amendment features source: 'release', 'develop', or path to JSON file.",
    ),
    amendment_majority_time: Optional[str] = typer.Option(
        None, "--amendment-majority-time",
        help="Override amendment majority time (e.g. '2 minutes').",
    ),
):
    """
    Write per-node rippled.cfg files under BASE_DIR/{val0..valN-1,rippled}/rippled.cfg
    """
    features = _load_features(features_from)

    spec = RippledConfigSpec(
        num_validators=validators,
        validator_name=validator_name,
        rippled_name=rippled_name,
        base_dir=base_dir,
        peer_port=peer_port,
        reference_fee=reference_fee,
        account_reserve=account_reserve,
        owner_reserve=owner_reserve,
        template_path=template_path,
        keygen=_pick_keygen(keygen),
        features=features,
        amendment_majority_time=amendment_majority_time,
    )

    try:
        result = spec.write()
    except Exception as e:
        typer.secho(f"ERROR: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    for p in result.paths:
        typer.echo(f"Wrote {p}")
