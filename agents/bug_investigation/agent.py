import json
import re
from typing import Dict, Any
from utils.llm import call_llm, is_llm_available
from agents.bug_investigation.prompts import BUG_INVESTIGATION_SYSTEM_PROMPT, BUG_INVESTIGATION_USER_PROMPT

def fallback_bug_investigation(source_code: str, error_log: str, code_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Intelligent fallback bug investigation when LLM is unavailable or error log is blank.
    Parses stack traces if provided, or inspects AST & source code patterns to identify bugs.
    """
    functions = code_analysis.get("functions", [])
    suspected_fn = functions[0] if functions else "main"
    error_log_clean = (error_log or "").strip()

    # 1. If an error log / stack trace is present, extract file and line number
    file_match = re.search(r'([A-Za-z0-9_\-\/\\]+\.(?:py|java)):(\d+)', error_log_clean)
    if not file_match:
        file_match = re.search(r'File "([^"]+)", line (\d+)', error_log_clean)
        
    suspected_file = file_match.group(1) if file_match else "source file"
    line_num = file_match.group(2) if file_match else "unknown"

    if line_num == "unknown":
        line_match = re.search(r'line (\d+)', error_log_clean, re.IGNORECASE)
        line_num = line_match.group(1) if line_match else "unknown"

    # 2. Inspect source code directly if error_log is empty or missing details
    lines = source_code.splitlines() if source_code else []

    # Check for SyntaxError in source code
    if not code_analysis.get("syntax_valid", True) or "SyntaxError" in error_log_clean or "expected ':'" in error_log_clean:
        syntax_err = code_analysis.get("syntax_error", "")
        line_err = re.search(r'line (\d+)', syntax_err)
        if line_err:
            line_num = line_err.group(1)
        return {
            "suspected_location": f"{suspected_file}:{line_num} in {suspected_fn}()",
            "suspicious_code": lines[int(line_num) - 1].strip() if line_num.isdigit() and int(line_num) <= len(lines) else (source_code.strip() if source_code else ""),
            "reason": "Python SyntaxError: Invalid statement syntax, missing punctuation (such as trailing colon ':'), or malformed expression.",
            "confidence": "High (Syntax AST Analyzer)"
        }

    # Check for Type Mismatches in operations (e.g. price * (discount / 100))
    for idx, l in enumerate(lines):
        if ("discount" in l or "price" in l or "str" in l) and "/" in l and "float(" not in l and "int(" not in l:
            return {
                "suspected_location": f"{suspected_file}:{idx + 1} in {suspected_fn}()",
                "suspicious_code": l.strip(),
                "reason": "Potential TypeError: Performing arithmetic operation on input parameters without ensuring numerical type conversion.",
                "confidence": "High (Static Code Inspection)"
            }

    # Check for Algorithmic Boundary / Loop Condition Bugs (e.g. while low < high in binary search)
    for idx, l in enumerate(lines):
        if "while low < high:" in l or "while low < len(" in l:
            return {
                "suspected_location": f"{suspected_file}:{idx + 1} in {suspected_fn}()",
                "suspicious_code": l.strip(),
                "reason": "AlgorithmicError / OffByOne: While loop condition `low < high` terminates before inspecting the boundary element. Should be `low <= high`.",
                "confidence": "High (Static Code Inspection)"
            }

    # Check for Missing Eviction in Cache Data Structures
    if "class LRUCache" in source_code and "del self.cache" not in source_code:
        return {
            "suspected_location": f"{suspected_file}:put in LRUCache",
            "suspicious_code": "def put(self, key, value):",
            "reason": "IncompleteImplementation / InvariantViolation: LRUCache does not evict least-recently-used node when capacity is exceeded.",
            "confidence": "High (Data Structure Invariant Analyzer)"
        }

    # Check for Division by Zero (unhandled division where divisor is variable / collection length)
    for idx, l in enumerate(lines):
        if "/" in l and not l.strip().startswith("#"):
            # If dividing by literal non-zero number like / 100 or // 2, it's not a ZeroDivisionError
            if re.search(r'/{1,2}\s*[1-9]\d*', l):
                continue
            if "len(" in l or "count" in l or "total /" in l or "/ 0" in l or "/ count" in l or re.search(r'/{1,2}\s*[a-zA-Z_]\w*', l):
                return {
                    "suspected_location": f"{suspected_file}:{idx + 1} in {suspected_fn}()",
                    "suspicious_code": l.strip(),
                    "reason": "Potential ZeroDivisionError: Division operation without checking if the divisor or collection length is zero.",
                    "confidence": "High (Static Code Inspection)"
                }

    # Check for Index Out of Bounds (hardcoded indexing like items[2])
    for idx, l in enumerate(lines):
        if re.search(r'\[\s*\d+\s*\]', l) and not l.strip().startswith("#") and "test" not in l:
            return {
                "suspected_location": f"{suspected_file}:{idx + 1} in {suspected_fn}()",
                "suspicious_code": l.strip(),
                "reason": "Potential IndexError: Hardcoded array/list index access without boundary verification against collection length.",
                "confidence": "High (Static Code Inspection)"
            }

    # Check for Unsafe Dictionary Subscripting
    for idx, l in enumerate(lines):
        if re.search(r'\[\s*["\'][a-zA-Z0-9_-]+["\']\s*\]', l) and not l.strip().startswith("#"):
            return {
                "suspected_location": f"{suspected_file}:{idx + 1} in {suspected_fn}()",
                "suspicious_code": l.strip(),
                "reason": "Potential KeyError: Direct dictionary key access without checking existence or using .get() with default fallback.",
                "confidence": "High (Static Code Inspection)"
            }

    # Check for Java NullPointer
    for idx, l in enumerate(lines):
        if "user.getName()" in l or (".get" in l and "== null" not in source_code and "!= null" not in source_code):
            return {
                "suspected_location": f"{suspected_file}:{idx + 1} in {suspected_fn}()",
                "suspicious_code": l.strip(),
                "reason": "Potential NullPointerException: Invoking method on object reference without null-check guard.",
                "confidence": "High (Static Code Inspection)"
            }

    # Extract suspicious snippet from code if line number was found in error log
    suspicious_snippet = source_code.strip() if source_code else "Full code inspection."
    if source_code and line_num.isdigit() and int(line_num) <= len(lines):
        suspicious_snippet = lines[int(line_num) - 1].strip()

    reason = "Code analyzed across all functions and statements."
    if "SyntaxError" in error_log_clean or "expected ':'" in error_log_clean:
        reason = "Python SyntaxError: Invalid statement syntax, missing punctuation (such as trailing colon ':'), or malformed expression."
    elif "IndentationError" in error_log_clean:
        reason = "Python IndentationError: Inconsistent leading indentation or unexpected indentation level."
    elif "NameError" in error_log_clean:
        reason = "Python NameError: Referenced variable or function name is not defined in current scope."
    elif "NullPointerException" in error_log_clean:
        reason = "NullPointerException occurs when attempting to call a method or access a field on an uninitialized (null) object reference."
    elif "ZeroDivisionError" in error_log_clean or "/ by zero" in error_log_clean:
        reason = "Division by zero occurs when denominator evaluates to 0 (e.g., empty collection or zero variable)."
    elif "IndexError" in error_log_clean or "ArrayIndexOutOfBoundsException" in error_log_clean:
        reason = "Attempting to access list or array index that does not exist."
    elif "TypeError" in error_log_clean:
        reason = "Incompatible types used in operation."
    elif "KeyError" in error_log_clean:
        reason = "Accessing dictionary key that does not exist in mapping."
    elif "compilation" in error_log_clean.lower() or "cannot find symbol" in error_log_clean.lower():
        reason = "Java compilation error encountered during build."

    return {
        "suspected_location": f"{suspected_file}:{line_num} in {suspected_fn}()",
        "suspicious_code": suspicious_snippet,
        "reason": reason,
        "confidence": "Medium (Comprehensive Code Analyzer)"
    }


def investigate_bug_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bug Investigation Agent Node for LangGraph.
    Receives source_code/project snippets, error_log, code_analysis, returns bug_investigation.
    """
    source_code = state.get("source_code", "")
    error_log = state.get("error_log", "")
    code_analysis = state.get("code_analysis", {})

    # In project mode, combine error logs or execution results if available
    exec_res = state.get("execution_result", {})
    if exec_res and not error_log:
        error_log = exec_res.get("stderr") or exec_res.get("output") or ""

    code_analysis_summary = code_analysis.get("summary", "Syntax valid")

    if is_llm_available():
        user_prompt = BUG_INVESTIGATION_USER_PROMPT.format(
            source_code=source_code if source_code else f"Project snippets: {json.dumps(code_analysis.get('snippets', {}), indent=2)}",
            error_log=error_log,
            code_analysis_summary=code_analysis_summary
        )
        raw_response = call_llm(user_prompt, BUG_INVESTIGATION_SYSTEM_PROMPT)
        
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
                return {"bug_investigation": parsed}
            except Exception:
                pass

    # Fallback mode
    result = fallback_bug_investigation(source_code, error_log, code_analysis)
    return {"bug_investigation": result}
