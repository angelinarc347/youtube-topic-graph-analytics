"""Tests for src/data_loader.py: validation, tag cleaning and derived metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data_loader import (
    MIN_AGE_DAYS,
    DataValidationError,
    compute_derived_metrics,
    has_simulated_traffic,
    load_videos,
    normalize_tags,
    validate_and_clean,
)

REF = pd.Timestamp("2026-10-28")


def test_normalize_tags_lowercases_trims_and_dedupes():
    assert normalize_tags(" AI; Python ;ai;;  Deep   Learning ") == ["ai", "python", "deep learning"]


@pytest.mark.parametrize("value", [None, np.nan, "", "  ;; ; "])
def test_normalize_tags_handles_missing_values(value):
    assert normalize_tags(value) == []


def test_engagement_rate_formula(raw_frame):
    result = validate_and_clean(raw_frame({"views": 1000, "likes": 50, "comments": 10}), REF)
    row = result.data.iloc[0]
    assert row["engagement_rate"] == pytest.approx(6.0)
    assert row["like_rate"] == pytest.approx(5.0)
    assert row["comment_rate"] == pytest.approx(1.0)


def test_zero_views_does_not_divide_by_zero(raw_frame):
    result = validate_and_clean(raw_frame({"views": 0, "likes": 0, "comments": 0}), REF)
    row = result.data.iloc[0]
    assert row["engagement_rate"] == 0.0 and row["like_rate"] == 0.0 and row["comment_rate"] == 0.0
    assert np.isfinite(row["views_per_day"])


def test_views_per_day_uses_reference_date(raw_frame):
    result = validate_and_clean(raw_frame({"published_at": "2026-10-18", "views": 500}), REF)
    row = result.data.iloc[0]
    assert row["age_days"] == 10
    assert row["views_per_day"] == pytest.approx(50.0)


def test_video_published_after_reference_date_uses_minimum_age(raw_frame):
    result = validate_and_clean(raw_frame({"published_at": "2026-10-28", "views": 90}), REF)
    assert result.data.iloc[0]["age_days"] == MIN_AGE_DAYS
    assert result.data.iloc[0]["views_per_day"] == pytest.approx(90.0 / MIN_AGE_DAYS)


def test_compute_derived_metrics_does_not_change_input(raw_frame):
    frame = validate_and_clean(raw_frame(), REF).data
    before = frame.copy()
    compute_derived_metrics(frame, REF)
    pd.testing.assert_frame_equal(frame, before)


def test_missing_required_column_raises(raw_frame):
    frame = raw_frame().drop(columns=["views"])
    with pytest.raises(DataValidationError, match="views"):
        validate_and_clean(frame, REF)


def test_empty_dataset_raises():
    with pytest.raises(DataValidationError, match="empty"):
        validate_and_clean(pd.DataFrame(), REF)


def test_duplicate_video_ids_raise(raw_frame):
    frame = raw_frame({}, {"video_id": "T001"})
    with pytest.raises(DataValidationError, match="Duplicate"):
        validate_and_clean(frame, REF)


def test_blank_title_row_is_removed_with_warning(raw_frame):
    result = validate_and_clean(raw_frame({}, {"title": "   "}), REF)
    assert result.rows_kept == 1 and result.rows_read == 2
    assert any("blank title" in w for w in result.warnings)


@pytest.mark.parametrize(
    "bad_values, expected_text",
    [({"views": -5}, "negative"), ({"likes": "many"}, "non-numeric"),
     ({"published_at": "not-a-date"}, "date"), ({"duration_minutes": None}, "non-numeric")],
)
def test_invalid_rows_are_dropped_with_a_warning(raw_frame, bad_values, expected_text):
    result = validate_and_clean(raw_frame({}, bad_values), REF)
    assert result.rows_kept == 1
    assert any(expected_text in w for w in result.warnings)


def test_all_rows_invalid_raises(raw_frame):
    with pytest.raises(DataValidationError, match="No valid rows"):
        validate_and_clean(raw_frame({"views": -1}), REF)


def test_missing_tags_are_allowed_but_reported(raw_frame):
    result = validate_and_clean(raw_frame({"tags": None}), REF)
    assert result.data.iloc[0]["tags_list"] == []
    assert any("no tags" in w for w in result.warnings)


def test_optional_columns_are_added_when_absent(raw_frame):
    result = validate_and_clean(raw_frame(), REF)
    assert {"description", "video_url"} <= set(result.data.columns)


def test_load_videos_reports_missing_file(tmp_path):
    with pytest.raises(DataValidationError, match="Could not find"):
        load_videos(tmp_path / "does_not_exist.csv")


def test_load_videos_reports_empty_file(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    with pytest.raises(DataValidationError, match="empty"):
        load_videos(empty)


# --- the bundled demo dataset itself -------------------------------------
def test_sample_dataset_size_and_quality(sample_videos):
    assert 100 <= len(sample_videos) <= 200
    assert sample_videos["video_id"].is_unique
    assert (sample_videos[["views", "likes", "comments"]] >= 0).all().all()
    assert sample_videos["published_at"].notna().all()
    assert sample_videos["topic"].nunique() >= 6
    assert np.isfinite(sample_videos[["engagement_rate", "views_per_day"]].to_numpy()).all()


def test_sample_dataset_is_labelled_synthetic(sample_videos):
    assert sample_videos["description"].str.contains("synthetic", case=False).all()
    assert (sample_videos["video_url"] == "").all()  # no pretend links to real YouTube videos
    assert has_simulated_traffic(sample_videos)


def test_simulated_traffic_columns_sum_to_100(sample_videos):
    total = sample_videos[["sim_search_pct", "sim_suggested_pct", "sim_direct_pct", "sim_external_pct"]].sum(axis=1)
    assert np.allclose(total, 100.0, atol=0.11)
