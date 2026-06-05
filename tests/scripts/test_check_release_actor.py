import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "release"))

from check_release_actor import is_actor_authorized, resolve_allowed_actors, split_actors


def test_split_actors_handles_commas_and_whitespace():
    assert split_actors("alice, bob\n charlie") == ("alice", "bob", "charlie")
    assert split_actors("") == ()
    assert split_actors(None) == ()


def test_resolve_allowed_actors_prefers_explicit_list():
    assert resolve_allowed_actors("alice,bob", "the-org") == ("alice", "bob")


def test_resolve_allowed_actors_falls_back_to_owner():
    assert resolve_allowed_actors("", "the-org") == ("the-org",)
    assert resolve_allowed_actors(None, None) == ()


def test_is_actor_authorized_is_case_insensitive():
    allowed = ("Alice", "Bob")
    assert is_actor_authorized("alice", allowed) is True
    assert is_actor_authorized("BOB", allowed) is True
    assert is_actor_authorized("mallory", allowed) is False


def test_is_actor_authorized_empty_allowlist_denies():
    assert is_actor_authorized("alice", ()) is False
