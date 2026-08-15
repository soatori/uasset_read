
class TestBlueprintDefaults:
    def test_scalar_and_object_defaults(self):
        from uasset_read.semantic.blueprint.defaults import default_value_for
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        class Pin:
            def __init__(self, **kw):
                self.pin_category = kw.get("pin_category", "")
                self.default_value = kw.get("default_value", "")
                self.default_object_name = kw.get("default_object_name", None)
                self.default_text_value = kw.get("default_text_value", None)
                self.linked_to = []

        rep = BlueprintReporting()
        assert default_value_for(Pin(pin_category="bool", default_value="true"), rep) is True
        assert default_value_for(Pin(pin_category="int", default_value="0"), rep) == 0
        assert default_value_for(Pin(pin_category="real", default_value="1.5"), rep) == 1.5
        assert default_value_for(Pin(pin_category="string", default_value=""), rep) == ""
        assert default_value_for(Pin(pin_category="object", default_object_name="/Game/X"), rep) == {"object": "/Game/X"}
        assert default_value_for(Pin(pin_category="text", default_text_value="Hello"), rep) == {"text": {"raw": "Hello"}}
        connected = Pin(pin_category="int", default_value="5")
        connected.linked_to = ["aa" * 16]
        assert default_value_for(connected, rep) is None
