from qcm.viz.design import APP_CSS


def test_single_root_token_block():
    assert APP_CSS.count(":root") == 1


def test_no_appended_css_war():
    assert "Single-screen compaction" not in APP_CSS
    assert "Iteration:" not in APP_CSS


def test_triad_regions_not_hidden():
    for region in (".qcm-context-bar { display: none",
                   ".qcm-context-bar{display:none",
                   ".qcm-footer { display: none"):
        assert region not in APP_CSS
