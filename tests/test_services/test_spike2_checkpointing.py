"""
Unit & Integration Tests for Spike 2: LangGraph Checkpointing, Interrupt & State Recovery
Owner: TechLead (cuongtv_02560)
"""

from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from src.orchestrator.checkpointer import CheckpointManager


class SampleWorkflowState(TypedDict):
    step: int
    customer_name: str
    consent_granted: bool
    status: str


def node_discovery(state: SampleWorkflowState) -> dict:
    return {
        "step": state["step"] + 1,
        "status": "DISCOVERY_COMPLETED",
    }


def node_await_consent(state: SampleWorkflowState) -> dict:
    # Trigger Human-in-the-loop (HITL) interrupt
    user_response = interrupt("WAITING_FOR_HANDOFF_CONSENT")
    consent = False
    if isinstance(user_response, dict):
        consent = user_response.get("consent_granted", False)
    return {
        "step": state["step"] + 1,
        "consent_granted": consent,
        "status": "CONSENT_PROCESSED",
    }


def node_finalize(state: SampleWorkflowState) -> dict:
    return {
        "step": state["step"] + 1,
        "status": "COMPLETED",
    }


def build_test_graph(checkpointer: MemorySaver):
    builder = StateGraph(SampleWorkflowState)
    builder.add_node("discovery", node_discovery)
    builder.add_node("await_consent", node_await_consent)
    builder.add_node("finalize", node_finalize)

    builder.add_edge(START, "discovery")
    builder.add_edge("discovery", "await_consent")
    builder.add_edge("await_consent", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)


def test_thread_config_namespace_isolation() -> None:
    """Verify thread ID and namespace format isolation."""
    pre_sales_config = CheckpointManager.build_thread_config(
        namespace="PRE_SALES",
        tenant_id="tenant_vland",
        entity_id="session_123",
    )
    assert pre_sales_config["metadata"]["namespace"] == "PRE_SALES"
    assert pre_sales_config["configurable"]["thread_id"] == "presales:tenant_vland:session_123"

    quote_config = CheckpointManager.build_thread_config(
        namespace="DEFAULT",
        tenant_id="tenant_vland",
        entity_id="quote_999",
    )
    assert quote_config["metadata"]["namespace"] == "DEFAULT"
    assert quote_config["configurable"]["thread_id"] == "quote:tenant_vland:quote_999"


@pytest.mark.asyncio
async def test_langgraph_interrupt_and_resume() -> None:
    """
    Test StateGraph pauses at HITL interrupt and resumes accurately with Command(resume=...).
    """
    checkpointer = MemorySaver()
    graph = build_test_graph(checkpointer)

    thread_config = CheckpointManager.build_thread_config(
        namespace="PRE_SALES",
        tenant_id="vland",
        entity_id="sess_001",
    )

    initial_input: SampleWorkflowState = {
        "step": 0,
        "customer_name": "Nguyen Van A",
        "consent_granted": False,
        "status": "INITIAL",
    }

    # 1. Run until interrupt
    await graph.ainvoke(initial_input, config=thread_config)

    # In LangGraph with interrupt, graph pauses and exposes the interrupt value
    state_snapshot = await graph.aget_state(thread_config)
    assert len(state_snapshot.tasks) > 0
    # Next node should be waiting at await_consent
    assert any(t.name == "await_consent" for t in state_snapshot.tasks)

    # 2. Resume graph with user consent command
    resume_command = Command(resume={"consent_granted": True})
    final_result = await graph.ainvoke(resume_command, config=thread_config)

    assert final_result["consent_granted"] is True
    assert final_result["status"] == "COMPLETED"
    assert final_result["step"] == 3

    # Checkpoint state is now finalized
    final_snapshot = await graph.aget_state(thread_config)
    assert len(final_snapshot.tasks) == 0


@pytest.mark.asyncio
async def test_langgraph_process_recovery_from_checkpoint() -> None:
    """
    Test that a new graph instance reading from same checkpointer
    can retrieve state without repeating completed nodes.
    """
    shared_checkpointer = MemorySaver()
    graph_instance_1 = build_test_graph(shared_checkpointer)

    thread_config = CheckpointManager.build_thread_config(
        namespace="DEFAULT",
        tenant_id="vland",
        entity_id="quote_456",
    )

    initial_input: SampleWorkflowState = {
        "step": 0,
        "customer_name": "Tran Thi B",
        "consent_granted": False,
        "status": "STARTED",
    }

    # Run instance 1 to interrupt
    await graph_instance_1.ainvoke(initial_input, config=thread_config)

    # Simulate crash by creating completely fresh graph instance
    graph_instance_2 = build_test_graph(shared_checkpointer)

    # Inspect state from instance 2
    recovered_state = await graph_instance_2.aget_state(thread_config)
    assert recovered_state.values["customer_name"] == "Tran Thi B"
    assert recovered_state.values["status"] == "DISCOVERY_COMPLETED"
    assert recovered_state.values["step"] == 1

    # Resume with instance 2
    resume_cmd = Command(resume={"consent_granted": True})
    final_output = await graph_instance_2.ainvoke(resume_cmd, config=thread_config)

    assert final_output["status"] == "COMPLETED"
    assert final_output["step"] == 3
