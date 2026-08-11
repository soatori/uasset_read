"""Tests for coverage model."""
from uasset_read.semantic.coverage import CoverageModel


class TestCoverageModel:
    def test_full_coverage(self):
        model = CoverageModel()
        model.track(10, 10, [])
        info = model.build()
        assert info.fields_expected == 10
        assert info.fields_parsed == 10
        assert info.coverage_pct == 100.0
        assert info.unparsed_fields == ()

    def test_partial_coverage(self):
        model = CoverageModel()
        model.track(10, 7, ["FieldA", "FieldB", "FieldC"])
        info = model.build()
        assert info.fields_expected == 10
        assert info.fields_parsed == 7
        assert info.coverage_pct == 70.0
        assert info.unparsed_fields == ("FieldA", "FieldB", "FieldC")

    def test_zero_expected(self):
        model = CoverageModel()
        model.track(0, 0, [])
        info = model.build()
        assert info.coverage_pct == 0.0

    def test_multiple_tracks_accumulate(self):
        model = CoverageModel()
        model.track(5, 5, [])
        model.track(5, 3, ["A", "B"])
        info = model.build()
        assert info.fields_expected == 10
        assert info.fields_parsed == 8
        assert info.coverage_pct == 80.0
        assert info.unparsed_fields == ("A", "B")
