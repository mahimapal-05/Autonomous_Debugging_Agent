import sys
import io
import time
import traceback
import ast
import contextlib
from typing import Dict, Any, Optional

def execute_python_code(
    code: str,
    timeout_seconds: float = 5.0,
    globals_dict: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Executes Python source code in a controlled namespace and captures stdout, stderr,
    execution time, return/local variables, and full tracebacks if exceptions occur.
    """
    if not code or not code.strip():
        return {
            "success": False,
            "stdout": "",
            "stderr": "No code provided to execute.",
            "error_type": "EmptyCodeError",
            "error_message": "Source code is empty.",
            "execution_time_ms": 0.0,
            "variables": {}
        }

    # 1. First validate Python syntax
    try:
        parsed_ast = ast.parse(code)
    except SyntaxError as e:
        tb_lines = traceback.format_exception_only(type(e), e)
        return {
            "success": False,
            "stdout": "",
            "stderr": "".join(tb_lines).strip(),
            "error_type": "SyntaxError",
            "error_message": f"SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}",
            "lineno": e.lineno,
            "execution_time_ms": 0.0,
            "variables": {}
        }

    # 2. Setup execution environment
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    exec_globals = {
        "__name__": "__main__",
        "__doc__": None,
        "sys": sys,
        "time": time
    }
    if globals_dict:
        exec_globals.update(globals_dict)

    exec_locals = {}
    start_time = time.perf_counter()
    success = True
    error_type = None
    error_message = None
    lineno = None

    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            compiled_code = compile(parsed_ast, filename="<web_interpreter>", mode="exec")
            exec(compiled_code, exec_globals, exec_locals)
    except Exception as e:
        success = False
        error_type = type(e).__name__
        error_message = str(e)
        
        # Extract traceback with line numbers
        exc_type, exc_value, exc_tb = sys.exc_info()
        formatted_tb = traceback.format_exception(exc_type, exc_value, exc_tb)
        
        # Find offending line inside user script
        for frame in traceback.extract_tb(exc_tb):
            if frame.filename == "<web_interpreter>":
                lineno = frame.lineno

        stderr_capture.write("".join(formatted_tb))

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # Filter serializable variables for state inspection
    safe_variables = {}
    combined_scope = {**exec_globals, **exec_locals}
    for k, v in combined_scope.items():
        if k.startswith("__") or k in {"sys", "time"}:
            continue
        try:
            # String representation limited to 300 chars
            v_str = repr(v)
            if len(v_str) > 300:
                v_str = v_str[:300] + "..."
            safe_variables[k] = {
                "type": type(v).__name__,
                "value": v_str
            }
        except Exception:
            pass

    return {
        "success": success,
        "stdout": stdout_capture.getvalue(),
        "stderr": stderr_capture.getvalue(),
        "error_type": error_type,
        "error_message": error_message,
        "lineno": lineno,
        "execution_time_ms": elapsed_ms,
        "variables": safe_variables
    }

def run_code_with_test_driver(
    solution_code: str,
    test_invocation_code: str
) -> Dict[str, Any]:
    """
    Executes solution code concatenated with a test invocation driver.
    Useful for self-correcting validation loops.
    """
    full_script = f"{solution_code}\n\n# Test Driver\n{test_invocation_code}"
    return execute_python_code(full_script)
