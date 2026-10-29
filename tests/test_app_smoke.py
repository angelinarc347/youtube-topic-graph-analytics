"""Smoke tests: the Streamlit dashboard starts and reacts to its controls without errors."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture()
def app() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=120).run()


def metric_values(app: AppTest) -> dict[str, str]:
    return {m.label: m.value for m in app.metric}


def test_dashboard_starts_without_errors(app):
    assert not app.exception and not app.error
    assert [t.label for t in app.tabs][:6] == [
        "Overview", "Video performance", "Topic network", "Centrality & communities", "Centrality & PageRank",
        "Communities & bridges"]
    values = metric_values(app)
    assert values["Videos"] == "150" and int(values["Communities"]) >= 5


def test_demo_data_is_labelled_synthetic(app):
    assert any("synthetic demo data" in info.value for info in app.info)


def test_threshold_slider_rebuilds_graph(app):
    before = metric_values(app)["Graph edges"]
    app.slider(key="f_threshold").set_value(0.6).run()
    assert not app.exception
    assert metric_values(app)["Graph edges"] != before
    assert any("disconnected" in w.value for w in app.warning)


def test_topic_filter_and_reset(app):
    app.multiselect(key="f_topics").set_value(["Gaming"]).run()
    assert metric_values(app)["Videos"] != "150" and not app.exception
    next(b for b in app.sidebar.button if b.label == "Reset filters").click().run()
    assert metric_values(app)["Videos"] == "150"
    assert app.slider(key="f_threshold").value == pytest.approx(0.25)


def test_filters_with_no_match_show_a_friendly_message(app):
    app.number_input(key="f_min_views").set_value(500_000_000).run()
    assert not app.exception
    assert any("No videos match" in w.value for w in app.warning)


def test_shortest_path_same_video_is_handled(app):
    app.selectbox(key="path_dst").set_value(app.selectbox(key="path_src").value).run()
    assert not app.exception
