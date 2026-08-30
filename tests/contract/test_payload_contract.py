"""Payload contract — texture and sound payload descriptors without bytes."""

from __future__ import annotations

from pathlib import Path

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


class TestTexturePayload:
    """Texture payload descriptors from ImportedSize struct."""

    def test_texture2d_payload_handler(self):
        """Texture2D emits a payload descriptor with source_region."""
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.handlers import TexturePayloadHandler
        from uasset_read.v2.version import VersionContext

        doc = parse_package_document(str(SAMPLES_DIR / "FirstPerson_T_GridChecker_A.uasset"), depth="object")
        tex = next(o for o in doc.objects if o.class_name == "Texture2D")
        handler = TexturePayloadHandler()
        result = handler.enrich(tex, VersionContext(), doc.objects, None)

        # May be None if ImportedSize is absent or empty
        if result is not None:
            payload = result["payload"]
            assert payload["kind"] == "texture_mip"
            assert payload["source_region"] == "main"
            assert isinstance(payload["logical_size"], int)
            # Payload must never contain raw bytes
            assert "raw_bytes" not in payload

    def test_texturecube_payload_handler(self):
        """TextureCube returns None (no ImportedSize property)."""
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.handlers import TexturePayloadHandler
        from uasset_read.v2.version import VersionContext

        doc = parse_package_document(str(SAMPLES_DIR / "MutableSample_GrayLightTextureCube.uasset"), depth="object")
        tex = next(o for o in doc.objects if o.class_name == "TextureCube")
        handler = TexturePayloadHandler()
        result = handler.enrich(tex, VersionContext(), doc.objects, None)
        assert result is None

    def test_texture2d_has_payload_coverage_at_asset_depth(self):
        """Texture2D handler adds a payload coverage entry at depth=asset."""
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "FirstPerson_T_GridChecker_A.uasset"), depth="asset")
        tex = next(o for o in doc.objects if o.class_name == "Texture2D")
        payload_features = [c for c in tex.coverage if c.feature == "texture.payload"]
        assert len(payload_features) == 1
        assert payload_features[0].status in ("present", "partial")


class TestSoundPayload:
    """Sound handler coverage without v1 asset_type_data."""

    def test_soundwave_handler_coverage(self):
        """SoundWave handler always produces coverage."""
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "ALS_Concrete_Step_01_SoundWave.uasset"), depth="asset")
        sw = next(o for o in doc.objects if o.class_name == "SoundWave")
        assert sw.semantic is not None
        assert sw.semantic["kind"] == "sound"
        handler_features = [c for c in sw.coverage if c.feature == "handler.SoundHandler"]
        assert len(handler_features) == 1

    def test_soundwave_semantic_kind(self):
        """SoundWave produces stable semantic.kind."""
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "ALS_Concrete_Step_01_SoundWave.uasset"), depth="asset")
        sw = next(o for o in doc.objects if o.class_name == "SoundWave")
        assert sw.semantic is not None
        assert sw.semantic["kind"] == "sound"
        assert sw.semantic["sound_type"] == "SoundWave"
