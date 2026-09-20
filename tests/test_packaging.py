import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cpm.constants import APP_NAME, VERSION

ISS = ROOT / 'packaging' / 'slimgma.iss'
INSTALLER_SCRIPT = ROOT / '.github' / 'scripts' / 'build-installer.ps1'
BUILD_WORKFLOW = ROOT / '.github' / 'workflows' / 'build.yml'
RELEASE_WORKFLOW = ROOT / '.github' / 'workflows' / 'release.yml'

BUILD_OUTPUTS = {'LICENSE.txt'}


def iss_text() -> str:
    return ISS.read_text(encoding='utf-8')


def directive(name: str) -> str:
    found = re.search(rf'^{name}=(.+)$', iss_text(), re.M)
    assert found, f"directive {name} absente de slimgma.iss"
    return found.group(1).strip()


def test_the_installer_script_exists():
    assert ISS.is_file()
    assert INSTALLER_SCRIPT.is_file()


def test_the_version_is_never_hardcoded():
    assert '#DAppVersion' not in iss_text()
    assert directive('AppVersion') == '{#AppVersion}'
    assert f'AppVersion={VERSION}' not in iss_text()
    assert 'AppVersion' in INSTALLER_SCRIPT.read_text(encoding='utf-8')
    assert 'from cpm.constants import VERSION' in INSTALLER_SCRIPT.read_text(
        encoding='utf-8')


def test_the_app_id_is_a_fixed_guid():
    app_id = directive('AppId')
    assert re.fullmatch(
        r'\{\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}',
        app_id), app_id


def test_every_referenced_file_exists():
    sources = re.findall(r'^Source: "([^"]+)"', iss_text(), re.M)
    assert sources
    for source in sources:
        if source.startswith('{#PayloadDir}') or source in BUILD_OUTPUTS:
            continue
        assert (ISS.parent / source.replace('\\', '/')).resolve().is_file(), source

    for name in ('SetupIconFile', 'LicenseFile'):
        value = directive(name)
        if value in BUILD_OUTPUTS:
            continue
        assert (ISS.parent / value.replace('\\', '/')).resolve().is_file(), value


def test_the_icon_ships_with_the_app():
    assert (ROOT / 'assets' / 'slimgma.ico').is_file()
    assert (ROOT / 'assets' / 'slimgma.png').is_file()
    for path in (BUILD_WORKFLOW, RELEASE_WORKFLOW, INSTALLER_SCRIPT):
        text = path.read_text(encoding='utf-8')
        assert 'slimgma.ico;assets' in text, path.name


def test_the_installer_is_named_after_the_version():
    assert directive('OutputBaseFilename') == 'Slimgma-Setup-{#AppVersion}'
    for path in (BUILD_WORKFLOW, RELEASE_WORKFLOW):
        assert 'Slimgma-Setup-' in path.read_text(encoding='utf-8'), path.name


def test_the_uninstaller_offers_to_drop_the_settings():
    text = iss_text()
    assert 'CurUninstallStepChanged' in text
    assert 'DropSettings' in text
    assert f'{{userappdata}}\\{APP_NAME}' in text


def test_the_install_needs_no_administrator():
    assert directive('PrivilegesRequired') == 'lowest'
    assert directive('DefaultDirName') == '{autopf}\\{#AppName}'


@pytest.mark.parametrize('language', ['French.isl', 'compiler:Default.isl'])
def test_both_languages_are_offered(language):
    assert language in iss_text()
