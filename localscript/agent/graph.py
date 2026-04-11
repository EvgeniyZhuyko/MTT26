"""LangGraph StateGraph — routes between Analyst, Generator, and Critic."""

from langgraph.graph import END, StateGraph

from localscript.agent.nodes.analyst import analyst_node
from localscript.agent.nodes.critic import critic_node
from localscript.agent.nodes.generator import generator_node
from localscript.agent.state import AgentState


def build_graph(max_iter: int = 3):
    """Build and compile the agent graph.

    Graph topology:
        START → analyst → generator → critic
                                        │
                          ┌─────────────┤
                          │ done or      │ not done and
                          │ iter ≥ max   │ iter < max
                          ▼             ▼
                         END        generator (retry)

    Args:
        max_iter: Maximum number of generator → critic cycles before giving up.

    Returns:
        A compiled LangGraph runnable.
    """
    graph = StateGraph(AgentState)

    graph.add_node("analyst", analyst_node)
    graph.add_node("generator", generator_node)
    graph.add_node("critic", critic_node)

    graph.set_entry_point("analyst")
    graph.add_edge("analyst", "generator")
    graph.add_edge("generator", "critic")

    def _route_critic(state: AgentState) -> str:
        if state["done"] or state["iterations"] >= max_iter:
            return "end"
        return "retry"

    graph.add_conditional_edges(
        "critic",
        _route_critic,
        {"end": END, "retry": "generator"},
    )

    return graph.compile()
