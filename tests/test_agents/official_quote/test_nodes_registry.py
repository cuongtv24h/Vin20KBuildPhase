"""Khóa cấu trúc Official Quote StateGraph: đủ 23 node N-01 → N-20."""

import inspect

import pytest

from src.agents.official_quote.graph import build_official_quote_graph
from src.agents.official_quote.nodes import NODE_REGISTRY

EXPECTED_NODE_CODES = [
    "N-01", "N-02", "N-03", "N-04", "N-05", "N-06", "N-07", "N-08", "N-09",
    "N-10A", "N-10B", "N-11", "N-12", "N-13", "N-14A", "N-14B",
    "N-15", "N-16", "N-17", "N-18", "N-19A", "N-19B", "N-20",
]


def test_registry_contains_exactly_td43_nodes():
    assert list(NODE_REGISTRY.keys()) == EXPECTED_NODE_CODES
    assert len(NODE_REGISTRY) == 23


def test_all_nodes_are_async_callables():
    for code, fn in NODE_REGISTRY.items():
        assert callable(fn), code
        assert inspect.iscoroutinefunction(fn), f"{code} phải là async node"


def test_graph_builder_blocked_until_implemented():
    """C-01 chưa dựng edges — builder phải báo NotImplemented, không trả graph rỗng."""
    with pytest.raises(NotImplementedError):
        build_official_quote_graph()


@pytest.mark.asyncio
@pytest.mark.parametrize("code", EXPECTED_NODE_CODES)
async def test_skeleton_nodes_signal_not_implemented(code):
    """Scaffold chưa implement — node phải nói rõ điều đó thay vì im lặng."""
    with pytest.raises(NotImplementedError):
        await NODE_REGISTRY[code]({})
