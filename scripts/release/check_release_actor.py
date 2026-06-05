"""Authorize release workflow actors from a repository allowlist."""

from __future__ import annotations

import argparse
import os
import re
import sys


def split_actors(raw_actors: str | None) -> tuple[str, ...]:
    if not raw_actors:
        return ()
    return tuple(actor for actor in (part.strip() for part in re.split(r"[\s,]+", raw_actors)) if actor)


def resolve_allowed_actors(raw_actors: str | None, repository_owner: str | None) -> tuple[str, ...]:
    actors = split_actors(raw_actors)
    if actors:
        return actors
    if repository_owner:
        return (repository_owner,)
    return ()


def is_actor_authorized(actor: str, allowed_actors: tuple[str, ...]) -> bool:
    normalized_actor = actor.casefold()
    return any(normalized_actor == allowed.casefold() for allowed in allowed_actors)


def _write_github_output(authorized: bool, allowed_actors: tuple[str, ...]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"authorized={'true' if authorized else 'false'}\n")
        handle.write(f"allowed_actors={','.join(allowed_actors)}\n")


def _write_step_summary(actor: str, authorized: bool, allowed_actors: tuple[str, ...]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    status = "authorized" if authorized else "blocked"
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("## Release authorization\n\n")
        handle.write(f"- Actor: `{actor}`\n")
        handle.write(f"- Status: `{status}`\n")
        handle.write(f"- Allowlist: `{', '.join(allowed_actors)}`\n\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor", default=os.environ.get("GITHUB_ACTOR"), help="GitHub actor to authorize")
    parser.add_argument(
        "--allowed",
        default=os.environ.get("RELEASE_ACTORS") or os.environ.get("AUTHORIZED_RELEASE_ACTORS"),
        help="Comma or whitespace separated authorized release actors",
    )
    parser.add_argument(
        "--repository-owner",
        default=os.environ.get("GITHUB_REPOSITORY_OWNER"),
        help="Fallback owner used when no allowlist is configured",
    )
    args = parser.parse_args(argv)

    if not args.actor:
        print("::error::GITHUB_ACTOR is required to authorize a release.", file=sys.stderr)
        return 2

    allowed_actors = resolve_allowed_actors(args.allowed, args.repository_owner)
    authorized = is_actor_authorized(args.actor, allowed_actors)
    _write_github_output(authorized, allowed_actors)
    _write_step_summary(args.actor, authorized, allowed_actors)

    if not authorized:
        allowlist = ", ".join(allowed_actors) if allowed_actors else "<empty>"
        print(
            f"::error::{args.actor!r} is not authorized to publish releases. "
            f"Set the RELEASE_ACTORS repository variable to one or more GitHub users. "
            f"Current allowlist: {allowlist}",
            file=sys.stderr,
        )
        return 1

    print(f"{args.actor} is authorized to publish releases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
