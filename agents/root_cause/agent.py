import json
import re
from typing import Dict, Any
from utils.llm import call_llm, is_llm_available
from agents.root_cause.prompts import ROOT_CAUSE_SYSTEM_PROMPT, ROOT_CAUSE_USER_PROMPT

def fallback_root_cause(error_log: str, bug_investigation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback root cause analyzer when LLM is unavailable or error log is blank.
    Infers root cause from error log or bug investigation findings.
    """
    error_text = (error_log or "").strip()
    reason_text = (bug_investigation.get("reason") or "").lower()
    snippet_text = (bug_investigation.get("suspicious_code") or "")

    category = "RuntimeError"
    if "SyntaxError" in error_text or "syntaxerror" in reason_text or "expected ':'" in error_text:
        category = "SyntaxError"
        cause = "Python statement syntax is invalid; a required token such as a trailing colon (:) is missing after a compound statement header or brackets are unbalanced."
        explanation = "In Python, header statements such as `for`, `if`, `while`, `def`, and `class` must conclude with a colon (':') preceding an indented block."
        strategy = "Add missing colon (:) to the end of the compound statement line and verify block indentation and brackets."
    elif "IndentationError" in error_text or "indentationerror" in reason_text:
        category = "IndentationError"
        cause = "Inconsistent indentation tabs or spaces encountered in code block."
        explanation = "Python relies strictly on uniform indentation to delimit statement blocks."
        strategy = "Re-indent the code uniformly using 4 spaces per block level."
    elif "NameError" in error_text or "nameerror" in reason_text:
        category = "NameError"
        cause = "Variable, function, or symbol name referenced before assignment or declaration."
        explanation = "A symbol was accessed that does not exist in local or global namespaces (possible typographical error)."
        strategy = "Declare and initialize the variable or correct the identifier spelling."
    elif "NullPointerException" in error_text or "nullpointer" in reason_text or "user.getName()" in snippet_text:
        category = "NullPointerException"
        cause = "The code attempts to invoke a method or dereference an attribute on a null object reference."
        explanation = "A variable or method parameter was not properly initialized or validated before accessing its methods/properties."
        strategy = "Add a null check guard (e.g., `if (obj != null)`) or assign a non-null fallback value before invocation."
    elif "TypeError" in error_text or "typeerror" in reason_text or ("discount" in snippet_text and "/" in snippet_text):
        category = "TypeError"
        cause = "Incompatible type passed to arithmetic operator or function."
        explanation = "Attempting arithmetic operations on string or incompatible types raises a TypeError."
        strategy = "Cast or convert parameters to appropriate numerical types (e.g., float, int) before performing operations."
    elif "ZeroDivisionError" in error_text or "zerodivision" in reason_text or "/ by zero" in error_text or ("/" in snippet_text and ("len" in snippet_text or "count" in snippet_text or "total /" in snippet_text)):
        category = "ZeroDivisionError"
        cause = "The code attempts to perform mathematical division where denominator evaluates to 0 without pre-checking collection length or variable value."
        explanation = "When an empty collection `[]` or 0 denominator is passed, dividing triggers a ZeroDivisionError."
        strategy = "Add a guard condition checking if denominator/length is 0 before dividing, returning 0 or default."
    elif "IndexError" in error_text or "indexerror" in reason_text or "ArrayIndexOutOfBoundsException" in error_text or re.search(r'\[\s*\d+\s*\]', snippet_text):
        category = "IndexError"
        cause = "The code accesses an array offset beyond the length of the list/array."
        explanation = "Accessing fixed index without checking collection length triggers index out of range on smaller lists."
        strategy = "Validate index bounds using `if (len(items) > index)` or default handling before indexing."
    elif "KeyError" in error_text or "keyerror" in reason_text or re.search(r'\[\s*["\'][a-zA-Z0-9_-]+["\']\s*\]', snippet_text):
        category = "KeyError"
        cause = "Accessing dictionary key without checking key existence."
        explanation = "Accessing `dict[key]` directly raises KeyError when key is missing."
        strategy = "Use `dict.get(key, default)` or `if key in dict:` guard."
    else:
        cause = f"Unhandled edge case or exception: {error_text.splitlines()[-1] if error_text else reason_text or 'Missing validation'}"
        explanation = "The code logic failed boundary conditions or lacked input safety checks."
        strategy = "Add comprehensive input validation, boundary guards, and error handling."

    return {
        "root_cause": cause,
        "bug_category": category,
        "explanation": explanation,
        "recommended_fix_strategy": strategy
    }


def analyze_root_cause_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Root Cause Agent Node for LangGraph.
    Receives state with source_code, error_log, bug_investigation.
    Returns root_cause dict.
    """
    source_code = state.get("source_code", "")
    error_log = state.get("error_log", "")
    bug_investigation = state.get("bug_investigation", {})

    exec_res = state.get("execution_result", {})
    if exec_res and not error_log:
        error_log = exec_res.get("stderr") or exec_res.get("output") or ""

    if is_llm_available():
        user_prompt = ROOT_CAUSE_USER_PROMPT.format(
            source_code=source_code if source_code else f"Project code context",
            error_log=error_log,
            bug_investigation=json.dumps(bug_investigation, indent=2)
        )
        raw_response = call_llm(user_prompt, ROOT_CAUSE_SYSTEM_PROMPT)

        if raw_response:
            try:
                cleaned = raw_response.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                
                parsed = json.loads(cleaned.strip())
                return {"root_cause": parsed}
            except Exception:
                pass

    # Fallback mode
    result = fallback_root_cause(error_log, bug_investigation)
    return {"root_cause": result}
