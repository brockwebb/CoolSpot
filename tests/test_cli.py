import pytest
from pipeline import cli


def test_no_args_prints_usage_and_fails(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main([])
    assert e.value.code == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_unknown_command_fails():
    with pytest.raises(SystemExit):
        cli.main(["frobnicate"])


def test_list_commands_registered():
    for cmd in ("acquire-census", "acquire-hospitals", "acquire-cooling", "geocode", "publish", "all"):
        assert cmd in cli.COMMANDS
