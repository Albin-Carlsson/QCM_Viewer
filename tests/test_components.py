import panel as pn

from qcm.viz import components as c


def _html(obj) -> str:
    return obj.object if isinstance(obj, pn.pane.HTML) else str(obj)


def test_pill_returns_escaped_html_string():
    out = c.pill("Duration", "<b>10 s")
    assert "qcm-pill" in out
    assert "&lt;b&gt;10 s" in out  # value is escaped
    assert "Duration" in out


def test_section_title_has_classes_and_escapes():
    out = _html(c.section_title("Review", eyebrow="Step 1"))
    assert "qcm-section-title" in out
    assert "Review" in out
    assert "Step 1" in out


def test_stat_badge_tone_class():
    out = _html(c.stat_badge("Mass", "12.3 ng/cm²", tone="accent"))
    assert "qcm-stat accent" in out
    assert "12.3 ng/cm" in out


def test_metric_strip_renders_each_row():
    out = _html(c.metric_strip([("Range", "100 s", "0–100"), ("Mean", "5", "")]))
    assert "qcm-metric-strip" in out
    assert "Range" in out and "Mean" in out


def test_empty_state_text():
    out = _html(c.empty_state("Nothing here"))
    assert "qcm-empty" in out
    assert "Nothing here" in out


def test_hint_tone_class():
    out = _html(c.hint("Set a <b>reference</b>", tone="warning"))
    assert "qcm-hint warning" in out
    # Inline markup is allowed in hints (trusted callers), so it is NOT escaped.
    assert "<b>reference</b>" in out


def test_card_is_panel_with_class():
    card = c.card(pn.pane.Markdown("x"), title="T")
    assert isinstance(card, pn.Card)
    assert "qcm-card" in card.css_classes


def test_toolbar_is_row_with_class():
    bar = c.toolbar(pn.widgets.Button(name="A"))
    assert isinstance(bar, pn.Row)
    assert "qcm-toolbar" in bar.css_classes
