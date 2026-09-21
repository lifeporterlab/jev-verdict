"""Key resolution tests: exactly three sources, nothing else.

These tests never name a foreign application or a foreign path: instead they
assert the candidate set itself, which is what makes the guarantee checkable.
"""

from pathlib import Path

import pytest

from jev_verdict.client import JevError, TypeSafeClient, key_source_candidates, load_api_key

TOOL_CONFIG = Path(".config") / "jev-verdict"


@pytest.fixture()
def isolated_home(tmp_path, monkeypatch):
    """Point the user home at a temporary directory on every platform."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOMEDRIVE", home.drive or "C:")
    monkeypatch.setenv("HOMEPATH", str(home)[len(home.drive):] or "\\")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    return home


def test_candidates_are_exactly_the_documented_sources(tmp_path, monkeypatch, isolated_home):
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    assert key_source_candidates() == [workdir / ".env", isolated_home / TOOL_CONFIG / ".env"]

    explicit = tmp_path / "explicit.env"
    assert key_source_candidates(explicit) == [
        explicit,
        workdir / ".env",
        isolated_home / TOOL_CONFIG / ".env",
    ]


def test_environment_variable_wins_over_every_file(tmp_path, monkeypatch, isolated_home):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("TYPESAFE_API_KEY=from-cwd-file\n", encoding="utf-8")
    monkeypatch.setenv("TYPESAFE_API_KEY", "from-environment")
    assert load_api_key() == "from-environment"


def test_explicit_env_file_is_read_instead_of_cwd(tmp_path, monkeypatch, isolated_home):
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    (workdir / ".env").write_text("TYPESAFE_API_KEY=from-cwd-file\n", encoding="utf-8")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "keys.env").write_text("# comment\nTYPESAFE_API_KEY = \"from-explicit-file\"\n", encoding="utf-8")

    assert load_api_key(outside / "keys.env") == "from-explicit-file"
    # Without the explicit file, resolution still only sees the cwd file.
    assert load_api_key() == "from-cwd-file"
    assert load_api_key(tmp_path / "missing.env") == "from-cwd-file"


def test_no_parent_directory_or_foreign_file_ever_supplies_a_key(tmp_path, monkeypatch, isolated_home):
    decoys = [
        isolated_home / ".env",
        isolated_home / "some-other-app" / ".env",
        isolated_home / "some-other-app" / "state" / ".env",
        tmp_path / ".env",
    ]
    for decoy in decoys:
        decoy.parent.mkdir(parents=True, exist_ok=True)
        decoy.write_text("TYPESAFE_API_KEY=decoy\n", encoding="utf-8")

    workdir = tmp_path / "nested" / "deep"
    workdir.mkdir(parents=True)
    monkeypatch.chdir(workdir)

    candidates = set(key_source_candidates())
    assert candidates.isdisjoint(Path(decoy).resolve() for decoy in decoys)
    assert load_api_key() == ""


def test_tool_own_config_path_is_used_last(tmp_path, monkeypatch, isolated_home):
    monkeypatch.chdir(tmp_path)
    config_dir = isolated_home / TOOL_CONFIG
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text("TYPESAFE_API_KEY=tool-config-key\n", encoding="utf-8")
    assert load_api_key() == "tool-config-key"


def test_only_typesafe_key_is_honoured_and_other_keys_are_ignored(tmp_path, monkeypatch, isolated_home):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("SOME_OTHER_KEY=nope\nnot-a-pair\n", encoding="utf-8")
    assert load_api_key() == ""
    (tmp_path / ".env").write_text("SOME_OTHER_KEY=nope\nTYPESAFE_API_KEY=right\n", encoding="utf-8")
    assert load_api_key() == "right"


def test_missing_key_reports_nothing_about_searched_locations(tmp_path, monkeypatch, isolated_home, capsys):
    monkeypatch.chdir(tmp_path)
    assert load_api_key() == ""
    assert capsys.readouterr() == ("", "")


def test_client_rejects_attempts_below_one():
    with pytest.raises(JevError):
        TypeSafeClient(api_key="dummy", attempts=0)


def test_client_uses_env_file_argument(tmp_path, monkeypatch, isolated_home):
    monkeypatch.chdir(tmp_path)
    key_file = tmp_path / "keys.env"
    key_file.write_text("TYPESAFE_API_KEY=client-env-file\n", encoding="utf-8")
    client = TypeSafeClient(env_file=key_file)
    assert client.api_key == "client-env-file"
    assert client.attempts == 3
