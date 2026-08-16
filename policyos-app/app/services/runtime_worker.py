"""Production CP10 Runtime Worker application sequencing."""

import asyncio
from dataclasses import dataclass

from app.runtime.ports import (
    RuntimeEffectLifecycleCommitDisposition,
    validate_runtime_effect_lifecycle_commit_result,
)
from app.services.runtime_worker_contracts import (
    RuntimeWorkerConfiguration,
    RuntimeWorkerConfigurationBinding,
    RuntimeWorkerInterruptibleWaitRequest,
    RuntimeWorkerOperationalFailureStage,
    RuntimeWorkerPollCycleDisposition,
    RuntimeWorkerPollCycleResultProductionRequest,
    RuntimeWorkerPollIterationDisposition,
    RuntimeWorkerPollIterationResultProductionRequest,
    RuntimeWorkerPreInvocationDisposition,
    RuntimeWorkerShutdownDisposition,
)
from app.services.runtime_worker_protocols import (
    RuntimeWorkerOperationalCapabilityFailure,
    RuntimeWorkerPreInvocationRevalidationRequest,
    RuntimeWorkerProductionDependencyBundle,
)
from app.services.runtime_worker_validation import (
    validate_runtime_worker_configuration_binding,
    validate_runtime_worker_poll_cycle_request,
    validate_runtime_worker_poll_cycle_result,
    validate_runtime_worker_poll_iteration_request,
    validate_runtime_worker_poll_iteration_result,
    validate_runtime_worker_pre_invocation_revalidation_result,
    validate_runtime_worker_prepared_delivery,
    validate_runtime_worker_prepared_delivery_request,
    validate_runtime_worker_result_completion,
    validate_runtime_worker_shutdown_observation_request_preparation,
    validate_runtime_worker_shutdown_observation_result,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeWorkerService:
    """Sequence governed Worker capabilities without acquiring Runtime authority."""

    dependencies: RuntimeWorkerProductionDependencyBundle

    async def _observe_shutdown(self, configuration, binding):
        async with self.dependencies.shutdown_observation_request_preparation_factory() as source:
            request = await source.prepare(configuration, binding)
        validate_runtime_worker_shutdown_observation_request_preparation(
            configuration, binding, request
        )
        result = await self.dependencies.shutdown_observation_factory().observe(request)
        return validate_runtime_worker_shutdown_observation_result(request, result)

    async def _produce_iteration(self, request, disposition, count, stage):
        production = RuntimeWorkerPollIterationResultProductionRequest(
            iteration_request=request,
            disposition=disposition,
            selected_candidate_count=count,
            failure_stage=stage,
        )
        async with self.dependencies.poll_iteration_result_production_factory() as producer:
            result = await producer.produce(production)
        return validate_runtime_worker_poll_iteration_result(request, result)

    async def _produce_cycle(self, request, disposition, visited, count, stage):
        production = RuntimeWorkerPollCycleResultProductionRequest(
            cycle_request=request,
            disposition=disposition,
            visited_assignment_count=visited,
            selected_candidate_count=count,
            failure_stage=stage,
        )
        async with self.dependencies.poll_cycle_result_production_factory() as producer:
            result = await producer.produce(production)
        return validate_runtime_worker_poll_cycle_result(request, result)

    async def _run_candidate(self, iteration, candidate):
        try:
            async with self.dependencies.prepared_delivery_request_preparation_factory() as source:
                request = await source.prepare(iteration, candidate)
            validate_runtime_worker_prepared_delivery_request(request)
            async with self.dependencies.prepared_delivery_factory() as source:
                prepared = await source.prepare(request)
            validate_runtime_worker_prepared_delivery(request, prepared)
        except RuntimeWorkerOperationalCapabilityFailure:
            return None

        try:
            async with self.dependencies.claim_factory() as capability:
                claim_result = await capability.claim(prepared.claim_request)
        except RuntimeWorkerOperationalCapabilityFailure:
            return None
        validate_runtime_effect_lifecycle_commit_result(prepared.claim_request, claim_result)
        if claim_result.disposition is not RuntimeEffectLifecycleCommitDisposition.APPENDED:
            return None

        try:
            async with self.dependencies.lifecycle_append_factory() as capability:
                delivering_result = await capability.append(prepared.delivering_append_request)
        except RuntimeWorkerOperationalCapabilityFailure:
            return None
        validate_runtime_effect_lifecycle_commit_result(
            prepared.delivering_append_request, delivering_result
        )
        if delivering_result.disposition is not RuntimeEffectLifecycleCommitDisposition.APPENDED:
            return None

        revalidation_request = RuntimeWorkerPreInvocationRevalidationRequest(
            prepared_delivery=prepared,
            delivering_result=delivering_result,
        )
        try:
            async with self.dependencies.pre_invocation_revalidation_factory() as capability:
                revalidation = await capability.revalidate(revalidation_request)
            validate_runtime_worker_pre_invocation_revalidation_result(
                revalidation_request, revalidation
            )
        except RuntimeWorkerOperationalCapabilityFailure:
            return None
        if revalidation.disposition is RuntimeWorkerPreInvocationDisposition.SHUTDOWN_BLOCKED:
            return None
        if revalidation.disposition is RuntimeWorkerPreInvocationDisposition.DEFINITELY_NOT_INVOKED:
            try:
                async with self.dependencies.lifecycle_append_factory() as capability:
                    append_result = await capability.append(revalidation.append_request)
                validate_runtime_effect_lifecycle_commit_result(
                    revalidation.append_request, append_result
                )
            except RuntimeWorkerOperationalCapabilityFailure:
                return None
            return None

        try:
            async with self.dependencies.delivery_factory() as delivery:
                result = await delivery.deliver(prepared.invocation)
        except RuntimeWorkerOperationalCapabilityFailure:
            return None
        try:
            append_request = await prepared.result_completion.complete(result)
            validate_runtime_worker_result_completion(prepared, result, append_request)
        except RuntimeWorkerOperationalCapabilityFailure:
            return None
        try:
            async with self.dependencies.lifecycle_append_factory() as capability:
                append_result = await capability.append(append_request)
            validate_runtime_effect_lifecycle_commit_result(append_request, append_result)
        except RuntimeWorkerOperationalCapabilityFailure:
            return None
        return None

    @staticmethod
    def _raise_completed_failures(completed: set[asyncio.Task[None]]) -> None:
        while completed:
            task = completed.pop()
            if not task.cancelled():
                task.result()

    async def _drain(self, tasks, shutdown) -> None:
        pending = {task for task in tasks if not task.done()}
        if not pending:
            return
        budget = max(
            0.0,
            (shutdown.drain_deadline - shutdown.observed_clock_reading.observed_at).total_seconds(),
        )
        _, pending = await asyncio.wait(pending, timeout=budget)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def run(
        self,
        configuration: RuntimeWorkerConfiguration,
        configuration_binding: RuntimeWorkerConfigurationBinding,
    ) -> None:
        validate_runtime_worker_configuration_binding(configuration, configuration_binding)
        semaphore = asyncio.Semaphore(configuration.maximum_concurrency)
        admitted: set[asyncio.Task[None]] = set()
        completed: set[asyncio.Task[None]] = set()
        stopping = False

        async def admitted_candidate(iteration, candidate):
            async with semaphore:
                if stopping:
                    return None
                await self._run_candidate(iteration, candidate)
                return None

        def candidate_completed(task: asyncio.Task[None]) -> None:
            admitted.discard(task)
            completed.add(task)

        try:
            while True:
                try:
                    async with self.dependencies.poll_cycle_request_preparation_factory() as source:
                        cycle = await source.prepare(configuration, configuration_binding)
                    validate_runtime_worker_poll_cycle_request(cycle)
                except RuntimeWorkerOperationalCapabilityFailure:
                    raise

                try:
                    shutdown = await self._observe_shutdown(configuration, configuration_binding)
                except RuntimeWorkerOperationalCapabilityFailure:
                    await self._produce_cycle(
                        cycle,
                        RuntimeWorkerPollCycleDisposition.OPERATIONAL_FAILURE,
                        0,
                        0,
                        RuntimeWorkerOperationalFailureStage.SHUTDOWN_OBSERVATION,
                    )
                    continue
                if shutdown.disposition is RuntimeWorkerShutdownDisposition.SHUTDOWN_REQUESTED:
                    stopping = True
                    await self._drain(admitted, shutdown)
                    self._raise_completed_failures(completed)
                    return

                visited = 0
                selected_count = 0
                cycle_disposition = RuntimeWorkerPollCycleDisposition.COMPLETED
                cycle_stage = None
                for position, assignment in enumerate(configuration.assignments, start=1):
                    try:
                        async with (
                            self.dependencies.poll_iteration_request_preparation_factory()
                        ) as source:
                            iteration = await source.prepare(cycle, position, assignment)
                        validate_runtime_worker_poll_iteration_request(iteration)
                    except RuntimeWorkerOperationalCapabilityFailure:
                        cycle_disposition = RuntimeWorkerPollCycleDisposition.OPERATIONAL_FAILURE
                        cycle_stage = RuntimeWorkerOperationalFailureStage.REQUEST_PREPARATION
                        break
                    visited += 1
                    try:
                        async with self.dependencies.due_selection_factory() as selector:
                            candidates = await selector.select_due(iteration.due_selection_request)
                    except RuntimeWorkerOperationalCapabilityFailure:
                        await self._produce_iteration(
                            iteration,
                            RuntimeWorkerPollIterationDisposition.OPERATIONAL_FAILURE,
                            0,
                            RuntimeWorkerOperationalFailureStage.DUE_SELECTION,
                        )
                        cycle_disposition = RuntimeWorkerPollCycleDisposition.OPERATIONAL_FAILURE
                        cycle_stage = RuntimeWorkerOperationalFailureStage.DUE_SELECTION
                        break
                    selected = len(candidates)
                    disposition = (
                        RuntimeWorkerPollIterationDisposition.SELECTED
                        if selected
                        else RuntimeWorkerPollIterationDisposition.EMPTY
                    )
                    await self._produce_iteration(iteration, disposition, selected, None)
                    selected_count += selected
                    for candidate in candidates:
                        task = asyncio.create_task(admitted_candidate(iteration, candidate))
                        admitted.add(task)
                        task.add_done_callback(candidate_completed)

                await self._produce_cycle(
                    cycle,
                    cycle_disposition,
                    visited,
                    selected_count,
                    cycle_stage,
                )
                self._raise_completed_failures(completed)
                shutdown = await self._observe_shutdown(configuration, configuration_binding)
                if shutdown.disposition is RuntimeWorkerShutdownDisposition.SHUTDOWN_REQUESTED:
                    stopping = True
                    await self._drain(admitted, shutdown)
                    self._raise_completed_failures(completed)
                    return
                wait_request = RuntimeWorkerInterruptibleWaitRequest(
                    configuration_binding=configuration_binding,
                    poll_interval_milliseconds=configuration.poll_interval_milliseconds,
                )
                await self.dependencies.interruptible_wait_factory().wait(wait_request)
                self._raise_completed_failures(completed)
                shutdown = await self._observe_shutdown(configuration, configuration_binding)
                if shutdown.disposition is RuntimeWorkerShutdownDisposition.SHUTDOWN_REQUESTED:
                    stopping = True
                    await self._drain(admitted, shutdown)
                    self._raise_completed_failures(completed)
                    return
                self._raise_completed_failures(completed)
        finally:
            pending = {task for task in admitted if not task.done()}
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            for task in completed:
                if not task.cancelled():
                    task.exception()


__all__ = ("RuntimeWorkerService",)
