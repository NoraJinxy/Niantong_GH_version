import numpy as np
import pytest

from app.engine.group import compare


def test_parse_cluster_channels_accepts_comma_string_case_insensitive():
    channels = ["Fp1", "Pz", "Oz"]

    assert compare._parse_cluster_channels("fp1, PZ", channels) == ["Fp1", "Pz"]


def test_paired_identity_mismatch_raises_when_subjects_are_available():
    a = {"unit_subjects": ["sub-001", "sub-002"]}
    b = {"unit_subjects": ["sub-002", "sub-001"]}

    with pytest.raises(ValueError, match="unit_subjects"):
        compare._validate_paired_identity(a, b)


def test_single_sensor_cluster_records_channel_first_masks(monkeypatch):
    def fake_cluster(A, B, **kwargs):
        assert A.shape == (3, 5)
        mask_stat = np.zeros(5)
        return mask_stat, [(np.array([1, 2]),)], np.array([0.01])

    monkeypatch.setattr(compare, "_run_mne_cluster", fake_cluster)
    A = np.zeros((3, 2, 5))
    B = np.zeros((3, 2, 5))

    result = compare._run_single_sensor_cluster(
        A,
        B,
        ["Fz", "Pz"],
        np.linspace(0, 0.4, 5),
        None,
        "evoked",
        "paired",
        "two-sided",
        0.05,
        32,
        "",
    )

    assert len(result["masks"]) == 2
    assert result["masks"][0].shape == (2, 5)
    assert result["summary"][0]["channels"] == ["Fz"]
    assert result["summary"][0]["tmin"] == pytest.approx(0.1)
    assert result["summary"][0]["tmax"] == pytest.approx(0.2)


def _unit_stack(condition: str, offset: float) -> dict:
    data = np.arange(3 * 2 * 5, dtype=float).reshape(3, 2, 5) + offset
    return {
        "data_type": "unit_stack",
        "base_type": "evoked",
        "data": data,
        "ch_names": ["Fz", "Pz"],
        "ch_types": ["eeg", "eeg"],
        "times": np.linspace(0.0, 0.4, 5),
        "freqs": None,
        "sfreq": 250.0,
        "condition": condition,
        "label": condition,
        "group_label": condition,
        "unit_labels": [condition] * 3,
        "unit_subjects": ["sub-009", "sub-008", "sub-007"],
        "unit_conditions": [condition] * 3,
        "unit_sessions": ["ses-a"] * 3,
        "unit_runs": ["run-04"] * 3,
        "unit_tasks": ["task-sensory"] * 3,
        "unit_n": [30.0, 30.0, 30.0],
        "unit_kind": "subject",
        "input_level": "subject_average",
        "n_units": 3,
    }


def test_group_compare_pairs_multiple_condition_stacks(monkeypatch):
    monkeypatch.setattr(compare, "extract_block", lambda data_info: data_info)

    raw_conditions = ["Stimulus/S  3", "Stimulus/S  4", "Stimulus/S  5"]
    clean_conditions = ["S  3", "S  4", "S  5"]
    a_infos = [_unit_stack(condition, index * 10.0) for index, condition in enumerate(raw_conditions)]
    b_infos = [_unit_stack(condition, index * 10.0 + 1.0) for index, condition in enumerate(raw_conditions)]

    results = compare.run_group_compare(
        a_infos,
        b_infos,
        {"design": "independent", "method": "pointwise", "correction": "none"},
    )

    assert isinstance(results, list)
    assert [result["condition"] for result in results] == clean_conditions
    assert [result["n_a"] for result in results] == [3, 3, 3]
    assert [result["n_b"] for result in results] == [3, 3, 3]
    assert results[0]["contrast_label"].startswith("A ")
    assert " B " in results[0]["contrast_label"]
    assert results[0]["contrast_label"].endswith("S  3")


def test_group_compare_condition_selector_returns_one_stack(monkeypatch):
    monkeypatch.setattr(compare, "extract_block", lambda data_info: data_info)

    conditions = ["Stimulus/S  3", "Stimulus/S  4"]
    a_infos = [_unit_stack(condition, index * 10.0) for index, condition in enumerate(conditions)]
    b_infos = [_unit_stack(condition, index * 10.0 + 1.0) for index, condition in enumerate(conditions)]

    result = compare.run_group_compare(
        a_infos,
        b_infos,
        {
            "condition": "Stimulus/S  4",
            "design": "independent",
            "method": "pointwise",
            "correction": "none",
        },
    )

    assert isinstance(result, dict)
    assert result["condition"] == "S  4"
