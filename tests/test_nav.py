from qcm.viz import nav


def test_steps_are_five_in_order():
    assert [s.id for s in nav.STEPS] == ["review", "reference", "phases", "quantify", "report"]


def test_clamp_step_bounds():
    assert nav.clamp_step(-3) == 0
    assert nav.clamp_step(99) == 4
    assert nav.clamp_step(2) == 2


def test_step_id_from_index():
    assert nav.step_id(0) == "review"
    assert nav.step_id(4) == "report"
    assert nav.step_id(50) == "report"


def test_next_prev_clamp_at_ends():
    assert nav.next_step(0) == 1
    assert nav.next_step(4) == 4
    assert nav.prev_step(0) == 0
    assert nav.prev_step(3) == 2


def test_brush_target_follows_step():
    assert nav.brush_target_for_step("review") == "current"
    assert nav.brush_target_for_step("reference") == "reference"
    assert nav.brush_target_for_step("phases") == "mark"
    assert nav.brush_target_for_step("quantify") == "current"
    assert nav.brush_target_for_step("report") == "current"
    assert nav.brush_target_for_step("unknown") == "current"


def test_reference_hint_only_when_referenced_and_unset():
    # Referenced quantity with reference == full run -> hint.
    assert nav.needs_reference_hint(True, (0.0, 100.0), 100.0) is True
    # Referenced quantity with a real sub-window -> no hint.
    assert nav.needs_reference_hint(True, (0.0, 20.0), 100.0) is False
    # Absolute quantity -> never hint.
    assert nav.needs_reference_hint(False, (0.0, 100.0), 100.0) is False
    # Compares against span_s, not a hardcoded value: full-span at a different span.
    assert nav.needs_reference_hint(True, (0.0, 200.0), 200.0) is True
    assert nav.needs_reference_hint(True, (0.0, 100.0), 200.0) is False
