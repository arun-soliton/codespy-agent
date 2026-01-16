import json
import os
import sys

from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional, Tuple, Union

from clang.cindex import Config

Config.set_library_file(r"C:\Program Files\LLVM\bin\libclang.dll")

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


def write_json_summary(
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
                        "line": callee_info["line"],
                    }
                calls_payload.append(entry)

            methods_entries.append(
                {
                    "name": info["simple"],
                    "qualified": info["qualified"],
                    "location": {
                        "file": info["file"],
                        "line": info["line"],
                    },
                    "calls": calls_payload,
                }
            )

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
                    "line": callee_info["line"],
                }
            calls_payload.append(entry)

        summary_free.append(
            {
                "name": info["simple"],
                "qualified": info["qualified"],
                "location": {
                    "file": info["file"],
                    "line": info["line"],
                },
                "calls": calls_payload,
            }
        )

    summary = {
        "project_root": project_root.as_posix(),
        "classes": summary_classes,
        "free_functions": summary_free,
    }

    output_path = project_root / "analysis.json"
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        "Analysis written to",
        relative_to_project(output_path, project_root),
    )


def sort_paths(items: Iterable[Path]) -> list[Path]:
    return sorted(
        {normalize_path(path) for path in items}, key=lambda item: item.as_posix()
    )


def prepare_inputs(
    raw_targets: Iterable[PathLike],
) -> Tuple[Optional[Path], list[Path], list[Path]]:
    script_root = normalize_path(Path(__file__).resolve().parent)
    cwd_root = normalize_path(Path.cwd())
    search_roots = [script_root, cwd_root]

    resolved_dirs: list[Path] = []
    resolved_files: list[Path] = []
    seen_dirs: set[str] = set()
    seen_files: set[str] = set()

    def add_directory(directory: Path) -> None:
        directory = normalize_path(directory)
        key = directory.as_posix().lower()
        if key in seen_dirs:
            return
        seen_dirs.add(key)
        resolved_dirs.append(directory)
        for candidate in directory.rglob("*.cpp"):
            add_file(candidate)

    def add_file(file_path: Path) -> None:
        file_path = normalize_path(file_path)
        if file_path.suffix.lower() != ".cpp":
            return
        key = file_path.as_posix().lower()
        if key in seen_files:
            return
        seen_files.add(key)
        resolved_files.append(file_path)

    def expand_candidate(raw: PathLike) -> None:
        tokens: list[str | Path]
        if isinstance(raw, Path):
            tokens = [raw]
        else:
            parts = [part.strip() for part in str(raw).split(os.pathsep)]
            tokens = [part for part in parts if part]
            if not tokens:
                tokens = [raw]

        for token in tokens:
            path = Path(token).expanduser()
            normalized = normalize_path(path)
            if normalized.exists():
                if normalized.is_dir():
                    add_directory(normalized)
                elif normalized.is_file():
                    add_file(normalized)
                continue

            located = False
            for root in search_roots:
                candidate = normalize_path(root / path)
                if candidate.exists():
                    if candidate.is_dir():
                        add_directory(candidate)
                    elif candidate.is_file():
                        add_file(candidate)
                    located = True
                    break
            if located:
                continue

            pattern = str(path)
            if any(char in pattern for char in "*?"):
                for root in search_roots:
                    for match in root.glob(pattern):
                        if match.is_dir():
                            add_directory(match)
                        elif match.is_file():
                            add_file(match)
                continue

            name = path.name
            if not name:
                continue
            for root in search_roots:
                for match in root.rglob(name):
                    if match.is_dir():
                        add_directory(match)
                    elif match.is_file():
                        add_file(match)

    for target in raw_targets:
        expand_candidate(target)

    if not resolved_files:
        return None, [], []

    root_candidates = resolved_dirs or [file.parent for file in resolved_files]
    project_root = normalize_path(
        Path(os.path.commonpath([str(path) for path in root_candidates]))
    )

    include_dirs: set[Path] = {project_root}
    include_candidate = project_root / "include"
    if include_candidate.is_dir():
        include_dirs.add(normalize_path(include_candidate))
    for directory in resolved_dirs:
        include_dirs.add(directory)
        dir_include = directory / "include"
        if dir_include.is_dir():
            include_dirs.add(normalize_path(dir_include))
    for file_path in resolved_files:
        include_dirs.add(file_path.parent)

    ordered_sources = sort_paths(resolved_files)
    ordered_includes = sort_paths(include_dirs)
    return project_root, ordered_sources, ordered_includes


def analyze_project(
    project_root: Path,
    source_files: list[Path],
    include_dirs: list[Path],
) -> None:

    index = Index.create()

    function_kinds = {
        CursorKind.CXX_METHOD,
        CursorKind.CONSTRUCTOR,
        CursorKind.DESTRUCTOR,
        CursorKind.FUNCTION_TEMPLATE,
        CursorKind.FUNCTION_DECL,
    }

    classes: dict[str, set[str]] = defaultdict(set)
    free_functions: set[str] = set()
    function_data: dict[str, dict] = {}

    def in_project(cursor: Cursor) -> bool:
        location = cursor.location
        if location.file is None:
            return False
        file_path = normalize_path(Path(location.file.name))
        return file_path == project_root or project_root in file_path.parents

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
                "line": cursor.location.line,
                "calls": set(),
            }
        return usr

    def visit(cursor: Cursor, current_function_usr: Optional[str] = None) -> None:
        if (
            cursor.kind == CursorKind.CLASS_DECL
            and cursor.is_definition()
            and in_project(cursor)
        ):
            class_name = qualified_name(cursor)
            classes.setdefault(class_name, set())

        if (
            cursor.kind in function_kinds
            and cursor.is_definition()
            and in_project(cursor)
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

    include_args = [f"-I{path.as_posix()}" for path in include_dirs]

    for source_file in source_files:
        try:
            tu = index.parse(
                str(source_file),
                args=[
                    "-std=c++17",
                    *include_args,
                ],
            )
        except TranslationUnitLoadError as exc:
            print(f"Error parsing {source_file.name}: {exc}")
            print("Ensure libclang can locate the C++ standard library headers.")
            continue

        for diag in tu.diagnostics:
            print(f"Diagnostic in {source_file.name}: {diag}")

        visit(tu.cursor)

    print("Classes and their associated functions:\n")
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
                calls: set[Tuple[Optional[str], str]] = function_data[usr]["calls"]
                if not calls:
                    print("    calls: (none)")
                    continue
                print("    calls:")
                for callee_usr, callee_name in sorted(calls, key=lambda item: item[1]):
                    if callee_usr and callee_usr in function_data:
                        callee_info = function_data[callee_usr]
                        location = f"{callee_info['file']}:{callee_info['line']}"
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
            calls: set[Tuple[Optional[str], str]] = info["calls"]
            if not calls:
                print("  calls: (none)")
            else:
                print("  calls:")
                for callee_usr, callee_name in sorted(calls, key=lambda item: item[1]):
                    if callee_usr and callee_usr in function_data:
                        callee_info = function_data[callee_usr]
                        location = f"{callee_info['file']}:{callee_info['line']}"
                        print(f"    - {callee_name} [{location}]")
                    else:
                        print(f"    - {callee_name} [external]")
            print()

    write_json_summary(project_root, classes, free_functions, function_data)


def main(*targets: PathLike) -> None:

    raw_targets: list[PathLike]
    if targets:
        raw_targets = list(targets)
    elif len(sys.argv) > 1:
        raw_targets = sys.argv[1:]
    else:
        raw_targets = [Path(__file__).resolve().parent]

    project_root, source_files, include_dirs = prepare_inputs(raw_targets)
    if not project_root or not source_files:
        print("No source files found.")
        return

    analyze_project(project_root, source_files, include_dirs)


if __name__ == "__main__":
    main(*sys.argv[1:])
