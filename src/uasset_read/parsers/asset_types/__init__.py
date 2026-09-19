"""Asset-type semantic handlers (v2).

``registry.run_handlers`` is the only dispatch path; every export not
claimed by a handler lands in the generic tagged-property parse. See
tests/test_handler_capability_ledger.py for the pinned coverage ledger.
"""
