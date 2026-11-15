import asyncio
import unittest
from copy import deepcopy
from dataclasses import replace
from uuid import UUID, uuid4

from app.repositories.errors import LeaseLost
from app.repositories.records import JobOutcome
from app.schemas.analysis import AnomalyJobRequest, SansJobRequest
from app.schemas.common import AnalysisModule, CurrentUser, JobState
from app.services.analysis import AnalysisService
from app.workers.analysis import (
    AnalysisWorker, InvalidModelOutput, PermanentModelError, TransientModelError,
    WorkerSettings, snapshot_hash,
)
from tests.fakes.worker import WorkerJobStore


class Pipeline:
    def __init__(self, store):
        self.store = store
        self.prepare_calls = self.evaluate_calls = self.persist_calls = 0
        self.actions = []
        self.inputs = []
        self.on_evaluate = None
        self.persist_failure = False
        self.invalid_outcome = False

    async def prepare(self, job):
        self.prepare_calls += 1
        assert self.store.transaction_depth == 0
        return {"records": [{"record_id": "fixture:1", "value": 42}]}

    async def evaluate(self, job, snapshot):
        self.evaluate_calls += 1
        assert self.store.transaction_depth == 0
        self.inputs.append(deepcopy(snapshot))
        if self.on_evaluate:
            await self.on_evaluate(job, snapshot)
        if self.actions:
            action = self.actions.pop(0)
            if isinstance(action, Exception):
                raise action
        return {"validated": True}

    def persist(self, repo, job, result):
        self.persist_calls += 1
        assert self.store.transaction_depth == 1
        self.store.results[job.job_id] = result
        if self.persist_failure:
            raise RuntimeError("PRIVATE PROVIDER RESPONSE")
        if self.invalid_outcome:
            return JobOutcome(state="COMPLETED", evaluation_status="evaluated")
        refs = ({"anomaly_result_id": uuid4()} if job.module == AnalysisModule.ANOMALY
                else {"sans_analysis_id": 1})
        return JobOutcome(state="COMPLETED", evaluation_status="evaluated", **refs)


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store = WorkerJobStore()
        self.service = AnalysisService(self.store.transaction)
        self.user = CurrentUser(user_id=UUID(int=1), role="ASTRONAUT", astronaut_id="A007")
        self.pipeline = Pipeline(self.store)
        self.settings = WorkerSettings(retry_delay_seconds=2)
        self.worker = self.make_worker()

    def make_worker(self, settings=None, pipeline=None):
        processor = pipeline or self.pipeline
        return AnalysisWorker(self.store.transaction,
                              {AnalysisModule.ANOMALY: processor, AnalysisModule.SANS: processor},
                              settings or self.settings)

    def create(self, module="anomaly"):
        request = (AnomalyJobRequest(module="anomaly", idempotency_key=uuid4(), module_scope="combined")
                   if module == "anomaly" else
                   SansJobRequest(module="sans", idempotency_key=uuid4(), session_id="S-A007-D074"))
        return self.service.create(self.user, request).response.job_id

    async def test_happy_path_and_no_transaction_during_provider_call(self):
        job_id = self.create()
        self.assertTrue(await self.worker.tick())
        stored = self.store.jobs[job_id]
        self.assertEqual(stored.record.state, JobState.COMPLETED)
        self.assertEqual(stored.record.attempts, 1)
        self.assertIsNotNone(stored.record.anomaly_result_id)
        self.assertEqual(stored.input_hash, snapshot_hash(stored.snapshot))
        self.assertNotIn(job_id, self.store.leases)
        self.assertFalse(await self.worker.tick())

    async def test_anomaly_only_worker_leaves_legacy_sans_job_queued(self):
        sans_id = self.create("sans")
        anomaly_id = self.create("anomaly")
        worker = AnalysisWorker(self.store.transaction,
                                {AnalysisModule.ANOMALY: self.pipeline}, self.settings)
        self.assertTrue(await worker.tick())
        self.assertEqual(self.store.jobs[anomaly_id].record.state, JobState.COMPLETED)
        self.assertEqual(self.store.jobs[sans_id].record.state, JobState.QUEUED)

    async def test_transient_retry_is_delayed_and_uses_same_snapshot(self):
        job_id = self.create()
        self.pipeline.actions = [TransientModelError("PRIVATE")]
        await self.worker.tick()
        before = deepcopy(self.store.jobs[job_id])
        self.assertEqual(before.record.state, JobState.QUEUED)
        self.assertFalse(await self.worker.tick())
        self.store.advance(2)
        await self.worker.tick()
        after = self.store.jobs[job_id]
        self.assertEqual(after.record.state, JobState.COMPLETED)
        self.assertEqual(after.record.attempts, 2)
        self.assertEqual(self.pipeline.prepare_calls, 1)
        self.assertEqual(self.pipeline.inputs[0], self.pipeline.inputs[1])
        self.assertEqual((before.snapshot, before.input_hash), (after.snapshot, after.input_hash))

    async def test_retry_exhaustion_is_failed_not_normal(self):
        job_id = self.create()
        self.pipeline.actions = [TransientModelError(), TransientModelError()]
        await self.worker.tick()
        self.store.advance(2)
        await self.worker.tick()
        stored = self.store.jobs[job_id]
        self.assertEqual(stored.record.state, JobState.FAILED)
        self.assertEqual(stored.record.error_code, "MODEL_CONNECTION_ERROR")
        self.assertEqual(self.pipeline.evaluate_calls, 2)
        self.assertEqual(self.pipeline.persist_calls, 0)
        self.assertIsNone(stored.record.anomaly_result_id)
        self.assertFalse(await self.worker.tick())

    async def test_permanent_and_invalid_outputs_are_not_retried(self):
        for error, expected in [(PermanentModelError("PRIVATE"), "MODEL_REQUEST_REJECTED"),
                                (InvalidModelOutput("PRIVATE"), "MODEL_OUTPUT_INVALID")]:
            with self.subTest(error=type(error).__name__):
                job_id = self.create()
                self.pipeline.actions = [error]
                await self.worker.tick()
                self.assertEqual(self.store.jobs[job_id].record.state, JobState.FAILED)
                self.assertEqual(self.store.jobs[job_id].record.error_code, expected)
                self.assertNotIn(job_id, self.store.results)

    async def test_timeout_is_bounded_and_scheduled_for_anomaly(self):
        job_id = self.create()
        async def wait(job, snapshot):
            await asyncio.Event().wait()
        self.pipeline.on_evaluate = wait
        worker = self.make_worker(replace(self.settings, model_timeout_seconds=0.02))
        await asyncio.wait_for(worker.tick(), 1)
        self.assertEqual(self.store.jobs[job_id].record.state, JobState.QUEUED)
        self.assertEqual(self.store.jobs[job_id].record.error_code, "MODEL_TIMEOUT")

    async def test_sans_timeout_and_manual_retry_do_not_repeat_post(self):
        job_id = self.create("sans")
        self.pipeline.actions = [TimeoutError()]
        await self.worker.tick()
        self.assertEqual(self.store.jobs[job_id].record.error_code, "SANS_RECONCILIATION_REQUIRED")
        self.assertEqual(self.store.jobs[job_id].record.state, JobState.FAILED)
        self.service.retry(self.user, job_id)
        await self.worker.tick()
        self.assertEqual(self.pipeline.evaluate_calls, 1)
        self.assertEqual(self.store.jobs[job_id].record.state, JobState.FAILED)
        self.assertEqual(self.store.jobs[job_id].record.error_code, "SANS_RECONCILIATION_REQUIRED")

    async def test_sans_retry_uses_explicit_reconciliation_adapter(self):
        job_id = self.create("sans")
        self.pipeline.actions = [TimeoutError()]
        await self.worker.tick()
        calls = []
        async def reconcile(job, snapshot):
            calls.append((job.job_id, deepcopy(snapshot)))
            return {"source_result_reconciled": True}
        self.pipeline.reconcile = reconcile
        self.service.retry(self.user, job_id)
        await self.worker.tick()
        self.assertEqual(self.pipeline.evaluate_calls, 1)
        self.assertEqual(calls[0][0], job_id)
        self.assertEqual(self.store.jobs[job_id].record.state, JobState.COMPLETED)

    async def test_provider_mutation_does_not_mutate_stored_input(self):
        job_id = self.create()
        async def mutate(job, snapshot):
            snapshot["records"][0]["value"] = 999
        self.pipeline.on_evaluate = mutate
        await self.worker.tick()
        self.assertEqual(self.store.jobs[job_id].snapshot["records"][0]["value"], 42)

    async def test_stale_worker_response_cannot_write_result(self):
        job_id = self.create()
        async def change_owner(job, snapshot):
            self.store.leases[job_id] = uuid4(), self.store.clock.replace(year=self.store.clock.year + 1)
        self.pipeline.on_evaluate = change_owner
        await self.worker.tick()
        self.assertEqual(self.store.jobs[job_id].record.state, JobState.ANALYZING)
        self.assertNotIn(job_id, self.store.results)
        self.assertEqual(self.pipeline.persist_calls, 0)

    async def test_heartbeat_loss_cancels_wait_and_discards_result(self):
        job_id = self.create()
        cancelled = asyncio.Event()
        async def wait(job, snapshot):
            self.store.leases[job_id] = uuid4(), self.store.clock.replace(year=self.store.clock.year + 1)
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        self.pipeline.on_evaluate = wait
        worker = self.make_worker(replace(self.settings, renew_seconds=0.01))
        await asyncio.wait_for(worker.tick(), 1)
        self.assertTrue(cancelled.is_set())
        self.assertNotIn(job_id, self.store.results)

    async def test_result_write_and_job_finalization_rollback_together(self):
        for invalid in (False, True):
            job_id = self.create()
            self.pipeline.persist_failure = not invalid
            self.pipeline.invalid_outcome = invalid
            await self.worker.tick()
            self.assertEqual(self.store.jobs[job_id].record.state, JobState.FAILED)
            self.assertNotIn(job_id, self.store.results)
            self.assertIsNone(self.store.jobs[job_id].record.anomaly_result_id)

    async def test_shutdown_leaves_lease_and_restart_reuses_snapshot(self):
        job_id = self.create()
        started = asyncio.Event()
        async def wait(job, snapshot):
            started.set()
            await asyncio.Event().wait()
        self.pipeline.on_evaluate = wait
        task = asyncio.create_task(self.worker.run(asyncio.Event()))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        frozen = deepcopy(self.store.jobs[job_id].snapshot)
        self.assertIn(job_id, self.store.leases)
        self.store.advance(121)
        replacement = Pipeline(self.store)
        replacement_worker = self.make_worker(pipeline=replacement)
        self.assertFalse(await replacement_worker.tick())
        self.store.advance(2)
        await replacement_worker.tick()
        self.assertEqual(replacement.prepare_calls, 0)
        self.assertEqual(replacement.inputs[0], frozen)
        self.assertEqual(self.store.jobs[job_id].record.state, JobState.COMPLETED)

    async def test_expired_sans_analysis_requires_reconciliation(self):
        job_id = self.create("sans")
        with self.store.transaction() as repo:
            claim = repo.claim_next_job(120)
            snapshot = {"preflight": ["fixture"]}
            repo.save_input_snapshot(job_id, claim.lease_token, snapshot, snapshot_hash(snapshot))
        self.store.advance(121)
        await self.worker.tick()
        self.assertEqual(self.store.jobs[job_id].record.state, JobState.FAILED)
        self.assertEqual(self.store.jobs[job_id].record.error_code, "SANS_RECONCILIATION_REQUIRED")
        self.assertEqual(self.pipeline.evaluate_calls, 0)

    async def test_corrupted_snapshot_hash_is_rejected(self):
        job_id = self.create()
        self.store.mark_failed(job_id, {"value": "frozen"}, "wrong")
        self.service.retry(self.user, job_id)
        await self.worker.tick()
        self.assertEqual(self.store.jobs[job_id].record.error_code, "INPUT_SNAPSHOT_INVALID")
        self.assertEqual(self.pipeline.evaluate_calls, 0)

    async def test_two_workers_do_not_process_same_job(self):
        job_id = self.create()
        other = self.make_worker()
        await asyncio.gather(self.worker.tick(), other.tick())
        self.assertEqual(self.pipeline.evaluate_calls, 1)
        self.assertEqual(self.pipeline.persist_calls, 1)
        self.assertEqual(self.store.jobs[job_id].record.state, JobState.COMPLETED)

    async def test_expired_lease_cannot_be_renewed_or_finalized(self):
        self.create()
        with self.store.transaction() as repo:
            claim = repo.claim_next_job(120)
        self.store.advance(120)
        with self.store.transaction() as repo:
            self.assertFalse(repo.renew_job_lease(claim.job.job_id, claim.lease_token, 120))
            with self.assertRaises(LeaseLost):
                repo.finalize_job(claim.job.job_id, claim.lease_token, JobOutcome(state="FAILED"))

    async def test_stop_empty_queue_without_busy_loop(self):
        stop = asyncio.Event()
        task = asyncio.create_task(self.worker.run(stop))
        await asyncio.sleep(0.02)
        stop.set()
        await asyncio.wait_for(task, 1)

    async def test_heartbeat_renews_while_provider_is_waiting(self):
        job_id = self.create()
        async def wait_for_renewal(job, snapshot):
            count = self.store.renewals
            while self.store.renewals == count:
                await asyncio.sleep(0.005)
        self.pipeline.on_evaluate = wait_for_renewal
        await asyncio.wait_for(self.make_worker(replace(self.settings, renew_seconds=0.01)).tick(), 1)
        self.assertEqual(self.store.jobs[job_id].record.state, JobState.COMPLETED)
        self.assertGreaterEqual(self.store.renewals, 3)

    async def test_exhausted_restart_does_not_call_provider_again(self):
        job_id = self.create()
        with self.store.transaction() as repo:
            repo.claim_next_job(120)
        stored = self.store.jobs[job_id]
        stored.record = stored.record.model_copy(update={"attempts": 2})
        self.store.advance(121)
        await self.worker.tick()
        self.assertEqual(stored.record.state, JobState.FAILED)
        self.assertEqual(self.pipeline.evaluate_calls, 0)

    async def test_disabled_automatic_retry_does_not_requeue(self):
        job_id = self.create()
        self.pipeline.actions = [TransientModelError()]
        await self.make_worker(replace(self.settings, automatic_retries=0)).tick()
        self.assertEqual(self.store.jobs[job_id].record.state, JobState.FAILED)
        self.assertEqual(self.pipeline.evaluate_calls, 1)

    async def test_preparation_failure_does_not_call_provider(self):
        job_id = self.create()
        async def broken_prepare(job):
            raise RuntimeError("PRIVATE INPUT")
        self.pipeline.prepare = broken_prepare
        await self.worker.tick()
        self.assertEqual(self.store.jobs[job_id].record.error_code, "INPUT_PREPARATION_FAILED")
        self.assertEqual(self.pipeline.evaluate_calls, 0)

    async def test_non_json_input_is_not_sent_to_provider(self):
        job_id = self.create()
        async def invalid_prepare(job):
            return {"bad_number": float("nan")}
        self.pipeline.prepare = invalid_prepare
        await self.worker.tick()
        self.assertEqual(self.store.jobs[job_id].record.error_code, "INPUT_SNAPSHOT_INVALID")
        self.assertEqual(self.pipeline.evaluate_calls, 0)

    async def test_sans_jobs_for_same_astronaut_are_serialized(self):
        first, second = self.create("sans"), self.create("sans")
        entered, release = asyncio.Event(), asyncio.Event()
        async def hold(job, snapshot):
            entered.set()
            await release.wait()
        self.pipeline.on_evaluate = hold
        task = asyncio.create_task(self.worker.tick())
        await asyncio.wait_for(entered.wait(), 1)
        self.assertFalse(await self.make_worker().tick())
        release.set()
        await task
        self.pipeline.on_evaluate = None
        await self.worker.tick()
        self.assertEqual(self.store.jobs[first].record.state, JobState.COMPLETED)
        self.assertEqual(self.store.jobs[second].record.state, JobState.COMPLETED)

    async def test_unevaluated_completion_has_no_fabricated_result(self):
        job_id = self.create()
        def insufficient(repo, job, result):
            return JobOutcome(state="COMPLETED", evaluation_status="insufficient_data",
                              outcome={"reason_code": "SOURCE_DATA_MISSING"})
        self.pipeline.persist = insufficient
        await self.worker.tick()
        stored = self.store.jobs[job_id]
        self.assertEqual(stored.record.state, JobState.COMPLETED)
        self.assertEqual(stored.record.evaluation_status, "insufficient_data")
        self.assertIsNone(stored.record.anomaly_result_id)
        self.assertNotIn(job_id, self.store.results)

    def test_configuration_requires_two_pipelines_and_bounded_retry(self):
        with self.assertRaises(ValueError):
            AnalysisWorker(self.store.transaction, {}, self.settings)
        for settings in ({"automatic_retries": 2}, {"renew_seconds": 120}, {"poll_seconds": 0}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                replace(self.settings, **settings)
