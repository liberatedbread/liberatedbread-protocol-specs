"""Independent ELK-BLEDOM effect and microphone frame transcriptions."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs/devices/elk-bledom-led-strip.yaml").read_text(
        encoding="utf-8"
    )
)


def render(command, **values):
    parameters = command.get("parameters", {})
    resolved = {
        name: values.get(name, definition.get("default"))
        for name, definition in parameters.items()
    }
    output = bytearray()
    for item in command["template"]:
        if isinstance(item, int):
            output.append(item)
        else:
            output.append(resolved[item.strip("{}")])
    return bytes(output)


def commands():
    return SPEC["services"][0]["characteristics"][0]["commands"]


def test_effect_mode_80_matches_audit_vector():
    command = commands()["set_mode"]
    assert render(command, mode=0x80) == bytes.fromhex(
        "7e 00 03 80 03 ff ff 00 ef"
    )
    assert command["parameters"]["mode"]["min"] == 0x80
    assert command["parameters"]["mode"]["max"] == 0x9C
    assert command["verification"] == "reported"


def test_microphone_effect_is_fixed_nine_byte_frame_without_sequence():
    command = commands()["set_mic_effect"]
    assert len(command["template"]) == 9
    assert "seq" not in command["parameters"]
    assert render(command, effect=0x80) == bytes.fromhex(
        "7e 05 03 80 04 ff ff 00 ef"
    )
    assert command["verification"] == "reported"


def test_light_entity_binds_the_corrected_effect_command():
    entity = SPEC["entities"][0]
    assert entity["commands"]["set_effect"] == "set_mode"
