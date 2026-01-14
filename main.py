from pathlib import Path

from clang.cindex import Config

Config.set_library_file(r"C:\Program Files\LLVM\bin\libclang.dll")

from clang.cindex import Index, CursorKind, TranslationUnitLoadError


def main():

    project_root = Path(__file__).resolve().parent
    source_file = project_root / "cpp_calculator" / "src" / "Calculator.cpp"
    include_dir = project_root / "cpp_calculator" / "include"

    index = Index.create()

    try:
        tu = index.parse(
            str(source_file),
            args=[
                "-std=c++17",
                f"-I{include_dir}",
            ],
        )
    except TranslationUnitLoadError as exc:
        print(f"Error parsing translation unit: {exc}")
        print("Ensure libclang can locate the C++ standard library headers.")
        return

    for diag in tu.diagnostics:
        print(f"Diagnostic: {diag}")

    method_kinds = {
        CursorKind.CXX_METHOD,
        CursorKind.CONSTRUCTOR,
        CursorKind.DESTRUCTOR,
        CursorKind.FUNCTION_TEMPLATE,
    }

    classes: dict[str, list[str]] = {}

    def in_project(cursor) -> bool:
        location = cursor.location
        if location.file is None:
            return False
        try:
            file_path = Path(location.file.name).resolve()
        except OSError:
            file_path = Path(location.file.name)
        return file_path == project_root or project_root in file_path.parents

    for cursor in tu.cursor.walk_preorder():
        if not in_project(cursor):
            continue

        if (
            cursor.kind == CursorKind.CLASS_DECL
            and cursor.is_definition()
            and cursor.spelling
        ):
            classes.setdefault(cursor.spelling, [])
            continue

        if cursor.kind in method_kinds:
            parent = cursor.semantic_parent
            if (
                not parent
                or parent.kind != CursorKind.CLASS_DECL
                or not parent.spelling
            ):
                continue
            if not in_project(parent):
                continue
            class_name = parent.spelling
            classes.setdefault(class_name, [])
            method_name = cursor.spelling or "<anonymous>"
            if method_name not in classes[class_name]:
                classes[class_name].append(method_name)

    print("Classes and their associated functions:\n")
    if not classes:
        print("No classes found.")
        return

    for class_name, methods in classes.items():
        print(f"Class: {class_name}")
        if methods:
            for method in methods:
                print(f"  - {method}")
        else:
            print("  (no methods found)")
        print()


if __name__ == "__main__":
    main()
