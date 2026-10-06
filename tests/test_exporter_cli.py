from pathlib import Path

from momentum_master.exporter.__main__ import parse_channel, prepare_session_path


def test_session_folder_is_created(tmp_path: Path) -> None:
    target = tmp_path / "data" / "momentum_reader"
    assert not target.parent.exists()
    assert prepare_session_path(str(target)) == str(target)
    assert target.parent.is_dir()


def test_parse_channel() -> None:
    assert parse_channel("-1001234567890") == -1001234567890
    assert parse_channel(" @canale ") == "@canale"
