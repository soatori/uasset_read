"""Tests for blueprint semantic JSON domain (#554)."""


class TestBlueprintIds:
    def test_ascii_slug_rules(self):
        from uasset_read.semantic.blueprint.ids import ascii_slug
        assert ascii_slug("EventGraph") == "EventGraph"
        assert ascii_slug("BeginPlay") == "BeginPlay"
        assert ascii_slug("My Var/Name") == "My_Var_Name"
        assert ascii_slug("123abc") == "x123abc"
        assert ascii_slug("") == "unnamed"
        assert ascii_slug("节点") == "unnamed"

    def test_id_builders(self):
        from uasset_read.semantic.blueprint.ids import graph_id, node_id, data_endpoint, exec_endpoint
        assert graph_id("EventGraph") == "blueprint://graph/EventGraph"
        assert node_id("EventGraph", "call", "SetActorLocation", 0) == \
            "blueprint://graph/EventGraph/node/call/SetActorLocation/0"
        assert data_endpoint("NewLocation", "input") == "input.NewLocation"
        assert exec_endpoint("execute") == "exec.in"
        assert exec_endpoint("then") == "exec.out"
        assert exec_endpoint("True") == "exec.true"

    def test_id_regexes_match_builders(self):
        import re
        from uasset_read.semantic.blueprint.ids import (
            GRAPH_ID_RE, NODE_ID_RE, ENDPOINT_RE,
            graph_id, node_id, data_endpoint, exec_endpoint,
        )
        assert re.fullmatch(GRAPH_ID_RE, graph_id("EventGraph"))
        assert re.fullmatch(NODE_ID_RE, node_id("Function_TakeDamage", "variable-set", "Health", 3))
        for ep in (data_endpoint("NewLocation", "input"), exec_endpoint("then")):
            assert re.fullmatch(ENDPOINT_RE, ep)
