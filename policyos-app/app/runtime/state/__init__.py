"""Public immutable runtime execution-state API."""

from app.runtime.state.domain import (
    RuntimeExecutionState,
    RuntimeExecutionStateRecord,
    RuntimeStateContractVersion,
    RuntimeStateScope,
    RuntimeStateTransitionDecision,
    RuntimeStateTransitionRecord,
    RuntimeStateTransitionRequest,
    RuntimeTransitionDecisionStatus,
)
from app.runtime.state.errors import (
    RuntimeStateAuthorityError,
    RuntimeStateClassificationError,
    RuntimeStateError,
    RuntimeStateHistoryError,
    RuntimeStateIdempotencyError,
    RuntimeStateRevisionError,
    RuntimeStateScopeError,
    RuntimeStateTerminalError,
    RuntimeStateTimestampError,
    RuntimeStateTransitionError,
)
from app.runtime.state.validation import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    build_runtime_state_transition_record,
    validate_runtime_execution_state_record,
    validate_runtime_state_transition_edge,
    validate_runtime_state_transition_request,
)

__all__ = (
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATES",
    "RuntimeExecutionState",
    "RuntimeExecutionStateRecord",
    "RuntimeStateAuthorityError",
    "RuntimeStateClassificationError",
    "RuntimeStateContractVersion",
    "RuntimeStateError",
    "RuntimeStateHistoryError",
    "RuntimeStateIdempotencyError",
    "RuntimeStateRevisionError",
    "RuntimeStateScope",
    "RuntimeStateScopeError",
    "RuntimeStateTerminalError",
    "RuntimeStateTimestampError",
    "RuntimeStateTransitionDecision",
    "RuntimeStateTransitionError",
    "RuntimeStateTransitionRecord",
    "RuntimeStateTransitionRequest",
    "RuntimeTransitionDecisionStatus",
    "build_runtime_state_transition_record",
    "validate_runtime_execution_state_record",
    "validate_runtime_state_transition_edge",
    "validate_runtime_state_transition_request",
)
