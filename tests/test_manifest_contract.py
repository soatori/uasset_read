"""Manifest contract — all 48 tracked samples exist with correct hash and size."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

SAMPLES_DIR = Path(__file__).parent / "samples"
MANIFEST_PATH = SAMPLES_DIR / "manifest.json"


@pytest.fixture(scope="module")
def manifest():
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class TestManifestIntegrity:
    def test_manifest_loads(self, manifest):
        assert manifest["version"] == 1
        assert len(manifest["samples"]) == 48

    def test_all_samples_exist(self, manifest):
        missing = []
        for s in manifest["samples"]:
            path = SAMPLES_DIR / s["name"]
            if not path.exists():
                missing.append(s["name"])
        assert not missing, f"Missing samples: {missing}"

    def test_sha256_matches(self, manifest):
        mismatches = []
        for s in manifest["samples"]:
            path = SAMPLES_DIR / s["name"]
            actual = _sha256(path)
            if actual != s["sha256"]:
                mismatches.append(f"{s['name']}: expected {s['sha256'][:16]}... got {actual[:16]}...")
        assert not mismatches, "Hash mismatches:\n" + "\n".join(mismatches)

    def test_size_matches(self, manifest):
        mismatches = []
        for s in manifest["samples"]:
            path = SAMPLES_DIR / s["name"]
            actual = path.stat().st_size
            if actual != s["size_bytes"]:
                mismatches.append(f"{s['name']}: expected {s['size_bytes']} got {actual}")
        assert not mismatches, "Size mismatches:\n" + "\n".join(mismatches)

    def test_no_extra_files(self, manifest):
        expected = {s["name"] for s in manifest["samples"]}
        expected.add("manifest.json")
        expected.add("README.md")
        expected.add("ORIGIN-issue-516-plugin-mount.md")
        expected.add("ORIGIN-issue-521-niagara.md")
        expected.add("ORIGIN-issue-522-cube-builder.md")
        actual = {f.name for f in SAMPLES_DIR.iterdir()}
        extra = actual - expected
        assert not extra, f"Unexpected files in samples/: {extra}"

    def test_zero_asset_role_fixture_is_manifested(self, manifest):
        entry = next(item for item in manifest["samples"] if item["name"] == "uasset_rs_UE410_SimpleRefsSoftRef.uasset")
        assert entry["size_bytes"] == 4037
        assert entry["engine_layout"] == "legacy"
        assert entry["export_count"] == 6
        assert entry["b_is_asset_count"] == 0

    @pytest.mark.parametrize(
        "sample_name",
        [s["name"] for s in json.load(open(MANIFEST_PATH))["samples"]],
    )
    def test_sample_parseable(self, sample_name):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / sample_name))
        assert doc.summary.total_exports > 0, f"{sample_name}: no exports"
        assert len(doc.objects) > 0, f"{sample_name}: no objects"
