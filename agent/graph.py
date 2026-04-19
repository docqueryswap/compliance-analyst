from langgraph.graph import StateGraph, END
from typing import TypedDict, List
from agent.nodes.planner import planner_node
from agent.nodes.retriever import retriever_node
from agent.nodes.executor import executor_node


class ComplianceState(TypedDict):
    document_text: str
    doc_id: str
    document_type: str
    plan: List[str]
    retrieved_context: List[str]
    draft_report: str


def build_compliance_graph():
    workflow = StateGraph(ComplianceState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("executor", executor_node)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "retriever")
    workflow.add_edge("retriever", "executor")
    workflow.add_edge("executor", END)

    return workflow.compile()