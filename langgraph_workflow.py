# langgraph_workflow.py

from langgraph.graph import StateGraph
from typing import TypedDict
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
import os

# Set your OpenAI key
os.environ["OPENAI_API_KEY"] = "your-openai-key"

llm = ChatOpenAI(model_name="gpt-4-turbo", temperature=0.2)

# ✅ Define State Schema with new 'frd_pattern'
class FRDState(TypedDict):
    existing_brd: str
    existing_frd: str
    new_brd: str
    user_notes: str
    new_frd: str
    frd_pattern: str

# ✅ Node: Extract FRD structural and formatting pattern
def extract_frd_pattern_node(state: FRDState) -> FRDState:
    existing_frd_summary = state["existing_frd"]

    pattern_prompt = f"""
You are a professional technical writer.

Analyze the FRD summary below and extract the following:
1. Common section headers or titles.
2. Title/subtitle formatting styles (e.g., numbering, bold).
3. Tone and language (e.g., formal/informal, active/passive).
4. Formatting styles (e.g., bullet points, numbered lists, indentation).

FRD Summary:
{existing_frd_summary}
"""

    result = llm([
        SystemMessage(content="Extract structural and language patterns from an FRD."),
        HumanMessage(content=pattern_prompt)
    ])

    return {
        **state,
        "frd_pattern": result.content
    }

# ✅ Node: Generate new FRD using the pattern
def generate_frd_node(state: FRDState) -> FRDState:
    existing_brd_summary = state["existing_brd"]
    existing_frd_summary = state["existing_frd"]
    new_brd_summary = state["new_brd"]
    user_notes = state.get("user_notes", "")
    frd_pattern = state.get("frd_pattern", "")

    system_prompt = (
        "You are an expert business analyst. Generate a well-structured and detailed FRD "
        "based on the new BRD. Match the format and writing style of the existing FRD."
    )

    user_prompt = f"""
STRUCTURE AND STYLE TO FOLLOW:
{frd_pattern}

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

    return {
        **state,
        "new_frd": result.content
    }

# ✅ Build LangGraph
def build_frd_graph():
    builder = StateGraph(FRDState)
    builder.add_node("extract_pattern", extract_frd_pattern_node)
    builder.add_node("generate_frd", generate_frd_node)

    builder.set_entry_point("extract_pattern")
    builder.add_edge("extract_pattern", "generate_frd")
    builder.set_finish_point("generate_frd")

    return builder.compile()
