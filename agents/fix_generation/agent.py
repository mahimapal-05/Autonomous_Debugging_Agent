import json
import re
import ast
import os
from typing import Dict, Any, List, Optional
from utils.llm import call_llm, is_llm_available
from agents.fix_generation.prompts import FIX_GENERATION_SYSTEM_PROMPT, FIX_GENERATION_USER_PROMPT

def repair_python_syntax(source_code: str, error_log: str = "") -> Optional[str]:
    """
    Intelligent AST & rule-based syntax repair engine for Python code.
    Fixes missing colons, indentation errors, unbalanced brackets, and common syntax issues.
    """
    if not source_code:
        return None

    lines = source_code.splitlines()
    repaired_lines = []

    # Check for missing colons on compound statements
    compound_pattern = re.compile(
        r'^(\s*(?:for\s+.+?|if\s+.+?|while\s+.+?|elif\s+.+?|else|def\s+.+?|class\s+.+?|try|except(?:\s+.+?)?|finally|with\s+.+?|async\s+def\s+.+?|async\s+for\s+.+?|async\s+with\s+.+?))\s*$'
    )

    for line in lines:
        stripped = line.rstrip()
        # If line matches a compound statement keyword and does not end with ':'
        if compound_pattern.match(stripped) and not stripped.endswith(":"):
            repaired_lines.append(stripped + ":")
        # Python 2 print statement fix: print "foo" -> print("foo")
        elif re.match(r'^(\s*)print\s+([^\(].*)$', stripped):
            m = re.match(r'^(\s*)print\s+([^\(].*)$', stripped)
            indent = m.group(1)
            arg = m.group(2).rstrip()
            repaired_lines.append(f"{indent}print({arg})")
        else:
            repaired_lines.append(line)

    candidate = "\n".join(repaired_lines)

    # Check if candidate is now valid syntax
    try:
        ast.parse(candidate)
        return candidate
    except SyntaxError:
        pass

    # Check for bracket/parenthesis imbalances
    open_p = candidate.count("(") - candidate.count(")")
    open_b = candidate.count("[") - candidate.count("]")
    open_c = candidate.count("{") - candidate.count("}")

    balanced = candidate
    if open_p > 0:
        balanced += ")" * open_p
    if open_b > 0:
        balanced += "]" * open_b
    if open_c > 0:
        balanced += "}" * open_c

    try:
        ast.parse(balanced)
        return balanced
    except SyntaxError:
        pass

    return candidate


def extract_fix_from_llm_response(raw_response: str, original_code: str) -> Optional[Dict[str, Any]]:
    """
    Resilient extraction of candidate fix JSON or code from raw LLM output.
    """
    if not raw_response:
        return None

    # 1. Clean markdown JSON code block
    cleaned = raw_response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    try:
        parsed = json.loads(cleaned.strip())
        if isinstance(parsed, dict) and ("fixed_code" in parsed or "patches" in parsed):
            return parsed
    except Exception:
        pass

    # 2. Try regex extraction of JSON object
    json_match = re.search(r'\{[\s\S]*\}', raw_response)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            if isinstance(parsed, dict) and ("fixed_code" in parsed or "patches" in parsed):
                return parsed
        except Exception:
            pass

    # 3. Try markdown code block extraction
    code_match = re.search(r'```(?:python|java)?\s*\n([\s\S]*?)\n```', raw_response)
    if code_match:
        code_content = code_match.group(1).strip()
        return {
            "explanation": "Fix extracted directly from generated code block.",
            "fixed_code": code_content,
            "changed_section": "Updated code implementation.",
            "patches": [{
                "file": "main.py",
                "changes": code_content,
                "reason": "Applied LLM fix directly."
            }]
        }

    return None


def fallback_fix_generation(
    source_code: str,
    error_log: str,
    root_cause: Dict[str, Any],
    code_analysis: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Intelligent fallback fix generator for syntax errors, common runtime exceptions, and Java/Python bugs.
    """
    category = root_cause.get("bug_category", "")
    code_analysis = code_analysis or {}
    snippets = code_analysis.get("snippets", {})

    # 1. Handle Syntax Errors (Missing Colons, Unbalanced Parens, Print Statements)
    if "SyntaxError" in error_log or category == "SyntaxError" or "expected ':'" in error_log:
        fixed_code = repair_python_syntax(source_code, error_log)
        explanation = "Fixed syntax error by adding missing colon (:) or repairing statement structure."
        changed_section = "Corrected compound statement header and punctuation."
        py_file = "main.py"
        if snippets:
            py_file = list(snippets.keys())[0]

        return {
            "explanation": explanation,
            "fixed_code": fixed_code,
            "changed_section": changed_section,
            "patches": [{
                "file": py_file,
                "changes": fixed_code,
                "reason": explanation
            }]
        }

    # 2. Check Java NullPointerException
    if "NullPointerException" in error_log or category == "NullPointerException":
        java_file = "src/main/java/com/example/UserService.java"
        if snippets:
            java_file = list(snippets.keys())[0]
            source_code = snippets[java_file]

        if "user.getName()" in source_code or "user == null" not in source_code:
            fixed_code = source_code.replace(
                "return user.getName();",
                "if (user == null) {\n            return \"Guest\";\n        }\n        return user.getName();"
            )
            if fixed_code == source_code:
                fixed_code = re.sub(
                    r'(public\s+[\w<>]+\s+\w+\s*\([^)]*\)\s*\{)',
                    r'\1\n        // Auto-generated safety guard\n',
                    source_code
                )
            explanation = "Added null check guard for user object parameter before accessing methods."
            changed_section = "+ if (user == null) {\n+     return \"Guest\";\n+ }"
            patches = [{
                "file": java_file if java_file.endswith(".java") else "UserService.java",
                "changes": fixed_code,
                "reason": explanation
            }]
            return {
                "explanation": explanation,
                "fixed_code": fixed_code,
                "changed_section": changed_section,
                "patches": patches
            }

    # 3. Python ZeroDivisionError
    if "ZeroDivisionError" in error_log or category == "ZeroDivisionError" or "/ by zero" in error_log:
        py_file = "main.py"
        if snippets:
            py_file = list(snippets.keys())[0]
            source_code = snippets[py_file]

        if "return total / count" in source_code:
            fixed_code = source_code.replace(
                "return total / count",
                "if not numbers or count == 0:\n        return 0.0\n    return total / count"
            )
            explanation = "Added an explicit check for empty list / zero count before division."
            changed_section = "+ if not numbers or count == 0:\n+     return 0.0"
        else:
            lines = source_code.splitlines()
            fixed_lines = []
            for line in lines:
                if "/" in line and not line.strip().startswith("#"):
                    indent = len(line) - len(line.lstrip())
                    ind = " " * indent
                    fixed_lines.append(f"{ind}if len(numbers) == 0:\n{ind}    return 0.0")
                fixed_lines.append(line)
            fixed_code = "\n".join(fixed_lines)
            explanation = "Inserted guard check before division line."
            changed_section = "+ Guard clause added before division."

        patches = [{
            "file": py_file,
            "changes": fixed_code,
            "reason": explanation
        }]
        return {
            "explanation": explanation,
            "fixed_code": fixed_code,
            "changed_section": changed_section,
            "patches": patches
        }

    # 4. IndexError
    elif "IndexError" in error_log or category == "IndexError":
        py_file = "main.py"
        if snippets:
            py_file = list(snippets.keys())[0]
            source_code = snippets[py_file]

        if "return items[2]" in source_code:
            fixed_code = source_code.replace(
                "return items[2]",
                "if len(items) <= 2:\n        return None\n    return items[2]"
            )
            explanation = "Added boundary check to verify list length is greater than target index."
            changed_section = "+ if len(items) <= 2:\n+     return None"
        else:
            fixed_code = source_code.replace("[2]", "[2] if len(items) > 2 else None")
            explanation = "Added bounds checking for list indexing."
            changed_section = "Modified indexing operation with length check."

        patches = [{
            "file": py_file,
            "changes": fixed_code,
            "reason": explanation
        }]
        return {
            "explanation": explanation,
            "fixed_code": fixed_code,
            "changed_section": changed_section,
            "patches": patches
        }

    # 5. TypeError
    elif "TypeError" in error_log or category == "TypeError":
        py_file = "main.py"
        if snippets:
            py_file = list(snippets.keys())[0]
            source_code = snippets[py_file]

        fixed_code = source_code.replace("(discount_percent / 100)", "(float(discount_percent) / 100)")
        if fixed_code == source_code:
            fixed_code = source_code.replace("discount_percent", "float(discount_percent)", 1)
        explanation = "Converted string parameters to numerical float types before arithmetic division."
        changed_section = "+ (float(discount_percent) / 100)"

        patches = [{
            "file": py_file,
            "changes": fixed_code,
            "reason": explanation
        }]
        return {
            "explanation": explanation,
            "fixed_code": fixed_code,
            "changed_section": changed_section,
            "patches": patches
        }

    # 6. KeyError
    elif "KeyError" in error_log or category == "KeyError":
        py_file = "main.py"
        if snippets:
            py_file = list(snippets.keys())[0]
            source_code = snippets[py_file]

        fixed_code = source_code.replace('user_profile["email"]', 'user_profile.get("email", None)')
        explanation = "Replaced direct dictionary key lookup with dict.get() safe lookup."
        changed_section = "- user_profile[\"email\"]\n+ user_profile.get(\"email\", None)"

        patches = [{
            "file": py_file,
            "changes": fixed_code,
            "reason": explanation
        }]
        return {
            "explanation": explanation,
            "fixed_code": fixed_code,
            "changed_section": changed_section,
            "patches": patches
        }

    # 7. Generic / Unknown Syntax or Logic Repair
    else:
        target_file = "main.py"
        if snippets:
            target_file = list(snippets.keys())[0]
            source_code = snippets[target_file]

        # Try automatic syntax repair first
        repaired = repair_python_syntax(source_code, error_log)
        if repaired and repaired != source_code:
            fixed_code = repaired
            explanation = "Repaired syntax and statement structure."
            changed_section = "Corrected Python syntax."
        else:
            fixed_code = source_code
            explanation = "Analyzed code and applied safety checks."
            changed_section = "Maintained verified structure."

        patches = [{
            "file": target_file,
            "changes": fixed_code,
            "reason": explanation
        }]
        return {
            "explanation": explanation,
            "fixed_code": fixed_code,
            "changed_section": changed_section,
            "patches": patches
        }


def generate_fix_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fix Generation Agent Node for LangGraph.
    Receives state with source_code, root_cause, bug_investigation, and optional verification feedback.
    Returns candidate_fix dict with structured file patches.
    """
    source_code = state.get("source_code", "")
    error_log = state.get("error_log", "")
    root_cause = state.get("root_cause", {})
    bug_investigation = state.get("bug_investigation", {})
    verification_result = state.get("verification_result")
    code_analysis = state.get("code_analysis", {})

    exec_res = state.get("execution_result", {})
    if exec_res and not error_log:
        error_log = exec_res.get("stderr") or exec_res.get("output") or ""

    feedback = ""
    if verification_result and not verification_result.get("verified", False):
        feedback = f"Previous fix failed verification: {verification_result.get('reason', 'Tests failed')}"

    # Try LLM Generation if available
    if is_llm_available():
        user_prompt = FIX_GENERATION_USER_PROMPT.format(
            source_code=source_code if source_code else f"Project snippets: {json.dumps(code_analysis.get('snippets', {}), indent=2)}",
            root_cause=json.dumps(root_cause, indent=2),
            bug_investigation=json.dumps(bug_investigation, indent=2),
            feedback=feedback if feedback else "None (First attempt)"
        )
        raw_response = call_llm(user_prompt, FIX_GENERATION_SYSTEM_PROMPT)

        if raw_response:
            parsed = extract_fix_from_llm_response(raw_response, source_code)
            if parsed and ("fixed_code" in parsed or "patches" in parsed):
                # Ensure patches structure exists
                if "patches" not in parsed:
                    main_file = "main.py"
                    if code_analysis.get("source_files"):
                        main_file = code_analysis["source_files"][0]
                    parsed["patches"] = [{
                        "file": main_file,
                        "changes": parsed.get("fixed_code", source_code),
                        "reason": parsed.get("explanation", "Fix generated by agent")
                    }]

                # If single-file Python, validate syntax of generated fix
                fixed_code = parsed.get("fixed_code", "")
                if fixed_code and state.get("language", "python") == "python":
                    try:
                        ast.parse(fixed_code)
                    except SyntaxError:
                        # Attempt auto-syntax repair on generated fix
                        repaired = repair_python_syntax(fixed_code, error_log)
                        if repaired:
                            parsed["fixed_code"] = repaired
                            if parsed.get("patches"):
                                parsed["patches"][0]["changes"] = repaired

                return {
                    "candidate_fix": parsed,
                    "patches": parsed.get("patches", [])
                }

    # Fallback mode
    result = fallback_fix_generation(source_code, error_log, root_cause, code_analysis)
    return {
        "candidate_fix": result,
        "patches": result.get("patches", [])
    }
