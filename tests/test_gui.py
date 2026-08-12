import os
import struct
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

tk = pytest.importorskip('tkinter')

pytestmark = pytest.mark.skipif(
    sys.platform.startswith('linux') and not os.environ.get('DISPLAY'),
    reason="aucun serveur X disponible",
)


def _probe_display():
    try:
        root = tk.Tk()
    except tk.TclError:
        return False
    root.destroy()
    return True


@pytest.fixture(scope='module', autouse=True)
def _require_display():
    if not _probe_display():
        pytest.skip("tkinter ne peut pas ouvrir de fenêtre")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.setenv('APPDATA', str(tmp_path / 'config'))
    import cpm.constants as constants
    import cpm.gui as gui_module
    monkeypatch.setattr(constants, 'CONFIG_PATH',
                        tmp_path / 'config' / 'cpm.json')
    monkeypatch.setattr(gui_module, 'CONFIG_PATH',
                        tmp_path / 'config' / 'cpm.json')
    monkeypatch.setattr(gui_module.messagebox, 'showinfo',
                        lambda *a, **k: None, raising=False)

    instance = gui_module.App()
    instance.root.withdraw()
    yield instance
    try:
        instance._stop_pump()
        instance._stop_timer()
        instance.root.destroy()
    except tk.TclError:
        pass


def settle(app, seconds=0.4):
    end = time.time() + seconds
    while time.time() < end:
        app.root.update()
        time.sleep(0.01)


def make_addon(root: Path) -> Path:
    (root / 'models' / 'player').mkdir(parents=True)
    (root / 'models' / 'player' / 'bob.mdl').write_bytes(b'IDST' + bytes(400))
    materials = root / 'materials' / 'models' / 'bob'
    materials.mkdir(parents=True)
    (materials / 'head.vmt').write_text(
        '"VertexLitGeneric"\n{\n"$basetexture" "models/bob/head"\n}\n')
    header = bytearray(80)
    header[0:4] = b'VTF\x00'
    struct.pack_into('<III', header, 4, 7, 2, 80)
    struct.pack_into('<HH', header, 16, 64, 64)
    struct.pack_into('<H', header, 24, 1)
    struct.pack_into('<i', header, 52, 13)
    header[56] = 1
    struct.pack_into('<i', header, 57, -1)
    (materials / 'head.vtf').write_bytes(bytes(header) + bytes(64))
    (root / 'lisezmoi.txt').write_text('doc')
    return root


def test_app_builds_every_page(app):
    settle(app, 0.2)
    assert set(app.pages) == {'source', 'options', 'advanced', 'log', 'report'}
    for page in app.pages:
        app._show_page(page)
        settle(app, 0.05)
        assert app._page == page


def test_theme_and_language_toggle_preserve_state(app):
    app._log("  ⚠ attention")
    settle(app)
    assert app._counts['warning'] == 1

    app._toggle_theme()
    settle(app, 0.2)
    assert app.theme_name == 'light'
    assert app._counts['warning'] == 1

    app._toggle_language()
    settle(app, 0.2)
    assert app.lang == 'en'
    assert set(app.pages) == {'source', 'options', 'advanced', 'log', 'report'}


def test_library_line_is_not_an_error(app):
    settle(app, 0.2)
    assert app._counts == {'warning': 0, 'error': 0}


def test_profile_applies_preset(app):
    app.profile_var.set(app._profile_label('minimal'))
    app._apply_profile()
    settle(app, 0.1)
    assert app.tex_qual.get() == 60
    assert app.max_res.get() == '512'


def test_compression_completes_and_fills_report(app, tmp_path):
    source = make_addon(tmp_path / 'addon')
    app.source_var.set(str(source))
    app.output_var.set(str(tmp_path / 'out'))
    settle(app, 0.1)

    app._start()
    deadline = time.time() + 60
    while app._thread.is_alive() and time.time() < deadline:
        app.root.update()
        time.sleep(0.02)
    settle(app, 1.0)

    assert not app._thread.is_alive()
    compressor = app._compressor
    assert compressor.final_size is not None
    assert app._steps_done
    assert str(app.open_btn['state']) == 'normal'
    assert str(app.report_btn['state']) == 'normal'
    assert app._report_data == compressor.report
    assert app._report_text().strip()
    assert not list((tmp_path / 'out').rglob('*.html'))


def test_batch_run_reports_success(app, tmp_path):
    root = tmp_path / 'batch'
    for name in ('a', 'b'):
        make_addon(root / name)
    app.source_var.set(str(root))
    app.output_var.set(str(tmp_path / 'batch_out'))
    app.batch.set(True)
    settle(app, 0.1)

    app._start()
    deadline = time.time() + 90
    while app._thread.is_alive() and time.time() < deadline:
        app.root.update()
        time.sleep(0.02)
    settle(app, 1.0)

    compressor = app._compressor
    assert compressor.final_size is not None
    assert app.status_dot_lbl.cget('fg') == app.GREEN
    assert str(app.open_btn['state']) == 'normal'
    assert len(compressor.report['batch']) == 2


def test_delta_label_signs(app):
    assert app._delta_label(12.5) == '-12.5%'
    assert app._delta_label(-3.0) == '+3.0%'
    assert app._delta_label(None) == '—'


def test_changelog_marks_versions_as_seen(app):
    from cpm.constants import VERSION
    app._seen_version = '0.0.1'
    app._paint_changelog_button()
    assert app.changelog_btn.cget('text').endswith('•')

    app._show_changelog()
    settle(app, 0.3)
    assert app._seen_version == VERSION
    assert not app.changelog_btn.cget('text').endswith('•')
