from langgraph.graph import StateGraph, END
from typing import TypedDict, List
from agent.nodes.planner import planner_node
from agent.nodes.retriever import retriever_node
from agent.nodes.executor import executor_node
from agent.nodes.critic import critic_node

class ComplianceState(TypedDict):
    document_text: str
    doc_id: str
    document_type: str      # ✅ Added
    plan: List[str]
    retrieved_context: List[str]
    draft_report: str
    passes_validation: bool
    critique: str
    final_report: str
    retry_count: int

def build_compliance_graph():
    workflow = StateGraph(ComplianceState)
    
    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("critic", critic_node)
    
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "retriever")
    workflow.add_edge("retriever", "executor")
    workflow.add_edge("executor", "critic")
    
    def should_continue(state: ComplianceState):
        if state.get("passes_validation", True):
            return END
        retry_count = state.get("retry_count", 0)
        if retry_count >= 2:
            return END
        state["retry_count"] = retry_count + 1
        return "executor"
    
    workflow.add_conditional_edges("critic", should_continue, {"executor": "executor", END: END})
    
    return workflow.compile()