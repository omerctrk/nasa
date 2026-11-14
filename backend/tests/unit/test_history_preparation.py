import asyncio
import json
from contextlib import contextmanager
from datetime import timedelta
from threading import get_ident
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI

from app.core.config import Settings
from app.core.history_runtime import configure_history
from app.core.snapshots import snapshot_hash
from app.repositories.records import JobOutcome
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from app.schemas.analysis import AnomalyJobRequest
from app.schemas.common import AnalysisModule, CurrentUser
from app.services.analysis import AnalysisService
from app.services.history import HistoryDataError, HistoryPreparer
from app.workers.analysis import AnalysisWorker, TransientModelError, WorkerSettings
from tests.fakes.worker import WorkerJobStore
from tests.fixtures.history import NOW, history_policy, job, profile, record, thresholds


@pytest.fixture
def policy_paths(tmp_path):
    history_path, threshold_path = tmp_path / "history.json", tmp_path / "thresholds.json"
    history_path.write_text(history_policy().model_dump_json(), encoding="utf-8")
    threshold_path.write_text(thresholds().model_dump_json(), encoding="utf-8")
    return history_path, threshold_path


def test_preparation_uses_a5_mapping_and_one_thread_per_read_context(policy_paths):
    events, queries = [], []
    safe = record(metadata_json={"original_source": "manual", "private": "DO-NOT-SEND"})
    source = safe.model_dump(mode="python")
    source["metadata_json"] = json.dumps(source["metadata_json"])
    session = Mock()
    session.execute.return_value.all.return_value = [SimpleNamespace(_mapping=source)]
    repo = SqlAlchemyRepository(session)
    repo.get_astronaut = Mock(return_value=profile())

    @contextmanager
    def factory():
        events.append(("open", get_ident()))
        try:
            yield repo
        finally:
            events.append(("close", get_ident()))

    times = iter([NOW, NOW + timedelta(seconds=1)])
    preparer = HistoryPreparer(factory, *policy_paths, clock=lambda: next(times))
    result = asyncio.run(preparer.prepare(job()))
    assert result["model_input"]["summary"][0]["record_count"] == 1
    assert "DO-NOT-SEND" not in json.dumps(result)
    assert events[0][1] == events[1][1] and events[0][1] != get_ident()
    statement, params = session.execute.call_args.args
    assert "anomaly.v_measurements" in str(statement)
    assert params == {"a": "A007", "s": NOW.date() - timedelta(days=73), "e": NOW.date() + timedelta(days=1)}


def test_missing_or_display_profile_does_not_read_measurements(policy_paths):
    for value in [None, profile(is_display_only=True)]:
        repo = Mock()
        repo.get_astronaut.return_value = value
        @contextmanager
        def factory():
            yield repo
        preparer = HistoryPreparer(factory, *policy_paths, clock=lambda: NOW)
        with pytest.raises(HistoryDataError):
            asyncio.run(preparer.prepare(job()))
        repo.get_measurements.assert_not_called()


def test_missing_policy_is_a_failure_not_empty_configuration(policy_paths):
    policy_paths[0].unlink()
    @contextmanager
    def unused():
        raise AssertionError("DB should not be read")
        yield
    with pytest.raises(FileNotFoundError):
        asyncio.run(HistoryPreparer(unused, *policy_paths).prepare(job()))


def test_runtime_uses_a5_and_accepts_explicit_date():
    settings = Settings(_env_file=None, db_password="test-only", anomaly_reference_date="2027-03-20")
    app = FastAPI()
    configure_history(app, settings)
    assert isinstance(app.state.history_preparer, HistoryPreparer)
    assert app.state.history_preparer.reference_date == NOW.date()
    assert Settings(_env_file=None, db_password="test-only", anomaly_reference_date="").anomaly_reference_date is None


def test_worker_retry_keeps_frozen_a5_data_and_policy_after_source_changes(policy_paths):
    store = WorkerJobStore()
    current_source = [record(value_num=42)]
    profile_value = profile()
    @contextmanager
    def source_factory():
        class Sources:
            def get_astronaut(self, astronaut_id):
                return profile_value
            def get_measurements(self, astronaut_id, start_date, end_date):
                return current_source
        yield Sources()

    preparer = HistoryPreparer(source_factory, *policy_paths, clock=lambda: NOW)
    user = CurrentUser(user_id=UUID(int=1), role="ASTRONAUT", astronaut_id="A007")
    job_id = AnalysisService(store.transaction).create(user, AnomalyJobRequest(
        module="anomaly", idempotency_key=uuid4(), module_scope="combined")).response.job_id

    class Pipeline:
        preparations = 0
        inputs = []
        async def prepare(self, job):
            self.preparations += 1
            return await preparer.prepare(job)
        async def evaluate(self, job, snapshot):
            self.inputs.append(snapshot)
            if len(self.inputs) == 1:
                raise TransientModelError()
            return {"test_validated": True}
        def persist(self, repo, job, result):
            return JobOutcome(state="COMPLETED", evaluation_status="evaluated", anomaly_result_id=uuid4())

    pipeline = Pipeline()
    worker = AnalysisWorker(store.transaction, {module: pipeline for module in AnalysisModule}, WorkerSettings())
    async def scenario():
        await worker.tick()
        frozen_hash = store.jobs[job_id].input_hash
        current_source[0] = record(value_num=999)
        policy_paths[1].write_text('{"version":"later-policy","rules":[]}', encoding="utf-8")
        store.advance(2)
        await worker.tick()
        assert store.jobs[job_id].record.state == "COMPLETED"
        assert store.jobs[job_id].input_hash == frozen_hash
    asyncio.run(scenario())
    assert pipeline.preparations == 1
    assert pipeline.inputs[0] == pipeline.inputs[1]
    assert pipeline.inputs[1]["model_input"]["current_measurements"][0]["value_num"] == 42
    assert pipeline.inputs[1]["threshold_policy"]["version"] == "test-unconfigured"
    assert snapshot_hash(pipeline.inputs[1]) == store.jobs[job_id].input_hash
