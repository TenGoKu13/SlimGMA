import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cpm.changelog import RELEASES, NEW, FIX, CHANGE, releases_since
from cpm.constants import VERSION


def keys():
    return [tuple(int(p) for p in r['version'].split('.')) for r in RELEASES]


def test_current_version_is_documented():
    assert VERSION in [r['version'] for r in RELEASES]


def test_releases_sorted_newest_first():
    assert keys() == sorted(keys(), reverse=True)


def test_versions_are_unique():
    versions = [r['version'] for r in RELEASES]
    assert len(versions) == len(set(versions))


def test_entries_are_translated_and_typed():
    for release in RELEASES:
        assert release['entries']
        for kind, text in release['entries']:
            assert kind in (NEW, FIX, CHANGE)
            assert text['fr'].strip()
            assert text['en'].strip()


def test_releases_since():
    assert [r['version'] for r in releases_since('1.1.0')] == ['1.2.0']
    assert releases_since('1.2.0') == []
    assert releases_since(VERSION) == []
    assert len(releases_since('0.0.0')) == len(RELEASES)


def test_releases_since_tolerates_unusable_values():
    assert releases_since(None) == []
    assert releases_since('') == []
    assert releases_since('nawak') == RELEASES
