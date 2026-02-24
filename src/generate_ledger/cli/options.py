# src/generate_ledger/cli/options.py
import typer
from pathlib import Path
from typing import Optional

def opt_output():
    return typer.Option(None, "--output-file", "-o", help="Write to this path.")

def opt_validators():
    return typer.Option(None, "--validators", "-v", envvar="GL_VALIDATORS")

def opt_validator_image():
    return typer.Option(None, "--validator-image", envvar="GL_VALIDATOR_IMAGE")

def opt_validator_name():
    return typer.Option(None, "--validator-name", envvar="GL_VALIDATOR_NAME")

def opt_validator_version():
    return typer.Option(None, "--validator-version", envvar="GL_VALIDATOR_VERSION")

def opt_hubs():
    return typer.Option(None, "--hubs", envvar="GL_HUBS")
