"""
Purpose: Test backend behavior for dataset QA and related API/service contracts.
Related: app/services/dataset_qa.py, app/routers/datasets.py, docs_v2/2-50.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
import importlib.util
import sys
import tempfile
import uuid


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def install_dependency_stubs() -> None:
    fastapi = ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code=None, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class APIRouter:
        def __init__(self, *args, prefix="", tags=None, **kwargs):
            self.prefix = prefix
            self.tags = tags or []
            self.routes = []

        def get(self, path, **kwargs):
            def decorator(fn):
                self.routes.append(SimpleNamespace(path=self.prefix + path, endpoint=fn, methods={"GET"}, **kwargs))
                return fn

            return decorator

        def post(self, path, **kwargs):
            def decorator(fn):
                self.routes.append(SimpleNamespace(path=self.prefix + path, endpoint=fn, methods={"POST"}, **kwargs))
                return fn

            return decorator

        def patch(self, path, **kwargs):
            def decorator(fn):
                self.routes.append(SimpleNamespace(path=self.prefix + path, endpoint=fn, methods={"PATCH"}, **kwargs))
                return fn

            return decorator

        def delete(self, path, **kwargs):
            def decorator(fn):
                self.routes.append(SimpleNamespace(path=self.prefix + path, endpoint=fn, methods={"DELETE"}, **kwargs))
                return fn

            return decorator

    def marker(*args, **kwargs):
        return None

    fastapi.APIRouter = APIRouter
    fastapi.Depends = marker
    fastapi.File = marker
    fastapi.Form = marker
    fastapi.HTTPException = HTTPException
    fastapi.UploadFile = type("UploadFile", (), {})
    fastapi.status = SimpleNamespace(
        HTTP_400_BAD_REQUEST=400,
        HTTP_201_CREATED=201,
        HTTP_403_FORBIDDEN=403,
        HTTP_404_NOT_FOUND=404,
        HTTP_409_CONFLICT=409,
        HTTP_500_INTERNAL_SERVER_ERROR=500,
    )
    sys.modules["fastapi"] = fastapi

    sqlalchemy = ModuleType("sqlalchemy")
    sqlalchemy.func = SimpleNamespace()
    sys.modules["sqlalchemy"] = sqlalchemy

    sqlalchemy_orm = ModuleType("sqlalchemy.orm")
    sqlalchemy_orm.Session = type("Session", (), {})
    sqlalchemy_orm.joinedload = lambda *args, **kwargs: None
    sys.modules["sqlalchemy.orm"] = sqlalchemy_orm

    app_database = ModuleType("app.database")
    app_database.get_db = lambda: None
    sys.modules["app.database"] = app_database

    class Column:
        def __init__(self, name):
            self.name = name

        def __eq__(self, other):
            return (self.name, other)

        def desc(self):
            return (self.name, "desc")

    class DatasetAsset:
        pass

    class DatasetVersion:
        dataset_asset_id = Column("dataset_asset_id")
        version_label = Column("version_label")

    class DatasetFile:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class DatasetFileDerivation:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class Study:
        id = Column("id")

    class AuditEvent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class Subject:
        study_id = Column("study_id")
        bids_subject_id = Column("bids_subject_id")

    class Recording:
        id = Column("id")
        study_id = Column("study_id")
        subject = object()
        current_version = object()
        imported_at = Column("imported_at")

    class RecordingVersion:
        pass

    class StudyDatasetMount:
        pass

    class User:
        pass

    app_models = ModuleType("app.models")
    for name, value in {
        "DatasetAsset": DatasetAsset,
        "DatasetVersion": DatasetVersion,
        "DatasetFile": DatasetFile,
        "DatasetFileDerivation": DatasetFileDerivation,
        "Study": Study,
        "AuditEvent": AuditEvent,
        "Recording": Recording,
        "RecordingVersion": RecordingVersion,
        "StudyDatasetMount": StudyDatasetMount,
        "Subject": Subject,
        "User": User,
    }.items():
        setattr(app_models, name, value)
    sys.modules["app.models"] = app_models

    routers_pkg = ModuleType("app.routers")
    routers_pkg.__path__ = []
    sys.modules["app.routers"] = routers_pkg

    app_auth = ModuleType("app.routers.auth")
    app_auth.get_current_user = lambda: None
    sys.modules["app.routers.auth"] = app_auth

    services_pkg = ModuleType("app.services")
    services_pkg.__path__ = []
    sys.modules["app.services"] = services_pkg

    dataset_qa = ModuleType("app.services.dataset_qa")
    dataset_qa.build_mock_qa_report = lambda study, dataset: {}
    sys.modules["app.services.dataset_qa"] = dataset_qa

    audit_events = ModuleType("app.services.audit_events")
    audit_events.record_audit_event = lambda *args, **kwargs: None
    sys.modules["app.services.audit_events"] = audit_events

    dataset_assets = ModuleType("app.services.dataset_assets")

    class DatasetAssetConflictError(Exception):
        pass

    dataset_assets.DatasetAssetConflictError = DatasetAssetConflictError
    dataset_assets.can_write_dataset_asset = lambda *args, **kwargs: True
    dataset_assets.create_dataset_asset = lambda *args, **kwargs: None
    dataset_assets.get_active_study_dataset_mount_for_asset = lambda *args, **kwargs: None
    dataset_assets.get_dataset_asset_for_user = lambda *args, **kwargs: None
    dataset_assets.get_or_create_working_dataset_asset = lambda *args, **kwargs: None
    dataset_assets.get_study_dataset_mount = lambda *args, **kwargs: None
    dataset_assets.get_study_dataset_mount_by_name = lambda *args, **kwargs: None
    dataset_assets.list_study_dataset_mounts = lambda *args, **kwargs: []
    dataset_assets.list_visible_dataset_assets = lambda *args, **kwargs: []
    dataset_assets.mount_dataset_asset_to_study = lambda *args, **kwargs: None
    dataset_assets.update_study_dataset_mount = lambda *args, **kwargs: None
    sys.modules["app.services.dataset_assets"] = dataset_assets

    dataset_bootstrap = ModuleType("app.services.dataset_bootstrap")

    class DatasetBootstrapStorageError(Exception):
        pass

    dataset_bootstrap.DatasetBootstrapStorageError = DatasetBootstrapStorageError
    dataset_bootstrap.bootstrap_dataset = lambda *args, **kwargs: None
    sys.modules["app.services.dataset_bootstrap"] = dataset_bootstrap

    studies = ModuleType("app.services.studies")

    class StudyCreateCodeConflictError(Exception):
        pass

    class StudyCreateIntegrityError(Exception):
        pass

    class StudyStorageSetupError(Exception):
        pass

    studies.StudyCreateCodeConflictError = StudyCreateCodeConflictError
    studies.StudyCreateIntegrityError = StudyCreateIntegrityError
    studies.StudyStorageSetupError = StudyStorageSetupError
    studies.ensure_study_create_permission = lambda *args, **kwargs: None
    sys.modules["app.services.studies"] = studies

    study_access = ModuleType("app.services.study_access")
    study_access.require_study_read = lambda study, db, current_user: study
    study_access.require_study_write = lambda study, db, current_user: study
    sys.modules["app.services.study_access"] = study_access

    recordings = ModuleType("app.services.recordings")
    recordings.get_recording_for_study = lambda *args, **kwargs: None
    recordings.list_recording_versions_for_study = lambda *args, **kwargs: []
    recordings.list_recordings_for_study = lambda *args, **kwargs: []
    sys.modules["app.services.recordings"] = recordings

    file_browser = ModuleType("app.services.file_browser")

    class FileAccessError(Exception):
        def __init__(self, code="", message="", status_code=400):
            super().__init__(message)
            self.code = code
            self.message = message
            self.status_code = status_code

    file_browser.FileAccessError = FileAccessError
    file_browser.build_dataset_file_tree = lambda files, prefix="raw_bids": {
        "name": prefix,
        "path": prefix,
        "kind": "directory",
        "children": [],
    }
    file_browser.dataset_file_metadata = lambda file_record, study=None: {
        "id": str(getattr(file_record, "id", "")),
        "study_id": getattr(file_record, "study_id", ""),
        "dataset_id": str(getattr(file_record, "dataset_id", "")),
        "dataset_upload_id": str(getattr(file_record, "dataset_upload_id", "")),
        "dataset_version_id": str(getattr(file_record, "dataset_version_id", "")) if getattr(file_record, "dataset_version_id", None) else None,
        "file_role": getattr(file_record, "file_role", ""),
        "storage_uri": getattr(file_record, "storage_uri", ""),
        "relative_path": getattr(file_record, "relative_path", ""),
        "logical_path": getattr(file_record, "logical_path", None),
        "file_name": "file",
        "extension": "",
        "file_size": getattr(file_record, "file_size", None),
        "sha256": getattr(file_record, "sha256", None),
        "mime_type": getattr(file_record, "mime_type", None),
        "metadata_json": getattr(file_record, "metadata_json", {}) or {},
        "exists": False,
        "preview_supported": False,
        "download_name": "file",
        "created_by": None,
        "created_at": None,
    }
    file_browser.dataset_file_preview = lambda file_record, study=None: {
        "file": file_browser.dataset_file_metadata(file_record, study=study),
        "preview_json": {},
        "generated_at": datetime.now(timezone.utc),
    }
    file_browser.download_filename = lambda file_record: "file"
    file_browser.resolve_dataset_file_path = lambda file_record, study=None: Path(".")
    sys.modules["app.services.file_browser"] = file_browser


def load_datasets_router():
    install_dependency_stubs()
    spec = importlib.util.spec_from_file_location(
        "datasets_under_test",
        BACKEND_DIR / "app" / "routers" / "datasets.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["datasets_under_test"] = module
    spec.loader.exec_module(module)
    return module


def load_real_dataset_qa_service():
    spec = importlib.util.spec_from_file_location(
        "dataset_qa_service_under_test",
        BACKEND_DIR / "app" / "services" / "dataset_qa.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["dataset_qa_service_under_test"] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_datasets_router()
REAL_QA_SERVICE = load_real_dataset_qa_service()

from app.schemas.dataset import DatasetQaReport, DatasetQaReviewRequest, DatasetQaStage, DatasetQaSummary  # noqa: E402


class FakeUser:
    def __init__(self):
        self.id = uuid.uuid4()
        self.permission_checks = []

    def has_role(self, name):
        return False

    def has_permission(self, code):
        self.permission_checks.append(code)
        return code in {"data:read", "data:write"}


class FakeQuery:
    def __init__(self, value, model_name):
        self.value = value
        self.model_name = model_name
        self.clauses = []

    def filter(self, *args, **kwargs):
        self.clauses.extend(args)
        return self

    def options(self, *args, **kwargs):
        return self

    def first(self):
        if self.value is None:
            return None
        for clause in self.clauses:
            if not isinstance(clause, tuple) or len(clause) != 2:
                continue
            field, expected = clause
            actual = getattr(self.value, field, None)
            if actual != expected and str(actual) != str(expected):
                return None
        return self.value


class FakeDB:
    def __init__(self, study, dataset):
        self.study = study
        self.dataset = dataset
        self.committed = False
        self.rolled_back = False
        self.refreshed = None
        self.added = []

    def query(self, model):
        if model.__name__ == "Study":
            return FakeQuery(self.study, model.__name__)
        if model.__name__ == "Recording":
            return FakeQuery(self.dataset, model.__name__)
        raise AssertionError(f"unexpected query model: {model!r}")

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, obj):
        self.refreshed = obj


def make_report(*, blocking_issues=None, warnings=None):
    blocking_issues = blocking_issues or []
    warnings = warnings or []
    return DatasetQaReport(
        mode="mock",
        generated_at=datetime.now(timezone.utc),
        summary=DatasetQaSummary(
            mock_qc_status="blocked" if blocking_issues else "passed_with_warnings" if warnings else "passed",
            level="bad" if blocking_issues else "warning" if warnings else "good",
            score=None,
            blocking_issues=blocking_issues,
            warnings=warnings,
        ),
        stages=[
            DatasetQaStage(
                key="signal_placeholder",
                title="信号质量占位",
                status="not_computed",
                severity="info",
                message="真实 RMS/PSD/坏段指标尚未实现。",
            )
        ],
    ).model_dump(mode="json")


def find_stage(report, key):
    for stage in report["stages"]:
        if stage["key"] == key:
            return stage
    raise AssertionError(f"stage not found: {key}")


def install_fake_mne_reader():
    old_mne = sys.modules.get("mne")
    old_had_mne = "mne" in sys.modules

    class FakeRaw:
        info = {"sfreq": 100.0, "nchan": 2}
        ch_names = ["Cz", "Pz"]
        n_times = 1000

        def close(self):
            return None

    fake_mne = ModuleType("mne")
    fake_mne.io = SimpleNamespace(read_raw_fif=lambda *args, **kwargs: FakeRaw())
    sys.modules["mne"] = fake_mne

    def restore():
        if old_had_mne:
            sys.modules["mne"] = old_mne
        else:
            sys.modules.pop("mne", None)

    return restore


def make_service_study_and_dataset(root, *, fif_path="derivatives/sub-01_task-rest_raw.fif", metadata=True):
    root = Path(root)
    source_path = Path("raw/sub-01_task-rest.edf")
    import_path = Path("sidecars/import.json")
    channels_path = Path("sidecars/channels.tsv")
    events_path = Path("sidecars/events.tsv")

    for relative_path, content in {
        source_path: "edf placeholder",
        import_path: "{}",
        channels_path: "name\ttype\nCz\tEEG\nPz\tEEG\n",
        events_path: "onset\tduration\ttrial_type\n1.0\t0.1\tstim\n",
    }.items():
        absolute_path = root / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_text(content, encoding="utf-8")

    if fif_path:
        fif_abs = root / fif_path
        fif_abs.parent.mkdir(parents=True, exist_ok=True)
        fif_abs.write_text("fif placeholder", encoding="utf-8")

    study = SimpleNamespace(id="202605000100", data_root=str(root))
    dataset = SimpleNamespace(
        id=uuid.uuid4(),
        study_id=study.id,
        bids_subject_id="sub-01",
        subject=SimpleNamespace(bids_subject_id="sub-01"),
        task="rest",
        session="ses-01",
        run="01",
        source_path=source_path.as_posix(),
        fif_path=fif_path,
        current_version_id=uuid.uuid4(),
        current_version=SimpleNamespace(
            id=uuid.uuid4(),
            sidecar_paths={
                "import": import_path.as_posix(),
                "channels": channels_path.as_posix(),
                "events": events_path.as_posix(),
            },
        ),
        n_channels=2 if metadata else None,
        sfreq=100.0 if metadata else None,
        duration_seconds=10.0 if metadata else None,
        n_events=1 if metadata else None,
        checksum="abc123" if metadata else None,
        qa_status="converted",
    )
    return study, dataset


def make_dataset(study_id, qa_status="converted"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        study_id=study_id,
        qa_status=qa_status,
        qa_report=None,
        current_version_id=uuid.uuid4(),
        imported_at=datetime.now(timezone.utc),
    )


def run_mock_case(dataset, report):
    study = SimpleNamespace(id=dataset.study_id)
    db = FakeDB(study, dataset)
    user = FakeUser()
    MODULE.build_mock_qa_report = lambda current_study, current_dataset: report
    response = MODULE.run_recording_mock_qa_report(study.id, dataset.id, db, user)
    return response, db, user


def run_review_case(dataset, conclusion, notes=None):
    study = SimpleNamespace(id=dataset.study_id)
    db = FakeDB(study, dataset)
    user = FakeUser()
    review = DatasetQaReviewRequest(conclusion=conclusion, notes=notes)
    response = MODULE.review_recording_qa_report(study.id, dataset.id, review, db, user)
    return response, db, user


def test_build_mock_qa_report_normal_dataset():
    with tempfile.TemporaryDirectory() as tmp:
        study, dataset = make_service_study_and_dataset(tmp)
        restore_mne = install_fake_mne_reader()
        try:
            report = REAL_QA_SERVICE.build_mock_qa_report(study, dataset)
        finally:
            restore_mne()

    assert report["mode"] == "mock"
    assert report["summary"]["score"] is None
    assert report["summary"]["blocking_issues"] == []
    assert find_stage(report, "file_integrity")["status"] == "pass"
    assert find_stage(report, "fif_header")["status"] == "pass"
    assert find_stage(report, "signal_placeholder")["status"] == "not_computed"


def test_build_mock_qa_report_missing_fif_path():
    with tempfile.TemporaryDirectory() as tmp:
        study, dataset = make_service_study_and_dataset(tmp, fif_path=None)
        report = REAL_QA_SERVICE.build_mock_qa_report(study, dataset)

    assert "fif_exists" in report["summary"]["blocking_issues"]
    assert find_stage(report, "file_integrity")["status"] == "fail"
    assert find_stage(report, "fif_header")["status"] == "fail"
    assert find_stage(report, "signal_placeholder")["status"] == "not_computed"


def test_build_mock_qa_report_missing_fif_file():
    with tempfile.TemporaryDirectory() as tmp:
        study, dataset = make_service_study_and_dataset(tmp, fif_path="derivatives/missing_raw.fif")
        missing_path = Path(tmp) / dataset.fif_path
        missing_path.unlink()
        report = REAL_QA_SERVICE.build_mock_qa_report(study, dataset)

    assert "fif_exists" in report["summary"]["blocking_issues"]
    assert find_stage(report, "file_integrity")["status"] == "fail"
    assert find_stage(report, "fif_header")["status"] == "fail"


def test_build_mock_qa_report_missing_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        study, dataset = make_service_study_and_dataset(tmp, metadata=False)
        restore_mne = install_fake_mne_reader()
        try:
            report = REAL_QA_SERVICE.build_mock_qa_report(study, dataset)
        finally:
            restore_mne()

    assert "n_channels_invalid" in report["summary"]["blocking_issues"]
    assert "sfreq_invalid" in report["summary"]["blocking_issues"]
    assert "duration_seconds_invalid" in report["summary"]["blocking_issues"]
    assert report["summary"]["warnings"]
    assert find_stage(report, "metadata_consistency")["status"] == "fail"


def test_get_qa_without_report_returns_empty_state():
    dataset = make_dataset("202605000010", qa_status="converted")
    study = SimpleNamespace(id=dataset.study_id)
    db = FakeDB(study, dataset)
    user = FakeUser()

    response = MODULE.get_recording_qa_report(study.id, dataset.id, db, user)

    assert response.has_report is False
    assert response.qa_report is None
    assert response.qa_status == "converted"
    assert response.dataset_id == str(dataset.id)
    assert response.current_upload_id == str(dataset.current_version_id)
    assert user.permission_checks == ["data:read"]


def test_get_qa_with_report_returns_complete_structure():
    dataset = make_dataset("202605000011", qa_status="checked")
    dataset.qa_report = make_report(warnings=["source 文件缺失。"])
    study = SimpleNamespace(id=dataset.study_id)
    db = FakeDB(study, dataset)
    user = FakeUser()

    response = MODULE.get_recording_qa_report(study.id, dataset.id, db, user)

    assert response.has_report is True
    assert response.qa_report.mode == "mock"
    assert response.qa_report.summary.score is None
    assert response.qa_report.summary.warnings == ["source 文件缺失。"]
    assert response.qa_report.stages[0].key == "signal_placeholder"


def test_mock_run_persists_report_and_returns_latest_status():
    dataset = make_dataset("202605000001", qa_status="converted")
    response, db, user = run_mock_case(dataset, make_report())

    assert db.committed is True
    assert db.rolled_back is False
    assert db.refreshed is dataset
    assert dataset.qa_report is not None
    assert dataset.qa_report["mode"] == "mock"
    assert response.qa_status == "converted"
    assert response.qa_report.mode == "mock"
    assert response.qa_report.summary.score is None
    assert response.qa_report.stages[0].key == "signal_placeholder"
    assert response.qa_report.stages[0].status == "not_computed"
    assert user.permission_checks == ["data:write"]
    assert len(db.added) == 1
    assert db.added[0].action == "dataset.qa.mock_run"
    assert db.added[0].metadata_json["dataset_id"] == str(dataset.id)
    assert db.added[0].metadata_json["current_upload_id"] == str(dataset.current_version_id)
    assert db.added[0].metadata_json["old_qa_status"] == "converted"
    assert db.added[0].metadata_json["new_qa_status"] == "converted"
    assert db.added[0].metadata_json["conclusion"] is None
    assert db.added[0].metadata_json["has_blocking_issues"] is False
    assert "qa_report" not in db.added[0].metadata_json
    assert dataset.qa_report["history"][-1]["action"] == "dataset.qa.mock_run"
    assert dataset.qa_report["history"][-1]["actor_id"] == str(user.id)
    assert dataset.qa_report["history"][-1]["status"] == "converted"


def test_warning_report_does_not_auto_check():
    dataset = make_dataset("202605000002", qa_status="converted")
    response, db, _user = run_mock_case(dataset, make_report(warnings=["source 文件缺失。"]))

    assert db.committed is True
    assert dataset.qa_report["summary"]["warnings"]
    assert dataset.qa_status == "converted"
    assert response.qa_status == "converted"
    assert response.qa_status != "checked"


def test_blocking_report_cannot_stay_checked():
    dataset = make_dataset("202605000003", qa_status="checked")
    response, db, _user = run_mock_case(dataset, make_report(blocking_issues=["fif_exists"]))

    assert db.committed is True
    assert dataset.qa_report["summary"]["blocking_issues"] == ["fif_exists"]
    assert dataset.qa_status == "failed"
    assert response.qa_status == "failed"
    assert response.qa_status != "checked"
    assert db.added[0].metadata_json["old_qa_status"] == "checked"
    assert db.added[0].metadata_json["new_qa_status"] == "failed"
    assert db.added[0].metadata_json["has_blocking_issues"] is True
    assert dataset.qa_report["history"][-1]["status"] == "failed"


def test_review_accept_success_writes_checked_and_human_review():
    dataset = make_dataset("202605000004", qa_status="converted")
    dataset.qa_report = make_report()
    original_stage_count = len(dataset.qa_report["stages"])

    response, db, user = run_review_case(dataset, "accept", notes="人工确认通过")

    assert db.committed is True
    assert dataset.qa_status == "checked"
    assert response.qa_status == "checked"
    assert len(dataset.qa_report["stages"]) == original_stage_count
    assert dataset.qa_report["human_review"]["conclusion"] == "accept"
    assert dataset.qa_report["human_review"]["notes"] == "人工确认通过"
    assert dataset.qa_report["human_review"]["reviewed_by"] == str(user.id)
    assert dataset.qa_report["human_review"]["reviewed_at"]
    assert response.qa_report.human_review.conclusion == "accept"
    assert len(db.added) == 1
    assert db.added[0].action == "dataset.qa.review"
    assert db.added[0].metadata_json["old_qa_status"] == "converted"
    assert db.added[0].metadata_json["new_qa_status"] == "checked"
    assert db.added[0].metadata_json["conclusion"] == "accept"
    assert db.added[0].metadata_json["has_blocking_issues"] is False
    assert "qa_report" not in db.added[0].metadata_json
    assert dataset.qa_report["history"][-1]["action"] == "dataset.qa.review"
    assert dataset.qa_report["history"][-1]["actor_id"] == str(user.id)
    assert dataset.qa_report["history"][-1]["status"] == "checked"


def test_review_accept_rejected_by_blocking_issue():
    dataset = make_dataset("202605000005", qa_status="failed")
    dataset.qa_report = make_report(blocking_issues=["fif_exists"])
    before_report = dataset.qa_report.copy()

    study = SimpleNamespace(id=dataset.study_id)
    db = FakeDB(study, dataset)
    user = FakeUser()
    review = DatasetQaReviewRequest(conclusion="accept")

    try:
        MODULE.review_recording_qa_report(study.id, dataset.id, review, db, user)
    except MODULE.HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("accept should fail when blocking issues exist")

    assert db.committed is False
    assert dataset.qa_status == "failed"
    assert dataset.qa_report == before_report
    assert db.added == []


def test_review_reject_writes_rejected():
    dataset = make_dataset("202605000006", qa_status="converted")
    dataset.qa_report = make_report(warnings=["source 文件缺失。"])

    response, db, _user = run_review_case(dataset, "reject", notes="需要重新上传")

    assert db.committed is True
    assert dataset.qa_status == "rejected"
    assert response.qa_status == "rejected"
    assert dataset.qa_report["human_review"]["conclusion"] == "reject"
    assert dataset.qa_report["human_review"]["notes"] == "需要重新上传"
    assert db.added[0].metadata_json["conclusion"] == "reject"
    assert db.added[0].metadata_json["new_qa_status"] == "rejected"
    assert dataset.qa_report["history"][-1]["status"] == "rejected"


def test_review_hold_does_not_write_checked():
    dataset = make_dataset("202605000007", qa_status="checked")
    dataset.qa_report = make_report()

    response, db, _user = run_review_case(dataset, "hold")

    assert db.committed is True
    assert dataset.qa_status == "converted"
    assert response.qa_status == "converted"
    assert response.qa_status != "checked"
    assert dataset.qa_report["human_review"]["conclusion"] == "hold"
    assert db.added[0].metadata_json["conclusion"] == "hold"
    assert db.added[0].metadata_json["old_qa_status"] == "checked"
    assert db.added[0].metadata_json["new_qa_status"] == "converted"
    assert dataset.qa_report["history"][-1]["status"] == "converted"


def test_review_hold_preserves_failed_or_rejected_status():
    failed_dataset = make_dataset("202605000008", qa_status="failed")
    failed_dataset.qa_report = make_report(blocking_issues=["fif_exists"])
    failed_response, _db, _user = run_review_case(failed_dataset, "hold")
    assert failed_response.qa_status == "failed"

    rejected_dataset = make_dataset("202605000009", qa_status="rejected")
    rejected_dataset.qa_report = make_report()
    rejected_response, _db, _user = run_review_case(rejected_dataset, "hold")
    assert rejected_response.qa_status == "rejected"


def test_dataset_from_other_study_is_not_accessible_for_qa_routes():
    requested_study = SimpleNamespace(id="202605-study-a")
    dataset = make_dataset("202605-study-b", qa_status="converted")
    dataset.qa_report = make_report()

    for call in (
        lambda db, user: MODULE.get_recording_qa_report(requested_study.id, dataset.id, db, user),
        lambda db, user: MODULE.run_recording_mock_qa_report(requested_study.id, dataset.id, db, user),
        lambda db, user: MODULE.review_recording_qa_report(
            requested_study.id,
            dataset.id,
            DatasetQaReviewRequest(conclusion="accept"),
            db,
            user,
        ),
    ):
        db = FakeDB(requested_study, dataset)
        user = FakeUser()
        try:
            call(db, user)
        except MODULE.HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("dataset from another study should not be accessible")
        assert db.committed is False


if __name__ == "__main__":
    test_build_mock_qa_report_normal_dataset()
    test_build_mock_qa_report_missing_fif_path()
    test_build_mock_qa_report_missing_fif_file()
    test_build_mock_qa_report_missing_metadata()
    test_get_qa_without_report_returns_empty_state()
    test_get_qa_with_report_returns_complete_structure()
    test_mock_run_persists_report_and_returns_latest_status()
    test_warning_report_does_not_auto_check()
    test_blocking_report_cannot_stay_checked()
    test_review_accept_success_writes_checked_and_human_review()
    test_review_accept_rejected_by_blocking_issue()
    test_review_reject_writes_rejected()
    test_review_hold_does_not_write_checked()
    test_review_hold_preserves_failed_or_rejected_status()
    test_dataset_from_other_study_is_not_accessible_for_qa_routes()
    print("dataset qa service/api tests passed")
