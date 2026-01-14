import json
import sys

from collections import defaultdict
from pathlib import Path
from typing import Optional, Tuple

from clang.cindex import Config

Config.set_library_file(r"C:\Program Files\LLVM\bin\libclang.dll")

from clang.cindex import Cursor, CursorKind, Index, TranslationUnitLoadError


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


def main():

    project_root = Path(__file__).resolve().parent
    src_dir = project_root / "cpp_calculator" / "src"
    include_dir = project_root / "cpp_calculator" / "include"

    source_files = sorted(src_dir.glob("*.cpp"))
    if not source_files:
        print("No source files found.")
        return

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

    for source_file in source_files:
        try:
            tu = index.parse(
                str(source_file),
                args=[
                    "-std=c++17",
                    f"-I{include_dir}",
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


if __name__ == "__main__":
    main()
