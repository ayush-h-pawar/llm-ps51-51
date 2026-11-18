import csv
import hashlib
import io
import json
import os
from pathlib import Path
import streamlit as st
from core import DISCLAIMER, ReportError, analyse, read_report
from llm import LLMClient

st.set_page_config(page_title="Medical Report Explainer", page_icon="🧪", layout="wide")
st.markdown("""<style>
.stApp {background:#f6f8fb;} h1 {color:#123349;} [data-testid="stMetric"] {background:white;border:1px solid #dce5eb;border-radius:12px;padding:14px;}
[data-testid="stSidebar"] {background:#eaf1f5;} .block-container {max-width:1250px;padding-top:4rem;}
</style>""", unsafe_allow_html=True)
st.caption("PS 51  /  HEALTH & WELLNESS")
st.title("Medical Report Explainer")
st.write("Understand your lab values, one test at a time.")
st.warning(DISCLAIMER)
with st.sidebar:
    st.header("Model connection")
    provider = st.selectbox("Provider", ["Ollama", "Groq", "llama.cpp"], index=["Ollama", "Groq", "llama.cpp"].index(os.getenv("LLM_PROVIDER", "Ollama")))
    defaults = {"Ollama": "qwen2.5:1.5b", "Groq": "llama-3.3-70b-versatile", "llama.cpp": "qwen2.5-1.5b"}
    model = st.text_input("Model", value=os.getenv("LLM_MODEL", defaults[provider]), key=f"model_{provider}")
    api_key, base_url = "", ""
    if provider == "Groq":
        api_key = st.text_input("Groq API key", type="password", value=os.getenv("GROQ_API_KEY", ""))
        st.caption("The report text will be sent to Groq. Remove names, IDs and contact details first.")
    else:
        base_url = st.text_input("Local server URL", value=os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434" if provider == "Ollama" else "http://127.0.0.1:8080"), key=f"url_{provider}")
        st.caption("Local model processing. No report files are saved by this application.")
    st.divider()
    st.caption("Ayush Hiraman Pawar · Roll 51")
    st.caption("PDF / TXT · up to 5 MB · 10 PDF pages")

samples = sorted((Path(__file__).parent / "samples").glob("*.txt"))
choice = st.selectbox("Try a synthetic sample", ["Choose a sample"] + [s.stem for s in samples])
if choice != st.session_state.get("last_sample"):
    st.session_state["report_text"] = "" if choice == "Choose a sample" else next(s for s in samples if s.stem == choice).read_text()
    st.session_state["last_sample"] = choice
upload = st.file_uploader("Upload a lab report (overrides pasted text)", type=["pdf", "txt"])
text = st.text_area("Or paste report text", key="report_text", height=160, placeholder="Test | Result | Unit | Reference range")
consent = st.checkbox("I have removed personal identifiers and agree to send this text to the selected model.") if provider == "Groq" else True
report = text
input_error = None
if upload is not None:
    try:
        report = read_report(upload.name, upload.getvalue())
        with st.expander("Text read from the uploaded file"):
            st.text(report)
    except ReportError as exc:
        input_error = str(exc)
        st.error(input_error)
identity = hashlib.sha256(json.dumps([report, provider, model, base_url]).encode()).hexdigest()
if st.button("Explain report", type="primary", disabled=not consent or input_error is not None):
    st.session_state.pop("result", None)
    try:
        with st.spinner("Extracting tests, checking ranges and writing explanations…"):
            result = analyse(report, LLMClient(provider, model, api_key, base_url))
        st.session_state["result"] = (identity, result)
    except ReportError as exc:
        st.error(str(exc))

saved = st.session_state.get("result")
if saved and saved[0] == identity and input_error is None:
    result = saved[1]
    rows = result["tests"]
    with st.container(key="result_summary"):
        st.subheader("Your report, explained")
        cols = st.columns(4)
        for col, label, count in zip(cols, ["Tests found", "Within range", "Outside range", "Not assessed"], [len(rows), sum(r["status"] == "Within range" for r in rows), sum(r["status"] in ("High", "Low") for r in rows), sum(r["status"] == "Not assessed" for r in rows)]):
            col.metric(label, count)
        st.caption("Flags compare exact numbers with the report’s printed range. They do not indicate disease or severity.")
        st.table([{"Test": r["test"], "Result": r["value"], "Unit": r["unit"] or "—", "Printed range": r["reference_range"] or "Not provided", "Status": r["status"]} for r in rows])
    for warning in result["warnings"]:
        st.warning(warning)
    for row in rows:
        with st.container(border=True):
            st.subheader(f'{row["test"]} · {row["status"]}')
            st.write(row["explanation"])
            st.caption(row["comparison_note"])
    with st.expander("Verify extracted source lines and JSON"):
        st.json(result)
    st.caption(f'Generated using {result["model"]} via {result["provider"]}. Model explanations may contain errors; verify with a clinician.')
    a, b = st.columns(2)
    a.download_button("Download results (JSON)", json.dumps(result, indent=2, ensure_ascii=False), "report_results.json", "application/json", on_click="ignore")
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    # Prevent spreadsheet formula execution in exported text cells.
    writer.writerows({k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v for k, v in row.items()} for row in rows)
    b.download_button("Download table (CSV)", stream.getvalue(), "report_results.csv", "text/csv", on_click="ignore")
    if st.button("Clear results"):
        st.session_state.pop("result", None)
        st.rerun()
else:
    st.info("Start with a sample or your own text report. Printed reference ranges are required for numerical flags.")
st.caption("Educational mini project. Scanned PDFs need OCR; qualitative and ambiguous results are left unassessed. For severe symptoms, seek urgent care independently of this tool.")
