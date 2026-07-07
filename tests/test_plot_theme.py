from bokeh.themes import Theme

from qcm.viz import plot_theme


def test_theme_is_bokeh_theme():
    assert isinstance(plot_theme.QCM_BOKEH_THEME, Theme)


def test_apply_is_idempotent_and_callable():
    # Should not raise when called more than once.
    plot_theme.apply()
    plot_theme.apply()
