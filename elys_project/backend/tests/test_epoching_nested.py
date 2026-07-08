import numpy as np

from app.engine.analysis.epoching import run_epoch_segment


def test_epoch_can_segment_inside_parent_epochs():
    import mne

    sfreq = 100.0
    info = mne.create_info(["Cz"], sfreq, ["eeg"])
    raw = mne.io.RawArray(np.zeros((1, int(10 * sfreq))), info, verbose="ERROR")
    raw.set_annotations(
        mne.Annotations(
            onset=[1.0, 1.5, 2.0, 5.0, 5.5, 6.0],
            duration=[0, 0, 0, 0, 0, 0],
            description=["block", "stim/A", "stim/B", "block", "stim/A", "stim/B"],
        )
    )

    parent, parent_diag = run_epoch_segment(
        raw,
        {"conditions": ["block"], "tmin": 0.0, "tmax": 2.0},
    )
    assert len(parent) == 2
    assert parent_diag["skipped_conditions"] == []

    child, child_diag = run_epoch_segment(
        parent,
        {"conditions": ["stim/A"], "tmin": -0.1, "tmax": 0.2},
    )
    assert len(child) == 2
    assert child.event_id == {"stim/A": 1}
    assert child_diag["skipped_conditions"] == []
    assert child_diag["source"] == "epochs"
    assert child_diag["dropped_outside_parent"] == 0

    per_child = child.get_annotations_per_epoch()
    assert len(per_child) == 2
    assert all(any(desc == "stim/A" and abs(float(onset)) < 1e-9 for onset, _, desc in anns) for anns in per_child)
