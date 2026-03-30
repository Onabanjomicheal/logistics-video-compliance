"""
This module defines the DAG : Directed Acyclic Graph that orchestrates the  videdo compliance. 
It connects the nodes using the LangGraph.

START -> observe_scene_node -> audit_compliance_node -> END
"""

from langgraph.graph import StateGraph, START, END
from backend.src.graph.state import VideoAuditState

from backend.src.graph.nodes import (
    observe_scene_node,
    audit_compliance_node,
)

def create_graph():
    """
    Constructs and complies the LangGraph workflow
    Returns:
    Complied graph: runnable graph object for execution
    """

    # Initialize the graph with the defined state schema
    workflow = StateGraph(VideoAuditState)
    # add the nodes
    workflow.add_node("observer", observe_scene_node)
    workflow.add_node("auditor", audit_compliance_node)
    # define the entry point : START -> observer
    workflow.add_edge(START, "observer")
    # observer -> auditor
    workflow.add_edge("observer", "auditor")
    # define the exit point : auditor -> END
    workflow.add_edge("auditor", END)
    # compile the graph
    app = workflow.compile()
    return app

# expose this runnable app
app = create_graph()
