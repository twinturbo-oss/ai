import debugpy
import sys
import os
import streamlit as st
from docx import Document
from pptx import Presentation
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from openai import OpenAI
from httpx import Client
from pathlib import Path
from langgraph.graph import StateGraph
from typing import TypedDict
from langchainNodes import build_frd_graph
from getts_utils import parse_docx_sections, format_frd_text

# Setup debugger
try:
    debugpy.listen(5678)
    print("Waiting for debugger attach")
except RuntimeError as e:
    print(f"{e}")

debugpy.wait_for_client()

# Load environment variable for API key
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")

# Setup secure verification for HTTP client


# Initialize HTTP and OpenAI clients
http_client = Client(verify=verify)
client = OpenAI(
    base_url="/openai/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=http_client
)


# Constants
MODEL = "03-mini"
MAX_TOKENS_PER_CHUNK = 2000
SUMMARY_MAX_TOKENS = 800

SECTIONS = [
    "introduction",
    "scenario"
]

# Utility functions
def read_docx(uploaded_file):
    doc = Document(uploaded_file)
    return [para.text.strip() for para in doc.paragraphs if para.text.strip()]

def chunk_paragraphs(paragraphs, max_tokens=MAX_TOKENS_PER_CHUNK):
    chunks, current_chunk, current_tokens = [], [], 0
    for para in paragraphs:
        tokens = len(para.split())
        if current_tokens + tokens > max_tokens:
            chunks.append("\n".join(current_chunk))
            current_chunk, current_tokens = [para], tokens
        else:
            current_chunk.append(para)
            current_tokens += tokens
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    return chunks

def summarize_chunk_safe(chunk, retry_count=3):
    for attempt in range(retry_count):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "Summarize the following document chunk clearly, retaining important requirements, features, and key points."},
                    {"role": "user", "content": chunk}
                ],
                max_completion_tokens=SUMMARY_MAX_TOKENS
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error summarizing chunk (attempt {attempt + 1}): {e}")
            time.sleep(2)
    return "[Error: Failed to summarize this chunk.]"

def summarize_document(paragraphs):
    chunks = chunk_paragraphs(paragraphs)
    summaries = [""] * len(chunks)
    progress_bar = st.progress(0)
    total = len(chunks)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(summarize_chunk_safe, chunk): i for i, chunk in enumerate(chunks)}
        completed = 0
        for future in as_completed(futures):
            i = futures[future]
            try:
                summaries[i] = future.result()
            except Exception as e:
                summaries[i] = "[Error]"
            completed += 1
            progress_bar.progress(completed / total)

    progress_bar.empty()
    return "\n\n".join(summaries)

# Define FRDState type
class FRDState(TypedDict):
    existing_brd: str
    existing_frd: str
    new_brd: str
    user_notes: str
    new_frd: str
    frd_pattern: str

# Streamlit UI Setup
st.set_page_config(page_title="GETTS", layout="wide")
st.sidebar.title("GETTS")
st.sidebar.markdown("---")
selected_topic = st.sidebar.radio("Select Functionality", ["Generate FRD", "Generate Test Scenario", "Generate Mockup", "Generate Excel File"], index=0)
st.title("GETTS")

# Initialize all session state variables
if 'frd_generated' not in st.session_state:
    st.session_state.frd_generated = False
if 'previous_brd' not in st.session_state:
    st.session_state.previous_brd = None
if 'reference_brd_full' not in st.session_state:
    st.session_state.reference_brd_full = ""
if 'reference_frd_full' not in st.session_state:
    st.session_state.reference_frd_full = ""
if 'new_brd_full' not in st.session_state:
    st.session_state.new_brd_full = ""
if 'new_frd_text' not in st.session_state:
    st.session_state.new_frd_text = ""
if 'user_notes' not in st.session_state:
    st.session_state.user_notes = ""

if selected_topic == "Generate FRD":
    st.header("FRD Generator")
    st.markdown("BRD and FRD is pre-loaded")

    docs_path = Path("docs/full_data")
    existing_brd_file = docs_path / "Bunching_Orders_Rewriting_BRD(in progress).docx"
    existing_frd_file = docs_path / "BO Functional Requirements Document_signOffVersion.docx"

    new_brd_file = st.file_uploader("Upload New BRD (.docx)", type="docx", key="brd_uploader")
    current_brd = new_brd_file.name if new_brd_file else None

    if st.session_state.previous_brd != current_brd:
        st.session_state.frd_generated = False
        st.session_state.previous_brd = current_brd

    if st.button("Generate New FRD", type="primary", key="generate_frd"):
        try:
            with st.spinner("Summarizing documents..."):
                st.session_state.reference_brd_full = "\n\n".join(read_docx(existing_brd_file))
                st.session_state.reference_frd_full = "\n\n".join(read_docx(existing_frd_file))
                st.session_state.new_brd_full = "\n\n".join(read_docx(new_brd_file)) if new_brd_file else ""

            with st.spinner("Generating new FRD (this may take a minute)..."):
                final_graph = build_frd_graph(
                    SECTIONS,
                    reference_brd_full=st.session_state.reference_brd_full,
                    reference_frd_full=st.session_state.reference_frd_full,
                    new_brd_full=st.session_state.new_brd_full,
                    skip_scenario_refine=True
                )

                result = final_graph.invoke({
                    "brd": st.session_state.new_brd_full,
                    "section": "",
                    "analysis": "",
                    "generated": "",
                    "frd_frd": {}
                })

                st.session_state.new_frd_text = format_frd_text(result["full_frd"])
                st.session_state.frd_generated = True
                st.rerun()  # Force refresh to show the enhancement UI

        except Exception as e:
            st.error(f"Error generating FRD: {str(e)}")

    # Show enhancement UI only after generation
    if st.session_state.frd_generated:
        st.success("Base FRD generated successfully!")
        st.session_state.user_notes = st.text_area(
            "Enter your additional requirements or changes:",
            value=st.session_state.user_notes,
            key="user_notes"
        )

        if st.button("Enhance FRD", type="primary", key="enhance_frd"):
            if not st.session_state.user_notes.strip():
                st.warning("Please enter some changes before enhancing")
            else:
                try:
                    with st.spinner("Incorporating your changes (this may take a minute)..."):
                        # Create clear instructions for the LLM
                        enhancement_prompt = f"""
                        Please revise the existing FRD by intelligently incorporating these user-requested changes:
                        
                        USER REQUESTED CHANGES:
                        {st.session_state.user_notes}
                        
                        GUIDELINES:
                        1. Merge changes contextually where they belong
                        2. Maintain all existing valid content
                        3. Keep the professional FRD format
                        4. Add new sections only if needed
                        5. Return the complete revised FRD
                        """
                        
                        final_graph = build_frd_graph(
                            SECTIONS,
                            reference_brd_full=st.session_state.reference_brd_full,
                            reference_frd_full=st.session_state.reference_frd_full,
                            new_brd_full=st.session_state.new_brd_full,
                            skip_scenario_refine=True
                        )

                        result = final_graph.invoke({
                            "brd": st.session_state.new_brd_full,
                            "section": "",
                            "analysis": enhancement_prompt,
                            "generated": st.session_state.new_frd_text,
                            "frd_frd": {}
                        })

                        st.session_state.new_frd_text = format_frd_text(result["full_frd"])
                        st.session_state.user_notes = ""  # Clear notes after successful enhancement
                        st.success("FRD enhanced successfully!")
                        st.rerun()  # Refresh to show updated FRD

                except Exception as e:
                    st.error(f"Error enhancing FRD: {str(e)}")

        # Display the current FRD
        st.subheader("Current FRD Version")
        st.text_area("FRD Content", 
                    st.session_state.new_frd_text, 
                    height=400,
                    key="frd_display")
        
        st.download_button(
            "Download Current FRD",
            st.session_state.new_frd_text,
            file_name="enhanced_frd.txt",
            mime="text/plain"
        )

elif selected_topic == "Generate Test Scenario":
    st.header("Generate Test Scenario")
    st.info("Work in progress")

elif selected_topic == "Generate Mockup":
    st.header("Generate Mockup Data")
    st.info("Work in progress")

elif selected_topic == "Generate Excel File":
    st.header("Generate Excel File")
    st.info("Work in progress")

st.markdown("---")
