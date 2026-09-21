"""Single-owner domain dispatch (plan Task 5)."""

from uasset_read.parsers.asset_types import handlers_impl, registry
from uasset_read.parsers.asset_types.registry import get_handlers, run_handlers


def test_registry_has_one_owner():
    assert get_handlers()
    assert not hasattr(handlers_impl, "_HANDLERS")
    assert not hasattr(handlers_impl, "run_handlers")


def test_unknown_handler_is_not_applicable_not_failed(unknown_object_record, package_context):
    result = run_handlers(unknown_object_record, "decode", [], package_context)
    assert result.status == "not_requested"
    assert result.reason == "no_domain_decoder"


def test_one_handler_failure_records_diagnostic_and_continues(
    unknown_object_record, package_context, monkeypatch
):
    class Failing:
        def supports(self, obj, depth):
            return True

        def enrich(self, obj, depth, all_objects, context):
            raise ValueError("boom")

    class Succeeding:
        capability = "decoded"

        def supports(self, obj, depth):
            return True

        def enrich(self, obj, depth, all_objects, context):
            return {"succeeded": True}

    monkeypatch.setattr(registry, "_HANDLERS", [Failing(), Succeeding()])
    result = run_handlers(unknown_object_record, "decode", [], package_context)
    assert any(d.code == "HANDLER_FAILURE" for d in result.diagnostics)
    assert result.semantic == {"succeeded": True}
    assert result.status == "partial"
