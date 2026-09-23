# Autonomous Software Debugging Agent (Multi-Language & ZIP Project Support)

An agentic AI system built in Python using **LangGraph**, **Streamlit**, **Groq / Google Gemini APIs**, **Language Adapters (Python & Java)**, **PyTest**, **Maven/Gradle**, and **SQLite** that autonomously analyzes buggy single-file code or complete software projects, investigates stack traces/compilation errors, identifies root causes, generates targeted patches, executes automated unit test suites in an isolated sandbox, and verifies solutions.

---

## 1. Supported LLM Engines & Providers

- **Groq (Recommended - Ultra Low Latency)**: `llama-3.3-70b-versatile`, `llama-3.1-70b-versatile`, `llama-3.1-8b-instant`, `mixtral-8x7b-32768`, `deepseek-r1-distill-llama-70b`
- **Google Gemini**: `gemini-2.5-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`
- **Mock Mode / Rule-Based Fallback**: Built-in AST analyzer and pattern recognition engine allowing full offline usage without API keys.

---

## 2. Supported Languages & Input Modes

### Supported Languages
- **Python**: `.py`, `requirements.txt`, `pyproject.toml`, `setup.py` (via `pytest` runner or entry file fallback)
- **Java**: `.java`, `pom.xml`, `build.gradle`, `build.gradle.kts` (via Maven `mvn`/`mvnw`, Gradle `gradle`/`gradlew`, or direct `javac`/`java`)

### Input Modes
1. **Single File**: Paste Python source code & error log directly in the Streamlit editor.
2. **ZIP Project Upload**: Upload a full `.zip` project archive containing multi-file Python or Java code bases.

---

## 3. High-Level Architecture & Workflow

```
User
  │
  ▼
Streamlit Upload UI (Single File / ZIP Upload)
  │
  ▼
Workspace Manager (Safe ZIP Extraction & Path Traversal Guard)
  │
  ▼
Project Detector (Language, Build System, Source/Test Dirs)
  │
  ▼
Language Adapter (PythonAdapter / JavaAdapter)
  │
  ▼
LangGraph Orchestration Engine (7-Agent Workflow)
  ├── 1. Code Analysis Agent
  ├── 2. Bug Investigation Agent (Groq / Gemini / Rule-Based)
  ├── 3. Root Cause Agent (Groq / Gemini / Rule-Based)
  ├── 4. Fix Generation Agent (Groq / Gemini / Rule-Based)
  ├── 5. Testing Agent (Executes Adapter build/tests in sandbox)
  ├── 6. Verification Agent (Evaluates test/build results)
  └── 7. Supervisor Agent (Retry loop control & report compiling)
  │
  ▼
Final Report & SQLite Session History
```

---

## 4. The 7 Specialized Agents

| # | Agent Name | Location | Responsibility |
|---|------------|----------|----------------|
| 1 | **Supervisor Agent** | `agents/supervisor/` | Manages state, iteration loop bounds (max 3 retries), and compiles final reports. |
| 2 | **Code Analysis Agent** | `agents/code_analysis/` | Parses single-file AST or analyzes multi-file project structure & manifests. |
| 3 | **Bug Investigation Agent** | `agents/bug_investigation/` | Pinpoints error locations from stack traces, tracebacks, or compilation logs. |
| 4 | **Root Cause Agent** | `agents/root_cause/` | Diagnoses underlying bug logic (`NullPointerException`, `ZeroDivisionError`, `IndexError`, etc.). |
| 5 | **Fix Generation Agent** | `agents/fix_generation/` | Generates candidate code fixes and multi-file patches (`file`, `changes`, `reason`). |
| 6 | **Testing Agent** | `agents/testing/` | Executes `pytest`, Maven (`mvn test`), or Gradle (`gradle test`) via Language Adapters. |
| 7 | **Verification Agent** | `agents/verification/` | Compares pre- and post-fix build/test results to verify fix correctness. |

---

## 5. Technology Stack
- **Languages Supported**: Python 3.10+, Java (JDK 11+)
- **Orchestration**: LangGraph, LangChain Core
- **LLM Engines**: Groq SDK (`groq`), Google GenAI (`google-genai` / `google-generativeai`)
- **Frontend UI**: Streamlit
- **Build & Test Tools**: PyTest, Maven (`mvn`/`mvnw`), Gradle (`gradle`/`gradlew`), `javac`
- **Database**: SQLite3 (`debug_history.db`)
- **Containerization**: Docker & Render Blueprint (`render.yaml`)

---

## 6. Installation & Local Setup

1. **Clone or Open Project**:
   ```bash
   cd Autonomous_Debugging_Agent
   ```

2. **Create & Activate Virtual Environment**:
   ```bash
   python -m venv venv
   # On Windows PowerShell:
   .\venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and add your API Keys:
   ```env
   LLM_PROVIDER=groq
   GROQ_API_KEY=gsk_your_groq_api_key_here
   GROQ_MODEL=llama-3.3-70b-versatile

   # Optional Gemini backup
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-2.5-flash
   ```
   > *Note: If no API key is provided, the system automatically runs in **Mock Mode**.*

5. **Run Locally**:
   ```bash
   python -m streamlit run frontend/streamlit_app.py
   ```
   Open your browser to `http://localhost:8501`.

---

## 7. Deploying to Render (Step-by-Step)

### Option 1: Automatic Blueprint Deployment (Recommended)
1. Push this repository to GitHub or GitLab.
2. In the [Render Dashboard](https://dashboard.render.com), click **New +** → **Blueprint**.
3. Connect your repository. Render will automatically read [`render.yaml`](file:///c:/Users/swaro/Desktop/Autonomous_Debugging_Agent-main/render.yaml) and configure the Docker Web Service.
4. Under Environment Variables, provide your `GROQ_API_KEY` (and optional `GEMINI_API_KEY`).
5. Click **Apply**. Render will build the container with Python 3.11, OpenJDK 17, and Maven pre-installed.

### Option 2: Manual Web Service on Render
1. In Render Dashboard, click **New +** → **Web Service**.
2. Connect your Git repository.
3. Select **Docker** as the Environment.
4. Set Region to your preferred location (e.g. `Oregon (US West)` or `Frankfurt`).
5. Add Environment Variables:
   - `GROQ_API_KEY`: `gsk_...`
   - `LLM_PROVIDER`: `groq`
   - `GROQ_MODEL`: `llama-3.3-70b-versatile`
6. Click **Create Web Service**.

---

## 8. Docker Build & Run (Self-Hosted)

```bash
# Build Docker Image
docker build -t autonomous-debugging-agent .

# Run Container on Port 8501 with Groq API Key
docker run -p 8501:8501 \
  -e GROQ_API_KEY="gsk_your_key_here" \
  -e LLM_PROVIDER="groq" \
  autonomous-debugging-agent
```
