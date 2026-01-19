import json
import os
import sys

from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional, Tuple, Union

from clang.cindex import Config

# ============================================================================
# CONFIGURATION - MODIFY THESE VALUES
# ============================================================================

# Path to libclang.dll
LIBCLANG_PATH = r"C:\Program Files\LLVM\bin\libclang.dll"

# Target: Can be either a directory or a specific .cpp file
# If directory: will analyze all .cpp files in that directory (non-recursive)
# If file: will analyze only that specific .cpp file
TARGET_PATH = r"D:\Source Codes\AI\knowledge-graph\cpp_calculator\src\Calculator.cpp"  # CHANGE THIS

# Output configuration
OUTPUT_DIR = r"D:\Source Codes\AI\knowledge-graph\output"  # Directory where analysis.json will be saved
OUTPUT_FILENAME = "analysis.json"  # Name of the output JSON file

# Additional include directories (optional)
ADDITIONAL_INCLUDE_DIRS = [
    # Add any additional include directories your CPP files need
    # r"C:\path\to\includes",
    r"D:\Source Codes\AI\knowledge-graph\cpp_calculator\include"
]

# ============================================================================

Config.set_library_file(LIBCLANG_PATH)

from clang.cindex import Cursor, CursorKind, Index, TranslationUnitLoadError

PathLike = Union[str, Path]


def qualified_name(cursor: Cursor) -> str:
    names = []
    current = cursor
    while current and current.kind != CursorKind.TRANSLATION_UNIT:
        name = current.spelling or current.displayname
        if name:
            names.append(name)
        current = current.semantic_parent
    if not names:
        return cursor.displayname or "<anonymous>"
    return "::".join(reversed(names))


def normalize_path(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def relative_to_project(path: Path, project_root: Path) -> str:
    path = normalize_path(path)
    project_root = normalize_path(project_root)
    if path == project_root:
        return "."
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def extract_comment_text(cursor: Cursor) -> Optional[str]:
    """Return a cleaned comment string attached to the cursor, if any."""
    comment = cursor.brief_comment
    if comment:
        stripped = comment.strip()
        return stripped or None

    raw_comment = cursor.raw_comment
    if not raw_comment:
        return None

    raw_comment = raw_comment.strip()
    if raw_comment.startswith("/*"):
        raw_comment = raw_comment[2:]
    if raw_comment.endswith("*/"):
        raw_comment = raw_comment[:-2]

    cleaned_lines: list[str] = []
    for line in raw_comment.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("*"):
            stripped_line = stripped_line[1:].lstrip()

        for prefix in ("///", "//!<", "//!>", "//!", "//"):
            if stripped_line.startswith(prefix):
                stripped_line = stripped_line[len(prefix) :].lstrip()
                break

        cleaned_lines.append(stripped_line)

    cleaned = " ".join(part for part in cleaned_lines if part)
    cleaned = cleaned.strip()
    return cleaned or None


def build_include_dirs(base_path: Path) -> list[Path]:
    """Build list of include directories for parsing."""
    include_dirs = [base_path]

    # Add additional hardcoded include directories
    for include_path in ADDITIONAL_INCLUDE_DIRS:
        include_dir = Path(include_path)
        if include_dir.exists():
            include_dirs.append(normalize_path(include_dir))

    # Check for common include directory patterns
    include_candidate = base_path / "include"
    if include_candidate.is_dir():
        include_dirs.append(normalize_path(include_candidate))

    return include_dirs


def print_analysis_results(
    classes: dict[str, set[str]],
    free_functions: set[str],
    function_data: dict[str, dict],
) -> None:
    """Print formatted analysis results to console."""
    print("=" * 70)
    print("ANALYSIS RESULTS")
    print("=" * 70)

    print("\nClasses and their associated functions:\n")
    if not classes:
        print("No classes found.")
    else:
        for class_name in sorted(classes):
            print(f"Class: {class_name}")
            methods = sorted(
                (function_data[usr]["simple"], usr)
                for usr in classes[class_name]
                if usr in function_data
            )
            if not methods:
                print("  (no methods found)")
            for method_name, usr in methods:
                print(f"  - {method_name}")
                desc = function_data[usr].get("description")
                if desc:
                    print(f"    description: {desc}")
                calls: set[Tuple[Optional[str], str]] = function_data[usr]["calls"]
                if not calls:
                    print("    calls: (none)")
                    continue
                print("    calls:")
                for callee_usr, callee_name in sorted(calls, key=lambda item: item[1]):
                    if callee_usr and callee_usr in function_data:
                        callee_info = function_data[callee_usr]
                        location = f"{callee_info['file']}:{callee_info['start_line']}-{callee_info['end_line']}"
                        print(f"      - {callee_name} [{location}]")
                    else:
                        print(f"      - {callee_name} [external]")
            print()

    if free_functions:
        print("Standalone functions:\n")
        for usr in sorted(
            free_functions, key=lambda item: function_data[item]["qualified"]
        ):
            info = function_data[usr]
            print(f"Function: {info['qualified']}")
            if info.get("description"):
                print(f"  description: {info['description']}")
            calls: set[Tuple[Optional[str], str]] = info["calls"]
            if not calls:
                print("  calls: (none)")
            else:
                print("  calls:")
                for callee_usr, callee_name in sorted(calls, key=lambda item: item[1]):
                    if callee_usr and callee_usr in function_data:
                        callee_info = function_data[callee_usr]
                        location = f"{callee_info['file']}:{callee_info['start_line']}-{callee_info['end_line']}"
                        print(f"    - {callee_name} [{location}]")
                    else:
                        print(f"    - {callee_name} [external]")
            print()


def write_json_summary(
    output_dir: Path,
    output_filename: str,
    project_root: Path,
    classes: dict[str, set[str]],
    free_functions: set[str],
    function_data: dict[str, dict],
) -> None:
    summary_classes: list[dict[str, object]] = []
    for class_name in sorted(classes):
        methods_entries: list[dict[str, object]] = []
        methods = sorted(
            (function_data[usr]["simple"], usr)
            for usr in classes[class_name]
            if usr in function_data
        )
        for _, usr in methods:
            info = function_data[usr]
            calls_payload: list[dict[str, object]] = []
            for callee_usr, callee_name in sorted(
                info["calls"], key=lambda item: item[1]
            ):
                entry: dict[str, object] = {
                    "name": callee_name,
                    "qualified": callee_name,
                    "external": True,
                }
                if callee_usr and callee_usr in function_data:
                    callee_info = function_data[callee_usr]
                    entry["qualified"] = callee_info["qualified"]
                    entry["external"] = False
                    entry["location"] = {
                        "file": callee_info["file"],
                        "start_line": callee_info["start_line"],
                        "end_line": callee_info["end_line"],
                    }
                calls_payload.append(entry)

            methods_entries.append(
                {
                    "name": info["simple"],
                    "qualified": info["qualified"],
                    "location": {
                        "file": info["file"],
                        "start_line": info["start_line"],
                        "end_line": info["end_line"],
                    },
                    "calls": calls_payload,
                }
            )
            description = info.get("description")
            if description:
                methods_entries[-1]["description"] = description

        summary_classes.append(
            {
                "name": class_name,
                "methods": methods_entries,
            }
        )

    summary_free: list[dict[str, object]] = []
    for usr in sorted(
        free_functions, key=lambda item: function_data[item]["qualified"]
    ):
        info = function_data[usr]
        calls_payload: list[dict[str, object]] = []
        for callee_usr, callee_name in sorted(info["calls"], key=lambda item: item[1]):
            entry = {
                "name": callee_name,
                "qualified": callee_name,
                "external": True,
            }
            if callee_usr and callee_usr in function_data:
                callee_info = function_data[callee_usr]
                entry["qualified"] = callee_info["qualified"]
                entry["external"] = False
                entry["location"] = {
                    "file": callee_info["file"],
                    "start_line": callee_info["start_line"],
                    "end_line": callee_info["end_line"],
                }
            calls_payload.append(entry)

        summary_free.append(
            {
                "name": info["simple"],
                "qualified": info["qualified"],
                "location": {
                    "file": info["file"],
                    "start_line": info["start_line"],
                    "end_line": info["end_line"],
                },
                "calls": calls_payload,
            }
        )
        description = info.get("description")
        if description:
            summary_free[-1]["description"] = description

    summary = {
        "project_root": project_root.as_posix(),
        "classes": summary_classes,
        "free_functions": summary_free,
    }

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / output_filename

    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nAnalysis written to: {output_path.absolute()}")


def create_analysis_visitors(
    project_root: Path,
    in_project_predicate,
    classes: dict[str, set[str]],
    free_functions: set[str],
    function_data: dict[str, dict],
):
    """Create the visitor functions for AST traversal.

    Args:
        project_root: Root directory for relative path calculations
        in_project_predicate: Function that takes a Cursor and returns bool
        classes: Dictionary to store class information
        free_functions: Set to store free function USRs
        function_data: Dictionary to store function metadata

    Returns:
        Tuple of (record_function, visit) functions
    """
    function_kinds = {
        CursorKind.CXX_METHOD,
        # CursorKind.CONSTRUCTOR,
        # CursorKind.DESTRUCTOR,
        CursorKind.FUNCTION_TEMPLATE,
        CursorKind.FUNCTION_DECL,
    }

    def record_function(cursor: Cursor) -> Optional[str]:
        if not cursor.location.file:
            return None
        usr = cursor.get_usr()
        if not usr:
            return None
        if usr not in function_data:
            file_path = normalize_path(Path(cursor.location.file.name))
            function_data[usr] = {
                "qualified": qualified_name(cursor),
                "simple": cursor.spelling or cursor.displayname or "<anonymous>",
                "file": relative_to_project(file_path, project_root),
                "start_line": cursor.extent.start.line,
                "end_line": cursor.extent.end.line,
                "calls": set(),
                "description": extract_comment_text(cursor),
            }
        else:
            if not function_data[usr].get("description"):
                comment_text = extract_comment_text(cursor)
                if comment_text:
                    function_data[usr]["description"] = comment_text
        return usr

    def visit(cursor: Cursor, current_function_usr: Optional[str] = None) -> None:
        if (
            cursor.kind == CursorKind.CLASS_DECL
            and cursor.is_definition()
            and in_project_predicate(cursor)
        ):
            class_name = qualified_name(cursor)
            classes.setdefault(class_name, set())

        if (
            cursor.kind in function_kinds
            and cursor.is_definition()
            and in_project_predicate(cursor)
        ):
            usr = record_function(cursor)
            if usr is None:
                for child in cursor.get_children():
                    visit(child, current_function_usr)
                return

            parent = cursor.semantic_parent
            if parent and parent.kind == CursorKind.CLASS_DECL and parent.spelling:
                class_name = qualified_name(parent)
                classes[class_name].add(usr)
            else:
                free_functions.add(usr)

            for child in cursor.get_children():
                visit(child, usr)
            return

        if (
            cursor.kind == CursorKind.CALL_EXPR
            and current_function_usr
            and current_function_usr in function_data
        ):
            referenced = cursor.referenced
            callee_usr: Optional[str] = None
            callee_name: str
            if referenced is not None:
                callee_usr = referenced.get_usr() or None
                callee_name = qualified_name(referenced)
            else:
                callee_name = cursor.displayname or cursor.spelling or "<unknown>"
            if callee_name:
                function_data[current_function_usr]["calls"].add(
                    (callee_usr, callee_name)
                )

        for child in cursor.get_children():
            visit(child, current_function_usr)

    return record_function, visit


def analyze_single_file(
    cpp_file_path: Path, output_dir: Path, output_filename: str
) -> None:
    """Analyze a single CPP file."""

    if not cpp_file_path.exists():
        print(f"Error: File not found: {cpp_file_path}")
        return

    if cpp_file_path.suffix.lower() != ".cpp":
        print(f"Warning: File does not have .cpp extension: {cpp_file_path}")

    # Use the file's directory as the project root
    project_root = cpp_file_path.parent

    # Build include directories
    include_dirs = build_include_dirs(project_root)

    print(f"Analyzing file: {cpp_file_path}")
    print(f"Project root: {project_root}")
    print(f"Include directories: {[str(d) for d in include_dirs]}\n")

    index = Index.create()

    # Initialize data structures
    classes: dict[str, set[str]] = defaultdict(set)
    free_functions: set[str] = set()
    function_data: dict[str, dict] = {}

    # Define predicate for this file
    normalized_cpp_file = normalize_path(cpp_file_path)

    def in_project(cursor: Cursor) -> bool:
        """Check if cursor is in the target file."""
        location = cursor.location
        if location.file is None:
            return False
        file_path = normalize_path(Path(location.file.name))
        return file_path == normalized_cpp_file

    # Create visitor functions
    record_function, visit = create_analysis_visitors(
        project_root, in_project, classes, free_functions, function_data
    )

    # Parse the file
    include_args = [f"-I{path.as_posix()}" for path in include_dirs]

    try:
        tu = index.parse(
            str(cpp_file_path),
            args=["-std=c++17", *include_args],
        )
    except TranslationUnitLoadError as exc:
        print(f"Error parsing {cpp_file_path.name}: {exc}")
        print("Ensure libclang can locate the C++ standard library headers.")
        return

    # Show diagnostics
    has_errors = False
    for diag in tu.diagnostics:
        if diag.severity >= 3:  # Error or Fatal
            has_errors = True
        print(f"Diagnostic in {cpp_file_path.name}: {diag}")

    if has_errors:
        print("\nWarning: There were parsing errors. Results may be incomplete.\n")

    # Traverse and analyze
    visit(tu.cursor)

    # Print and save results
    print_analysis_results(classes, free_functions, function_data)
    write_json_summary(
        output_dir,
        output_filename,
        project_root,
        classes,
        free_functions,
        function_data,
    )
    print("=" * 70)


def analyze_directory(
    directory_path: Path, output_dir: Path, output_filename: str
) -> None:
    """Analyze all CPP files in a directory (non-recursive)."""

    if not directory_path.exists():
        print(f"Error: Directory not found: {directory_path}")
        return

    if not directory_path.is_dir():
        print(f"Error: Path is not a directory: {directory_path}")
        return

    # Find all .cpp files in the directory
    cpp_files = list(directory_path.glob("*.cpp"))

    if not cpp_files:
        print(f"No .cpp files found in directory: {directory_path}")
        return

    print(f"Found {len(cpp_files)} CPP file(s) in directory: {directory_path}")
    print(f"Files to analyze: {[f.name for f in cpp_files]}")
    print(f"Project root: {directory_path}")
    print(f"Output will be saved to: {output_dir / output_filename}\n")

    # Build include directories
    include_dirs = build_include_dirs(directory_path)
    print(f"Include directories: {[str(d) for d in include_dirs]}\n")

    index = Index.create()

    # Initialize data structures
    classes: dict[str, set[str]] = defaultdict(set)
    free_functions: set[str] = set()
    function_data: dict[str, dict] = {}

    # Define predicate for multiple files
    normalized_cpp_files = [normalize_path(cpp_file) for cpp_file in cpp_files]

    def in_project(cursor: Cursor) -> bool:
        """Check if cursor is in any of the target files."""
        location = cursor.location
        if location.file is None:
            return False
        file_path = normalize_path(Path(location.file.name))
        return file_path in normalized_cpp_files

    # Create visitor functions
    record_function, visit = create_analysis_visitors(
        directory_path, in_project, classes, free_functions, function_data
    )

    # Parse all CPP files
    include_args = [f"-I{path.as_posix()}" for path in include_dirs]

    for cpp_file in cpp_files:
        print(f"Parsing: {cpp_file.name}...")
        try:
            tu = index.parse(
                str(cpp_file),
                args=["-std=c++17", *include_args],
            )
        except TranslationUnitLoadError as exc:
            print(f"Error parsing {cpp_file.name}: {exc}")
            print("Ensure libclang can locate the C++ standard library headers.")
            continue

        # Show diagnostics
        has_errors = False
        for diag in tu.diagnostics:
            if diag.severity >= 3:  # Error or Fatal
                has_errors = True
            print(f"  Diagnostic: {diag}")

        if has_errors:
            print(f"  Warning: There were parsing errors in {cpp_file.name}")

        visit(tu.cursor)

    print()

    # Print and save results
    print_analysis_results(classes, free_functions, function_data)
    write_json_summary(
        output_dir,
        output_filename,
        directory_path,
        classes,
        free_functions,
        function_data,
    )
    print("=" * 70)


def main() -> None:
    """Main entry point."""
    target_path = Path(TARGET_PATH)
    output_dir = Path(OUTPUT_DIR)

    print("=" * 70)
    print("CPP ANALYZER")
    print("=" * 70)
    print(f"Target: {target_path.absolute()}")
    print(f"Output: {output_dir.absolute() / OUTPUT_FILENAME}")
    print("=" * 70)
    print()

    if not target_path.exists():
        print(f"Error: Target path does not exist: {target_path}")
        return

    if target_path.is_file():
        # Analyze single file
        if target_path.suffix.lower() != ".cpp":
            print(f"Warning: File does not have .cpp extension: {target_path}")
        analyze_single_file(target_path, output_dir, OUTPUT_FILENAME)
    elif target_path.is_dir():
        # Analyze all .cpp files in directory
        analyze_directory(target_path, output_dir, OUTPUT_FILENAME)
    else:
        print(f"Error: Target path is neither a file nor a directory: {target_path}")


if __name__ == "__main__":
    main()
