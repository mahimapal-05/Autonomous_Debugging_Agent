import sys
import os
import json
import io
import zipfile
import streamlit as st

# Add project root directory to python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from demo_examples import DEMO_EXAMPLES, DEMO_PROJECT_PRESETS
from utils.llm import (
    is_llm_available,
    is_gemini_available,
    get_gemini_api_key,
    set_gemini_api_key,
    set_llm_provider,
    DEFAULT_GEMINI_MODEL,
    get_preferred_provider
)
from database.database import save_debug_session, get_all_sessions, init_db
from orchestration.graph import debugging_app
from utils.workspace import WorkspaceManager
from utils.interpreter import execute_python_code
from language_adapters.detector import detect_project
from language_adapters.python.adapter import PythonAdapter
from language_adapters.java.adapter import JavaAdapter
from agents.testing.agent import run_pytest_in_sandbox

# Set page config
st.set_page_config(
    page_title="Autonomous Debugging Agent & Live Python Interpreter",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for rich dark modern aesthetic
st.markdown("""
<style>
    .main-header {
        font-size: 2.3rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FF6B6B 0%, #FFD93D 50%, #6BCB77 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2px;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #94A3B8;
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0px 0px;
        padding: 10px 20px;
        font-weight: 600;
    }
    .interpreter-card {
        border-radius: 12px;
        padding: 18px;
        background: #0F172A;
        border: 1px solid #1E293B;
        margin-bottom: 15px;
    }
    .live-runner-box {
        border-radius: 10px;
        padding: 15px;
        background-color: #111827;
        border: 1px solid #374151;
        margin-top: 12px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
init_db()

# Initialize session state variables
if "code_input" not in st.session_state:
    st.session_state["code_input"] = DEMO_EXAMPLES["🔥 Palindrome Number (Logic Bug & Identifier Typo)"]["code"]
if "error_input" not in st.session_state:
    st.session_state["error_input"] = DEMO_EXAMPLES["🔥 Palindrome Number (Logic Bug & Identifier Typo)"]["error_log"]
if "test_input" not in st.session_state:
    st.session_state["test_input"] = DEMO_EXAMPLES["🔥 Palindrome Number (Logic Bug & Identifier Typo)"].get("test_code", "")
if "interpreter_code" not in st.session_state:
    st.session_state["interpreter_code"] = DEMO_EXAMPLES["🔥 Palindrome Number (Logic Bug & Identifier Typo)"]["code"]
if "active_debugging_result" not in st.session_state:
    st.session_state["active_debugging_result"] = None
if "interp_last_result" not in st.session_state:
    st.session_state["interp_last_result"] = None
if "live_fix_run_result" not in st.session_state:
    st.session_state["live_fix_run_result"] = None
if "custom_test_run_result" not in st.session_state:
    st.session_state["custom_test_run_result"] = None

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/isometric/96/bug.png", width=64)
    st.markdown("### 🤖 Agent & Gemini Engine")

    # Check existing keys from environment
    gemini_active = is_gemini_available()
    llm_active = is_llm_available()

    if gemini_active:
        st.success(f"🟢 **Gemini Active** (`{os.getenv('GEMINI_MODEL', DEFAULT_GEMINI_MODEL)}`)")
    else:
        st.warning("🟠 **Autonomous Fallback & Self-Correcting Mode** (No API Key)")
        st.caption("Operating with intelligent multi-pass AST & rule-based self-correction engine.")

    with st.expander("⚙️ Gemini Configuration & Key", expanded=not gemini_active):
        mode_choice = st.selectbox(
            "Engine Mode:",
            options=["Google Gemini", "Autonomous Multi-Pass / Mock Mode"],
            index=0 if gemini_active else 1
        )
        
        input_gemini_key = st.text_input(
            "Gemini API Key:",
            value=get_gemini_api_key() if get_gemini_api_key() != "your_gemini_api_key_here" else "",
            type="password",
            placeholder="AIzaSy..."
        )
        if input_gemini_key:
            set_gemini_api_key(input_gemini_key.strip())

        if mode_choice == "Google Gemini":
            set_llm_provider("gemini")
            gemini_model_choice = st.selectbox(
                "Gemini Model:",
                options=["gemini-2.0-flash", "gemini-2.0-pro-exp-02-05", "gemini-1.5-flash", "gemini-1.5-pro"],
                index=0
            )
            os.environ["GEMINI_MODEL"] = gemini_model_choice
        else:
            set_llm_provider("mock")

    st.divider()
    st.markdown("### 📚 Demo Presets")
    
    preset_mode = st.radio("Preset type:", ["Single File", "ZIP Project"])

    if preset_mode == "Single File":
        selected_demo = st.selectbox(
            "Load single-file example:",
            options=["Select preset..."] + list(DEMO_EXAMPLES.keys())
        )

        if st.button("Load Selected Preset", type="secondary", use_container_width=True):
            if selected_demo in DEMO_EXAMPLES:
                ex = DEMO_EXAMPLES[selected_demo]
                st.session_state["code_input"] = ex["code"]
                st.session_state["error_input"] = ex["error_log"]
                st.session_state["test_input"] = ex.get("test_code", "")
                st.session_state["interpreter_code"] = ex["code"]
                st.session_state["debug_mode"] = "Single File"
                st.session_state["active_debugging_result"] = None
                st.session_state["live_fix_run_result"] = None
                st.session_state["custom_test_run_result"] = None
                st.rerun()

    else:
        selected_proj = st.selectbox(
            "Load project ZIP preset:",
            options=["Select project preset..."] + list(DEMO_PROJECT_PRESETS.keys())
        )

        if st.button("Load Selected Project ZIP", type="secondary", use_container_width=True):
            if selected_proj in DEMO_PROJECT_PRESETS:
                p_spec = DEMO_PROJECT_PRESETS[selected_proj]
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for path, text in p_spec["files"].items():
                        zf.writestr(path, text)
                buf.seek(0)
                
                st.session_state["uploaded_preset_bytes"] = buf.getvalue()
                st.session_state["uploaded_preset_name"] = p_spec["filename"]
                st.session_state["debug_mode"] = "Upload Project"
                st.session_state["active_debugging_result"] = None
                st.session_state["live_fix_run_result"] = None
                st.session_state["custom_test_run_result"] = None
                st.rerun()

    st.divider()
    st.markdown("### 📜 Session History")
    sessions = get_all_sessions()
    if sessions:
        for s in sessions[:5]:
            status_icon = "✅" if s["verification_status"] == "VERIFIED" else "❌"
            lang = s.get("language", "Python")
            st.caption(f"{status_icon} **{s['title']}** [{lang}] ({s['timestamp']})")
    else:
        st.caption("No saved debug sessions yet.")


# --- MAIN HEADER ---
st.markdown('<div class="main-header">Autonomous Software Debugging Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Multi-Agent AI Pipeline + Live Web Python Interpreter & Self-Correction Engine</div>', unsafe_allow_html=True)

# Main Navigation Tabs
tab_debugger, tab_interpreter, tab_history = st.tabs([
    "🤖 Multi-Agent Autonomous Debugger",
    "⚡ Live Web Python Interpreter & Sandbox",
    "📊 Session History & Analytics"
])

# ==============================================================================
# TAB 1: MULTI-AGENT AUTONOMOUS DEBUGGER
# ==============================================================================
with tab_debugger:
    if "debug_mode" not in st.session_state:
        st.session_state["debug_mode"] = "Single File"

    debug_mode = st.radio(
        "Select Debug Input Mode:",
        options=["Single File", "Upload Project"],
        horizontal=True,
        index=0 if st.session_state.get("debug_mode") == "Single File" else 1,
        key="mode_radio"
    )
    st.session_state["debug_mode"] = debug_mode

    st.divider()

    active_project_path = None
    active_temp_dir = None
    active_language = "python"
    active_build_system = "pytest"
    detection_info = None

    if debug_mode == "Single File":
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("1. Python Source Code")
            source_code = st.text_area(
                "Enter buggy Python code:",
                value=st.session_state.get("code_input", ""),
                height=260,
                key="source_editor"
            )
            st.session_state["code_input"] = source_code

        with col2:
            st.subheader("2. Stack Trace / Error Log (Optional)")
            error_log = st.text_area(
                "Paste error log or stack trace (Optional):",
                value=st.session_state.get("error_input", ""),
                placeholder="Optional: Leave blank to auto-detect bugs across code, execute sandbox tests, and self-correct.",
                height=260,
                key="error_editor"
            )
            st.session_state["error_input"] = error_log

        btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 1])
        with btn_col1:
            start_btn = st.button("🚀 Start Autonomous Self-Correcting Debugging", type="primary", use_container_width=True)
        with btn_col2:
            if st.button("⚡ Test in Live Interpreter", use_container_width=True):
                st.session_state["interpreter_code"] = source_code
                st.info("Code copied to Live Python Interpreter! Switch to Tab 2 to run.")
        with btn_col3:
            if st.button("🧹 Clear Logs", use_container_width=True):
                st.session_state["error_input"] = ""
                st.session_state["active_debugging_result"] = None
                st.session_state["live_fix_run_result"] = None
                st.session_state["custom_test_run_result"] = None
                st.rerun()

    else:
        # Upload Project Mode
        st.subheader("📦 Upload Complete Project (ZIP)")
        st.caption("Upload a `.zip` archive containing a Python or Java project.")

        uploaded_file = st.file_uploader("Choose a project ZIP file", type=["zip"])
        
        zip_bytes = None
        zip_filename = None

        if uploaded_file is not None:
            zip_bytes = uploaded_file.read()
            zip_filename = uploaded_file.name
        elif "uploaded_preset_bytes" in st.session_state:
            zip_bytes = st.session_state["uploaded_preset_bytes"]
            zip_filename = st.session_state.get("uploaded_preset_name", "preset_project.zip")
            st.info(f"Loaded demo project preset: `{zip_filename}`")

        if zip_bytes is not None:
            temp_dir, project_root, extract_err = WorkspaceManager.extract_zip(io.BytesIO(zip_bytes))
            
            if extract_err:
                st.error(extract_err)
            else:
                active_temp_dir = temp_dir
                active_project_path = project_root
                
                detection_info = detect_project(project_root)
                
                if not detection_info.get("is_supported", False):
                    st.error(detection_info.get("message", "Unsupported project format."))
                    WorkspaceManager.cleanup(temp_dir)
                    active_temp_dir = None
                    active_project_path = None
                else:
                    st.success("Project ZIP extracted and inspected successfully!")
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Project Name", zip_filename)
                    
                    detected_lang = detection_info.get("language")
                    if detected_lang == "multiple":
                        st.warning("⚠️ Multiple languages detected in project.")
                        selected_lang = st.radio("Select target language to debug:", ["Python", "Java"], horizontal=True)
                        active_language = selected_lang.lower()
                        active_build_system = "pytest" if active_language == "python" else "maven"
                    else:
                        active_language = detected_lang
                        active_build_system = detection_info.get("build_system", "unknown")

                    c2.metric("Detected Language", active_language.capitalize())
                    c3.metric("Build/Test System", active_build_system)
                    c4.metric("Total Files", detection_info.get("files_count", 0))

                    st.markdown(f"**Test Files Detected:** `{detection_info.get('test_files_count', 0)}`")
                    if detection_info.get("dependency_files"):
                        st.markdown(f"**Manifest Files:** `{', '.join(detection_info.get('dependency_files'))}`")

        start_btn = st.button("🚀 Start Autonomous Project Debugging", type="primary", use_container_width=True, disabled=(active_project_path is None))

    # --- WORKFLOW TRIGGER ---
    if start_btn:
        if debug_mode == "Single File" and not source_code.strip():
            st.error("Please provide Python source code to debug.")
        elif debug_mode == "Upload Project" and not active_project_path:
            st.error("Please upload a valid project ZIP archive first.")
        else:
            st.session_state["live_fix_run_result"] = None
            st.session_state["custom_test_run_result"] = None

            progress_bar = st.progress(0)
            status_text = st.empty()

            active_llm = is_llm_available()

            # Initialize execution state
            if debug_mode == "Single File":
                effective_error_log = (error_log or "").strip()
                if not effective_error_log:
                    pre_test = run_pytest_in_sandbox(source_code, st.session_state.get("test_input", None))
                    if pre_test.get("status") == "FAIL" or pre_test.get("failed", 0) > 0 or pre_test.get("exit_code") != 0:
                        effective_error_log = pre_test.get("output", "")

                initial_state = {
                    "input_mode": "single_file",
                    "source_code": source_code,
                    "error_log": effective_error_log,
                    "test_code": st.session_state.get("test_input", None),
                    "code_analysis": None,
                    "bug_investigation": None,
                    "root_cause": None,
                    "candidate_fix": None,
                    "test_results": None,
                    "verification_result": None,
                    "iteration_count": 0,
                    "max_iterations": 5,
                    "history": [],
                    "final_report": None,
                    "is_mock_mode": not active_llm,
                    "language": "python",
                    "project_name": "Single File"
                }
            else:
                if active_language == "java":
                    init_adapter = JavaAdapter(active_project_path)
                else:
                    init_adapter = PythonAdapter(active_project_path)

                init_exec = init_adapter.run_tests()
                init_error_log = init_exec.get("output") or init_exec.get("stderr") or "Build/Test failure"

                initial_state = {
                    "input_mode": "project",
                    "project_path": active_project_path,
                    "project_name": zip_filename,
                    "language": active_language,
                    "build_system": active_build_system,
                    "source_code": "",
                    "error_log": init_error_log,
                    "execution_result": init_exec,
                    "test_code": None,
                    "code_analysis": None,
                    "bug_investigation": None,
                    "root_cause": None,
                    "candidate_fix": None,
                    "test_results": None,
                    "verification_result": None,
                    "iteration_count": 0,
                    "max_iterations": 5,
                    "history": [],
                    "final_report": None,
                    "is_mock_mode": not active_llm
                }

            try:
                status_text.text("1/7 Code Analysis Agent inspecting syntax, symbols & structure...")
                progress_bar.progress(15)
                
                # Execute LangGraph workflow
                final_state = debugging_app.invoke(initial_state)
                progress_bar.progress(100)
                status_text.text("✅ Autonomous Debugging & Self-Correction Pipeline Complete!")

                # Store active debugging result in session state
                st.session_state["active_debugging_result"] = {
                    "final_state": final_state,
                    "debug_mode": debug_mode,
                    "source_code": source_code if debug_mode == "Single File" else "",
                    "active_language": active_language,
                    "project_name": zip_filename if debug_mode == "Upload Project" else "Single File"
                }

                # Save session to SQLite database
                report = final_state.get("final_report", {})
                v_status = report.get("status", "UNVERIFIED")
                save_title = f"Fix {report.get('bug_category', 'Bug')} ({final_state.get('project_name', 'Project')})"
                save_debug_session(
                    title=save_title,
                    source_code=source_code if debug_mode == "Single File" else f"Project: {final_state.get('project_name')}",
                    error_log=final_state.get("error_log", ""),
                    bug_category=report.get("bug_category", ""),
                    root_cause=report.get("root_cause", ""),
                    fixed_code=report.get("fixed_code", "") if not report.get("patches") else json.dumps(report.get("patches")),
                    verification_status=v_status,
                    iterations=report.get("iterations_used", 1),
                    language=active_language.capitalize(),
                    project_name=final_state.get("project_name", "Single File")
                )
                st.toast("Saved debug session to history database!", icon="💾")

            except Exception as e:
                st.error(f"Error during agent pipeline execution: {str(e)}")
                st.exception(e)
            finally:
                if active_temp_dir:
                    WorkspaceManager.cleanup(active_temp_dir)

    # --- PERSISTENT WORKFLOW RESULTS RENDERING ---
    dbg_data = st.session_state.get("active_debugging_result")
    if dbg_data:
        final_state = dbg_data["final_state"]
        res_debug_mode = dbg_data["debug_mode"]
        res_source_code = dbg_data["source_code"]
        res_language = dbg_data["active_language"]
        report = final_state.get("final_report", {})
        v_status = report.get("status", "UNVERIFIED")

        st.divider()
        st.subheader("🔄 Multi-Agent Self-Correcting Execution Pipeline")
        st.success("Workflow Execution Finished Successfully!")

        # --- DISPLAY 7 AGENTS DETAILS ---
        st.subheader("🧩 Specialized Agent Execution Trace")

        # 1. Code Analysis
        with st.expander("🔍 1. Code Analysis Agent", expanded=False):
            ca = final_state.get("code_analysis", {})
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Mode", "Project" if ca.get("is_project") else "Single File")
            c2.metric("Language", final_state.get("language", "python").capitalize())
            c3.metric("Functions", len(ca.get("functions", [])))
            c4.metric("Cyclomatic Complexity", ca.get("cyclomatic_complexity", 1))
            
            if ca.get("algorithmic_archetypes"):
                st.markdown(f"**Algorithmic Archetypes:** `{', '.join(ca.get('algorithmic_archetypes'))}`")
            
            if ca.get("semantic_issues"):
                st.warning("⚠️ **Semantic Anti-Patterns & Risk Indicators Detected:**")
                for issue in ca.get("semantic_issues"):
                    st.markdown(f"- **[{issue.get('severity')}] {issue.get('type')}** ({issue.get('location')}): {issue.get('description')}")

            st.markdown(f"**Summary:** {ca.get('summary')}")
            st.json(ca)

        # 2. Bug Investigation
        with st.expander("📍 2. Bug Investigation Agent", expanded=False):
            bi = final_state.get("bug_investigation", {})
            st.markdown(f"**Suspected Location:** `{bi.get('suspected_location')}`")
            st.markdown(f"**Suspicious Code Snippet:** `{bi.get('suspicious_code')}`")
            st.markdown(f"**Reason:** {bi.get('reason')}")
            st.json(bi)

        # 3. Root Cause
        with st.expander("🧠 3. Root Cause Agent", expanded=False):
            rc = final_state.get("root_cause", {})
            st.info(f"**Bug Category:** `{rc.get('bug_category')}`")
            st.markdown(f"**Root Cause:** {rc.get('root_cause')}")
            st.markdown(f"**Explanation:** {rc.get('explanation')}")
            st.markdown(f"**Recommended Strategy:** {rc.get('recommended_fix_strategy')}")

        # 4. Fix Generation & Self-Correcting Loop
        with st.expander("🛠️ 4. Fix Generation & Self-Correcting Engine", expanded=True):
            cf = final_state.get("candidate_fix", {})
            st.markdown(f"**Fix Strategy Explanation:** {cf.get('explanation')}")
            
            if cf.get("self_correction_history"):
                st.markdown("##### 🔁 Self-Correction Iterations Timeline")
                for step in cf.get("self_correction_history", []):
                    iter_icon = "✅ Clean" if step.get("success") else f"⚠️ Error ({step.get('error_type', 'ExecutionError')})"
                    st.markdown(f"**Iteration {step.get('iteration')}:** {iter_icon}")
                    if step.get("error_message"):
                        st.caption(f"Error caught: `{step.get('error_message')}`")
            
            fix_code_block = cf.get("fixed_code", "")
            if cf.get("patches"):
                for p in cf.get("patches"):
                    st.markdown(f"**Patch File:** `{p.get('file')}`")
                    st.code(p.get("changes", ""), language=res_language)
                    if not fix_code_block:
                        fix_code_block = p.get("changes", "")
            else:
                st.code(fix_code_block, language=res_language)

        # 5. Testing Agent
        with st.expander("🧪 5. Testing Agent (4-Tier Adversarial Matrix & Sandbox)", expanded=True):
            tr = final_state.get("test_results", {})
            tc1, tc2, tc3 = st.columns(3)
            tc1.metric("Tests Executed", tr.get("tests_run", 0))
            tc2.metric("Passed", tr.get("passed", 0))
            tc3.metric("Failed", tr.get("failed", 0))
            
            if tr.get("autopsy"):
                st.error(f"❌ **Failing Test Autopsy:** {tr['autopsy'].get('failure_reason')}")
            st.code(tr.get("output", ""), language="bash")

        # 6. Verification Agent
        with st.expander("🎯 6. Verification Agent", expanded=True):
            vr = final_state.get("verification_result", {})
            v_status_inner = vr.get("status", "UNVERIFIED")
            if v_status_inner == "VERIFIED":
                st.success(f"Status: {v_status_inner} — {vr.get('reason')}")
            else:
                st.error(f"Status: {v_status_inner} — {vr.get('reason')}")

        # 7. Supervisor Agent Overview
        with st.expander("👑 7. Supervisor Agent Overview", expanded=False):
            sup = final_state.get("final_report", {})
            st.json(sup)

        # --- FINAL REPORT SUMMARY CARD ---
        st.divider()
        st.subheader("📊 Final Debugging Report")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Verification Status", v_status)
        m2.metric("Iterations Used", report.get("iterations_used", 1))
        m3.metric("Bug Category", report.get("bug_category", "Unknown"))
        m4.metric("Tests Passed", f"{report.get('tests_passed', 0)} / {report.get('tests_passed', 0) + report.get('tests_failed', 0)}")

        comp_col1, comp_col2 = st.columns(2)
        with comp_col1:
            st.markdown("#### ❌ Initial Bug Context")
            if res_debug_mode == "Single File":
                st.code(res_source_code, language="python")
            else:
                st.code(final_state.get("error_log", "Execution Log"), language="text")

        with comp_col2:
            st.markdown("#### ✅ Candidate Fix / Patches")
            fixed_code_to_run = ""
            if report.get("patches"):
                for p in report.get("patches"):
                    st.markdown(f"**{p.get('file')}**")
                    st.code(p.get("changes", ""), language=res_language)
                    if not fixed_code_to_run:
                        fixed_code_to_run = p.get("changes", "")
            else:
                fixed_code_to_run = report.get("fixed_code", "")
                st.code(fixed_code_to_run, language=res_language)

            # --- LIVE CODE RUNNER RIGHT ON SCREEN ---
            st.markdown("##### 🚀 Test & Run This Fix Live")
            run_btn_c1, run_btn_c2 = st.columns([1.5, 1])
            with run_btn_c1:
                if st.button("▶ Run Fixed Code Live", type="primary", key="btn_run_fix_report", use_container_width=True):
                    if res_language == "python" and fixed_code_to_run:
                        exec_res = execute_python_code(fixed_code_to_run)
                        st.session_state["live_fix_run_result"] = exec_res
                    else:
                        st.info("Direct execution is available for Python.")
            with run_btn_c2:
                if st.button("⚡ Open in Playground", key="btn_open_in_interp_report", use_container_width=True):
                    st.session_state["interpreter_code"] = fixed_code_to_run
                    st.info("Fixed code loaded into Live Interpreter (Tab 2)!")

            # Display Live Execution Result if executed
            live_res = st.session_state.get("live_fix_run_result")
            if live_res is not None:
                st.markdown("###### 🖥️ Live Output & Execution Result:")
                if live_res["success"]:
                    st.success(f"✅ **Execution Succeeded (0 Errors)** in `{live_res['execution_time_ms']} ms`")
                else:
                    st.error(f"❌ **{live_res.get('error_type', 'ExecutionError')}**: {live_res.get('error_message')}")

                if live_res["stdout"]:
                    st.code(live_res["stdout"], language="text")
                elif live_res["success"]:
                    st.info("Code executed cleanly with 0 exceptions.")

                if live_res["stderr"]:
                    st.code(live_res["stderr"], language="python")

            # Interactive Custom Test Call
            with st.expander("🧪 Run Custom Test Inputs / Assertions", expanded=True):
                default_call = ""
                if "isPalindrome" in fixed_code_to_run:
                    default_call = "print('isPalindrome(12321) ->', isPalindrome(12321))\nprint('isPalindrome(-101) ->', isPalindrome(-101))"
                elif "calculate_average" in fixed_code_to_run:
                    default_call = "print('calculate_average([10, 20, 30]) ->', calculate_average([10, 20, 30]))"
                
                custom_driver = st.text_area("Enter custom test calls to test the fix:", value=default_call, height=90, key="custom_call_area")
                if st.button("▶ Execute Custom Test", key="btn_run_custom_call"):
                    combined = f"{fixed_code_to_run}\n\n{custom_driver}"
                    custom_res = execute_python_code(combined)
                    st.session_state["custom_test_run_result"] = custom_res

                cust_res = st.session_state.get("custom_test_run_result")
                if cust_res is not None:
                    if cust_res["success"]:
                        st.success(f"Custom Test Output:\n{cust_res['stdout']}")
                    else:
                        st.error(f"Error:\n{cust_res['stderr']}")


# ==============================================================================
# TAB 2: LIVE WEB PYTHON INTERPRETER & INTERACTIVE DEBUGGER
# ==============================================================================
with tab_interpreter:
    st.subheader("⚡ Live Web Python Interpreter & Real-Time Execution Console")
    st.caption("Execute Python scripts live in the browser, inspect variables, capture runtime tracebacks, and self-correct.")

    int_col1, int_col2 = st.columns([1.2, 1])

    with int_col1:
        st.markdown("##### 💻 Python Code Editor")
        interp_code_val = st.text_area(
            "Write or edit Python code:",
            value=st.session_state.get("interpreter_code", ""),
            height=320,
            key="web_interpreter_editor"
        )
        st.session_state["interpreter_code"] = interp_code_val

        act_col1, act_col2 = st.columns(2)
        with act_col1:
            run_interp_btn = st.button("▶ Run in Interpreter", type="primary", use_container_width=True, key="btn_run_interp_tab2")
        with act_col2:
            debug_from_interp_btn = st.button("🩺 Auto-Debug with AI Agent", type="secondary", use_container_width=True, key="btn_debug_interp_tab2")

    with int_col2:
        st.markdown("##### 🖥️ Console Output & Diagnostics")
        
        if run_interp_btn:
            exec_res = execute_python_code(interp_code_val)
            st.session_state["interp_last_result"] = exec_res

        elif debug_from_interp_btn:
            exec_res = execute_python_code(interp_code_val)
            st.session_state["interp_last_result"] = exec_res
            st.session_state["code_input"] = interp_code_val
            st.session_state["error_input"] = exec_res.get("stderr", "")
            st.session_state["debug_mode"] = "Single File"
            st.session_state["active_debugging_result"] = None
            st.success("Transferred code and runtime trace to Autonomous Multi-Agent Debugger! Switch to Tab 1 to run.")

        # Render last execution result if present
        last_res = st.session_state.get("interp_last_result")
        if last_res is not None:
            stat_c1, stat_c2 = st.columns(2)
            if last_res["success"]:
                stat_c1.success("✅ **Execution Successful** (0 Errors)")
            else:
                stat_c1.error(f"❌ **{last_res.get('error_type', 'Error')} Detected**")
            stat_c2.metric("Execution Time", f"{last_res['execution_time_ms']} ms")

            # Standard Output
            if last_res["stdout"]:
                st.markdown("**Standard Output (stdout):**")
                st.code(last_res["stdout"], language="text")
            elif last_res["success"]:
                st.info("Program executed cleanly with no stdout output.")

            # Standard Error / Traceback
            if last_res["stderr"]:
                st.markdown("**Error Traceback (stderr):**")
                st.code(last_res["stderr"], language="python")
                if last_res.get("lineno"):
                    st.warning(f"📍 Exception occurred at **Line {last_res['lineno']}**")

            # Variables State Inspector
            if last_res.get("variables"):
                with st.expander("🔍 Variable State Inspector", expanded=True):
                    for var_name, var_info in last_res["variables"].items():
                        st.markdown(f"- `{var_name}` (*{var_info['type']}*): `{var_info['value']}`")
        else:
            st.info("Click **▶ Run in Interpreter** to execute code in real-time or **🩺 Auto-Debug with AI Agent** to send it directly to the multi-agent self-correcting debugger.")


# ==============================================================================
# TAB 3: SESSION HISTORY & ANALYTICS
# ==============================================================================
with tab_history:
    st.subheader("📊 Debugging History & Fix Analytics")
    all_sessions = get_all_sessions()

    if not all_sessions:
        st.info("No debugging sessions recorded yet. Run a debugging workflow to persist history.")
    else:
        hist_c1, hist_c2, hist_c3 = st.columns(3)
        total_sessions = len(all_sessions)
        verified_count = sum(1 for s in all_sessions if s.get("verification_status") == "VERIFIED")
        hist_c1.metric("Total Sessions", total_sessions)
        hist_c2.metric("Verified Fixes", verified_count)
        hist_c3.metric("Fix Success Rate", f"{round((verified_count / total_sessions) * 100, 1)}%")

        st.divider()

        for s in all_sessions:
            status_color = "🟢" if s["verification_status"] == "VERIFIED" else "🔴"
            with st.expander(f"{status_color} {s['title']} — {s.get('verification_status')} ({s.get('timestamp')})"):
                st.markdown(f"**Language:** `{s.get('language')}` | **Project:** `{s.get('project_name')}` | **Bug Category:** `{s.get('bug_category')}`")
                st.markdown(f"**Root Cause:** {s.get('root_cause')}")
                
                hc1, hc2 = st.columns(2)
                with hc1:
                    st.markdown("**Original Buggy Input:**")
                    st.code(s.get("source_code", ""), language="python")
                with hc2:
                    st.markdown("**Generated Fix / Patch:**")
                    st.code(s.get("fixed_code", ""), language="python")
