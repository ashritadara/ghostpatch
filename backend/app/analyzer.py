import ast
from pathlib import Path
import re

from .errors import redact
from .schemas import Analysis, Finding


def analyze(root: Path, repo_id: str) -> Analysis:
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    python_files = [p for p in files if p.endswith(".py")]
    imports: dict[str, list[str]] = {}
    findings: list[Finding] = []
    warnings: list[str] = []
    modules = {p.removesuffix(".py").replace("/", ".").removesuffix(".__init__"): p for p in python_files}
    edges: set[tuple[str, str]] = set()
    for path in python_files:
        source = (root / path).read_text(encoding="utf-8")
        lines = source.splitlines()

        def finding(node: ast.AST | None, category: str, severity: str, message: str, recommendation: str, line: int | None = None):
            number = line or getattr(node, "lineno", None)
            evidence = lines[number - 1].strip()[:500] if number and number <= len(lines) else ""
            findings.append(Finding(id=f"finding-{len(findings) + 1}", file_path=path,
                line=number, category=category, severity=severity, explanation=message,
                evidence=redact(evidence), recommendation=recommendation))

        try:
            tree = ast.parse(source, filename=path)
        except (SyntaxError, ValueError, RecursionError) as exc:
            finding(None, "parse_error", "high", "Python AST parsing failed; no code was executed.", "Review syntax and Python-version compatibility.", getattr(exc, "lineno", None))
            warnings.append(f"Could not parse {path}.")
            imports[path] = []
            continue
        found_imports = []
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found_imports.extend(alias.name for alias in node.names)
                if any(alias.name in {"imp", "optparse", "distutils"} for alias in node.names):
                    finding(node, "compatibility", "medium", "Legacy module import requires compatibility review.", "Consider a supported standard-library alternative and test behavior.")
            elif isinstance(node, ast.ImportFrom):
                package = path.removesuffix(".py").replace("/", ".").split(".")[:-1]
                prefix = ".".join(package[:len(package) - node.level + 1]) if node.level else ""
                base = ".".join(p for p in (prefix, node.module or "") if p)
                found_imports.append(base)
                found_imports.extend(".".join(p for p in (base, a.name) if p) for a in node.names)
            elif isinstance(node, ast.ExceptHandler) and node.type is None:
                finding(node, "reliability", "high", "Bare except also catches interruption and exit signals.", "Catch the specific expected exception types.")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
                if not isinstance(parents.get(node), ast.withitem):
                    finding(node, "resource_handling", "medium", "File handle is not opened directly in a context manager.", "Use a with statement while preserving encoding and error behavior.")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "utcnow":
                finding(node, "compatibility", "medium", "utcnow returns a naive timestamp and is deprecated in Python 3.12.", "Review timezone-aware UTC with explicit compatibility tests.")
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Subscript) for t in node.targets) and isinstance(node.value, ast.Constant) and node.value.value == 0:
                finding(node, "maintainability", "low", "Manual mapping initialization may be simplified.", "Consider defaultdict or setdefault; preserve numeric types, ordering, and empty-input behavior.")
        imports[path] = sorted(set(x for x in found_imports if x))
        for imported in imports[path]:
            if imported in modules and modules[imported] != path:
                edges.add((path, modules[imported]))
        for number, line in enumerate(lines, 1):
            if re.search(r"#.*\b(?:TODO|FIXME)\b", line):
                finding(None, "maintainability", "low", "Developer follow-up marker in source.", "Review the comment before selecting a modernization.", number)
    return Analysis(repository_id=repo_id, files=files, python_file_count=len(python_files),
                    imports=imports, local_dependencies=[{"source": a, "target": b} for a, b in sorted(edges)],
                    findings=findings, warnings=warnings)
