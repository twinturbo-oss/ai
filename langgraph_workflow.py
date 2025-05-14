# langgraph_workflow.py

from langgraph.graph import StateGraph
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
import os

# Set your OpenAI key
os.environ["OPENAI_API_KEY"] = "your-openai-key"

llm = ChatOpenAI(model_name="gpt-4-turbo", temperature=0.2)

# Node to generate the new FRD
def generate_frd_node(state):
    existing_brd_summary = state["existing_brd"]
    existing_frd_summary = state["existing_frd"]
    new_brd_summary = state["new_brd"]
    user_notes = state.get("user_notes", "")

    system_prompt = (
        "You are an expert business analyst. "
        "Generate a structured and detailed new FRD based on the new BRD, using the format of the existing FRD."
    )

    user_prompt = f"""
EXISTING BRD SUMMARY:
{existing_brd_summary}

EXISTING FRD SUMMARY:
{existing_frd_summary}

NEW BRD SUMMARY:
{new_brd_summary}

USER NOTES (if any):
{user_notes}
"""

    result = llm([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])

    return {"new_frd": result.content}

# Build LangGraph
def build_frd_graph():
    builder = StateGraph()
    builder.add_node("generate_frd", generate_frd_node)
    builder.set_entry_point("generate_frd")
    builder.set_finish_point("generate_frd")
    return builder.compile()
