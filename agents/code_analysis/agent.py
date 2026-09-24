import ast
import os
import re
from typing import Dict, Any, List, Set

def calculate_cyclomatic_complexity(node: ast.AST) -> int:
    """Computes McCabe cyclomatic complexity for an AST subtree."""
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.AsyncWith)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
        elif isinstance(child, ast.IfExp):
            complexity += 1
    return complexity

def detect_semantic_anti_patterns(tree: ast.AST, source_code: str) -> List[Dict[str, Any]]:
    """Detects advanced semantic anti-patterns and subtle bugs in Python AST."""
    issues = []
    builtins_set = {"sum", "list", "dict", "set", "min", "max", "type", "id", "input", "print", "len", "range", "map", "filter", "all", "any", "format", "open"}

    for node in ast.walk(tree):
        # 1. Mutable Default Arguments
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults + node.args.kw_defaults:
                if default and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    issues.append({
                        "type": "MutableDefaultArgument",
                        "location": f"line {node.lineno} in {node.name}()",
                        "severity": "HIGH",
                        "description": f"Function `{node.name}` defines mutable default argument (list/dict/set). This retains state across multiple function calls."
                    })

        # 2. Modifying List/Dict while iterating
        if isinstance(node, (ast.For, ast.AsyncFor)):
            if isinstance(node.iter, ast.Name):
                target_var = node.iter.id
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                        if isinstance(sub.func.value, ast.Name) and sub.func.value.id == target_var:
                            if sub.func.attr in {"remove", "pop", "append", "extend", "insert", "clear"}:
                                issues.append({
                                    "type": "IterationMutation",
                                    "location": f"line {node.lineno}",
                                    "severity": "CRITICAL",
                                    "description": f"Mutating collection `{target_var}` (calling `.{sub.func.attr}()`) while iterating over it causes skipped elements or invalid bounds."
                                })

        # 3. Shadowed Builtins
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id in builtins_set:
                issues.append({
                    "type": "ShadowedBuiltin",
                    "location": f"line {getattr(node, 'lineno', '?')}",
                    "severity": "MEDIUM",
                    "description": f"Variable `{node.id}` shadows Python standard library builtin `{node.id}()`."
                })

        # 4. Bare Except Clauses
        if isinstance(node, ast.ExceptHandler):
            if node.type is None or (isinstance(node.type, ast.Name) and node.type.id == "BaseException"):
                issues.append({
                    "type": "BareExcept",
                    "location": f"line {node.lineno}",
                    "severity": "MEDIUM",
                    "description": "Bare `except:` catches SystemExit, KeyboardInterrupt, and masks critical syntax or name errors."
                })

        # 5. Float Equality Check
        if isinstance(node, ast.Compare):
            for op in node.ops:
                if isinstance(op, (ast.Eq, ast.NotEq)):
                    for comp in [node.left] + node.comparators:
                        if isinstance(comp, ast.Constant) and isinstance(comp.value, float):
                            issues.append({
                                "type": "FloatEqualityComparison",
                                "location": f"line {node.lineno}",
                                "severity": "HIGH",
                                "description": "Exact floating point equality comparison (`==`) is brittle due to IEEE 754 precision limits. Use `math.isclose()` instead."
                            })

    return issues

def detect_algorithmic_archetypes(source_code: str, tree: ast.AST) -> List[str]:
    """Identifies algorithmic patterns and data structures present in code."""
    patterns = []
    text = source_code.lower()

    if "class " in source_code and ("treenode" in text or "left" in text and "right" in text):
        patterns.append("BinaryTree / TreeNode")
    if "class " in source_code and ("listnode" in text or ".next" in text):
        patterns.append("LinkedList / ListNode")
    if "heapq" in text or "heappush" in text or "heappop" in text or "minheap" in text:
        patterns.append("Heap / PriorityQueue")
    if "queue" in text or "deque" in text:
        patterns.append("Queue / Deque")
    if "memo" in text or "cache" in text or "dp" in text or "@lru_cache" in text:
        patterns.append("DynamicProgramming / Memoization")
    if "def " in source_code and ("low" in text and "high" in text and "mid" in text or "binary_search" in text):
        patterns.append("BinarySearch")
    if "left" in text and "right" in text and ("while left < right" in text or "while left <= right" in text):
        patterns.append("TwoPointers / SlidingWindow")
    if "visited" in text or "adj" in text or "graph" in text or "neighbors" in text or "bfs" in text or "dfs" in text:
        patterns.append("GraphTraversal (BFS/DFS)")
    if "matrix" in text or "grid" in text or "row" in text and "col" in text:
        patterns.append("Matrix / 2DGrid")

    return patterns

def parse_python_ast(source_code: str) -> Dict[str, Any]:
    """
    Deep Industrial-Grade AST Parser and Semantic Code Graph Analyzer.
    Extracts structural components, cyclomatic complexity, anti-patterns, and algorithmic archetypes.
    """
    result = {
        "functions": [],
        "function_signatures": {},
        "classes": [],
        "class_methods": {},
        "imports": [],
        "variables": [],
        "syntax_valid": True,
        "syntax_error": None,
        "cyclomatic_complexity": 1,
        "semantic_issues": [],
        "algorithmic_archetypes": [],
        "incomplete_functions": [],
        "missing_returns": [],
        "summary": ""
    }

    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        result["syntax_valid"] = False
        result["syntax_error"] = f"SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}"
        result["summary"] = f"Invalid Python syntax at line {e.lineno}: {e.msg}"
        return result
    except Exception as e:
        result["syntax_valid"] = False
        result["syntax_error"] = str(e)
        result["summary"] = f"Parsing error: {str(e)}"
        return result

    functions = []
    function_signatures = {}
    classes = []
    class_methods = {}
    imports = []
    variables = set()
    incomplete_functions = []
    missing_returns = []

    # Calculate overall cyclomatic complexity
    total_complexity = calculate_cyclomatic_complexity(tree)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
            args_list = [a.arg for a in node.args.args]
            function_signatures[node.name] = {
                "args": args_list,
                "complexity": calculate_cyclomatic_complexity(node),
                "has_docstring": ast.get_docstring(node) is not None,
                "lineno": node.lineno
            }
            
            # Check stubs
            is_stub = False
            if len(node.body) == 1:
                first = node.body[0]
                if isinstance(first, ast.Pass) or (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and first.value.value is Ellipsis):
                    is_stub = True
                elif isinstance(first, ast.Raise) and isinstance(first.exc, ast.Call) and getattr(first.exc.func, "id", "") == "NotImplementedError":
                    is_stub = True
            if is_stub:
                incomplete_functions.append(node.name)

            has_return = any(isinstance(b, ast.Return) for b in ast.walk(node))
            if not has_return and not is_stub:
                missing_returns.append(node.name)

        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(item.name)
            class_methods[node.name] = methods

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            variables.add(node.id)

    # Detect anti-patterns and algorithms
    semantic_issues = detect_semantic_anti_patterns(tree, source_code)
    archetypes = detect_algorithmic_archetypes(source_code, tree)

    result["functions"] = sorted(list(set(functions)))
    result["function_signatures"] = function_signatures
    result["classes"] = sorted(list(set(classes)))
    result["class_methods"] = class_methods
    result["imports"] = sorted(list(set(imports)))
    result["variables"] = sorted(list(variables))
    result["cyclomatic_complexity"] = total_complexity
    result["semantic_issues"] = semantic_issues
    result["algorithmic_archetypes"] = archetypes
    result["incomplete_functions"] = incomplete_functions
    result["missing_returns"] = missing_returns

    fn_str = ", ".join(result["functions"]) if result["functions"] else "None"
    cls_str = ", ".join(result["classes"]) if result["classes"] else "None"
    archetype_str = f" [Patterns: {', '.join(archetypes)}]" if archetypes else ""
    issue_str = f" [Potential Issues: {len(semantic_issues)} flagged]" if semantic_issues else ""
    
    result["summary"] = (
        f"Valid AST. Cyclomatic Complexity: {total_complexity}. "
        f"Functions ({len(result['functions'])}): [{fn_str}], Classes ({len(result['classes'])}): [{cls_str}]."
        f"{archetype_str}{issue_str}"
    )

    return result

def analyze_code_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Code Analysis Agent Node for LangGraph.
    Handles both single-file mode and full multi-file project analysis.
    """
    project_path = state.get("project_path")
    language = state.get("language", "python")

    if project_path and os.path.exists(project_path):
        if language == "java":
            adapter = JavaAdapter(project_path)
        else:
            adapter = PythonAdapter(project_path)

        analysis = adapter.analyze_project()
        summary_info = adapter.get_project_summary()

        analysis_result = {
            "is_project": True,
            "language": language,
            "build_system": summary_info.get("build_system", "unknown"),
            "functions": [],
            "classes": [],
            "imports": [],
            "source_files": analysis.get("source_files", []),
            "test_files": analysis.get("test_files", []),
            "syntax_valid": True,
            "summary": summary_info.get("summary_text", f"Analyzed {language.capitalize()} project."),
            "snippets": summary_info.get("snippets", {})
        }
        return {
            "code_analysis": analysis_result,
            "source_files": analysis.get("source_files", []),
            "test_files": analysis.get("test_files", [])
        }

    # Single-file mode
    source_code = state.get("source_code", "")
    analysis_result = parse_python_ast(source_code)
    analysis_result["is_project"] = False

    return {
        "code_analysis": analysis_result
    }

