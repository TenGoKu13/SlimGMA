import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import slimgma
from cpm.cli import cli_main


def test_leaves_working_streams_alone(monkeypatch):
    before_out, before_err = sys.stdout, sys.stderr

    slimgma.attach_console()

    assert sys.stdout is before_out
    assert sys.stderr is before_err


def test_replaces_missing_streams(monkeypatch):
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)

    slimgma.attach_console()

    assert sys.stdout is not None
    assert sys.stderr is not None
    sys.stdout.write('essai')
    sys.stderr.write('essai')


def test_print_survives_missing_streams(monkeypatch):
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)

    slimgma.attach_console()
    print("rien ne doit exploser")


def test_help_does_not_crash_without_a_console(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['Slimgma.exe', '--help'])
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)

    slimgma.attach_console()

    with pytest.raises(SystemExit) as exit_info:
        cli_main()

    assert exit_info.value.code == 0


def test_help_reaches_the_reopened_stream(monkeypatch):
    captured = io.StringIO()
    monkeypatch.setattr(slimgma, '_open_console_stream', lambda: captured)
    monkeypatch.setattr(sys, 'argv', ['Slimgma.exe', '--help'])
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)

    slimgma.attach_console()

    with pytest.raises(SystemExit):
        cli_main()

    assert '--in-place' in captured.getvalue()


def test_swallowed_output_without_the_fallback(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['Slimgma.exe', '--help'])
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)

    with pytest.raises(SystemExit) as exit_info:
        cli_main()

    assert exit_info.value.code == 0
