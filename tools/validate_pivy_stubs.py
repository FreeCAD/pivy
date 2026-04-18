#!/usr/bin/env python

import argparse
import ast
import os
import re
import subprocess
import sys
import tempfile

from tools.pivy_stub_validation_data import (
    ARRAY_METHOD_CHECKS,
    CALLBACK_METHOD_CHECKS,
    DEFERRED_RAW_ATTRIBUTE_CHECKS,
    DEFERRED_RAW_METHOD_CHECKS,
    DOC_TYPED_METHOD_CHECKS,
    EXTEND_HELPER_METHOD_CHECKS,
    GENERATED_HEADER,
    ITER_CONTAINER_TYPES,
    MULTIFIELD_METHOD_CHECKS,
    MYPY_SNIPPET,
    OPERATOR_METHOD_CHECKS,
    POINTER_HELPER_METHOD_CHECKS,
    POINTER_HELPER_TYPES,
    PROPERTY_ATTRIBUTE_CHECKS,
    PYTHON_HELPER_METHOD_CHECKS,
    REQUIRED_STUBS,
    RUNTIME_UNSUPPORTED_METHOD_CHECKS,
    RUNTIME_UNSUPPORTED_NOTE,
    SENSOR_CALLBACK_CLASSES,
    SOQT_COIN_DUPLICATE_CLASSES,
    STUB_SPECS,
    StubKind,
    TYPEDEF_AND_STRING_METHOD_CHECKS,
    UNSUPPORTED_ARRAY_METHOD_CHECKS,
    UNSUPPORTED_REFERENCE_METHOD_CHECKS,
)


BARE_METHOD_RE = re.compile(r"^    def [^(]+\([^)]*\): \.\.\.$", re.MULTILINE)


def parse_stub(path):
    with open(path) as stub_file:
        text = stub_file.read()
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as exc:
        raise AssertionError("%s is not valid Python syntax: %s" % (path, exc))
    return text, tree


def is_top_level_statement(line):
    return bool(line) and not line.startswith((" ", "\t", "#"))


def assert_generated_header(path, text):
    if not text.startswith(GENERATED_HEADER):
        raise AssertionError("%s is missing the generated stub header" % path)


def assert_no_bare_method_stubs(path, text):
    bare_methods = BARE_METHOD_RE.findall(text)
    if bare_methods:
        raise AssertionError(
            "%s has unresolved bare method stubs: %s"
            % (path, ", ".join(method.strip() for method in bare_methods))
        )


def assert_swig_meta_setattr(path, tree):
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "_SwigNonDynamicMeta":
            continue
        for item in node.body:
            if not isinstance(item, ast.FunctionDef) or item.name != "__setattr__":
                continue
            decorators = [
                decorator.id
                for decorator in item.decorator_list
                if isinstance(decorator, ast.Name)
            ]
            if "classmethod" in decorators:
                raise AssertionError(
                    "%s has an invalid @classmethod on _SwigNonDynamicMeta.__setattr__"
                    % path
                )
            return
        raise AssertionError("%s is missing _SwigNonDynamicMeta.__setattr__" % path)

    raise AssertionError("%s is missing _SwigNonDynamicMeta" % path)


def annotation_text(node):
    if node is None:
        return None
    return ast.unparse(node)


def class_map(tree):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }


def method_map(node):
    return {
        item.name: item
        for item in node.body
        if isinstance(item, ast.FunctionDef)
    }


def methods_named(node, name):
    return [
        item
        for item in node.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    ]


def argument_annotations(method):
    return {
        arg.arg: annotation_text(arg.annotation)
        for arg in method.args.args
    }


def assert_swig_thisown_annotations(path, tree):
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, ast.AnnAssign):
                continue
            if not isinstance(item.target, ast.Name) or item.target.id != "thisown":
                continue
            if annotation_text(item.annotation) != "bool":
                raise AssertionError("%s has a non-bool thisown annotation" % path)


def assert_pointer_helper_classes(path, tree):
    classes = class_map(tree)
    for class_name, value_type in POINTER_HELPER_TYPES.items():
        node = classes.get(class_name)
        if node is None:
            raise AssertionError("%s is missing %s" % (path, class_name))

        methods = method_map(node)
        checks = (
            ("assign", "None", (("value", value_type),)),
            ("value", value_type, ()),
            ("cast", "Any", ()),
            ("frompointer", class_name, (("t", "Any"),)),
        )
        for method_name, return_type, args in checks:
            method = methods.get(method_name)
            if method is None:
                raise AssertionError(
                    "%s is missing %s.%s" % (path, class_name, method_name)
                )
            if annotation_text(method.returns) != return_type:
                raise AssertionError(
                    "%s has an unexpected %s.%s return annotation"
                    % (path, class_name, method_name)
                )
            for arg_name, arg_type in args:
                for arg in method.args.args:
                    if arg.arg == arg_name:
                        if annotation_text(arg.annotation) != arg_type:
                            raise AssertionError(
                                "%s has an unexpected %s.%s %s annotation"
                                % (path, class_name, method_name, arg_name)
                            )
                        break
                else:
                    raise AssertionError(
                        "%s is missing %s.%s %s argument"
                        % (path, class_name, method_name, arg_name)
                    )


def assert_iter_container_classes(path, tree):
    classes = class_map(tree)
    for class_name, element_type in ITER_CONTAINER_TYPES.items():
        node = classes.get(class_name)
        if node is None:
            continue

        method = method_map(node).get("__iter__")
        if method is None:
            raise AssertionError("%s is missing %s.__iter__" % (path, class_name))
        if annotation_text(method.returns) != "Iterator[%s]" % element_type:
            raise AssertionError(
                "%s has an unexpected %s.__iter__ return annotation"
                % (path, class_name)
            )

        methods = method_map(node)
        getitem = methods.get("__getitem__")
        if getitem and annotation_text(getitem.returns) == "Incomplete":
            raise AssertionError(
                "%s has an incomplete %s.__getitem__ annotation"
                % (path, class_name)
            )

        setitem = methods.get("__setitem__")
        if not setitem:
            continue
        for arg in setitem.args.args:
            if arg.arg in {"value", "val"}:
                if annotation_text(arg.annotation) == "Incomplete":
                    raise AssertionError(
                        "%s has an incomplete %s.__setitem__ value annotation"
                        % (path, class_name)
                    )
                break


def assert_method_signature(
    path,
    classes,
    class_name,
    method_name,
    argument_types,
    return_type,
):
    node = classes.get(class_name)
    if node is None:
        raise AssertionError("%s is missing %s" % (path, class_name))

    methods = methods_named(node, method_name)
    for method in methods:
        annotations = argument_annotations(method)
        if all(
            annotations.get(arg_name) == arg_type
            for arg_name, arg_type in argument_types.items()
        ) and annotation_text(method.returns) == return_type:
            return

    raise AssertionError(
        "%s is missing expected %s.%s annotations"
        % (path, class_name, method_name)
    )


def assert_array_helpers(path, tree, checks):
    classes = class_map(tree)
    for class_name, method_name, argument_types, return_type in checks:
        assert_method_signature(
            path, classes, class_name, method_name, argument_types, return_type
        )


def assert_unsupported_array_helpers(path, tree, checks):
    classes = class_map(tree)
    for class_name, method_name, argument_name, argument_type in checks:
        node = classes.get(class_name)
        if node is None:
            raise AssertionError("%s is missing %s" % (path, class_name))
        for method in methods_named(node, method_name):
            annotations = argument_annotations(method)
            if annotations.get(argument_name) == argument_type:
                raise AssertionError(
                    "%s has unsupported %s.%s %s annotation"
                    % (path, class_name, method_name, argument_type)
                )


def assert_runtime_unsupported_methods(path, tree, checks):
    classes = class_map(tree)
    for class_name, method_name, argument_types, return_type in checks:
        node = classes.get(class_name)
        if node is None:
            raise AssertionError("%s is missing %s" % (path, class_name))

        methods = methods_named(node, method_name)
        if not methods:
            raise AssertionError(
                "%s is missing %s.%s" % (path, class_name, method_name)
            )

        for method in methods:
            annotations = argument_annotations(method)
            for arg_name, arg_type in argument_types.items():
                if annotations.get(arg_name) != arg_type:
                    raise AssertionError(
                        "%s has unsupported %s.%s %s annotation"
                        % (path, class_name, method_name, arg_name)
                    )
            if annotation_text(method.returns) != return_type:
                raise AssertionError(
                    "%s has unsupported %s.%s return annotation"
                    % (path, class_name, method_name)
                )


def assert_runtime_unsupported_notes(path, text, checks):
    lines = text.splitlines()
    current_class = None
    note_seen = False
    missing = {
        (class_name, method_name)
        for class_name, method_name, _, _ in checks
    }

    for line in lines:
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if class_match:
            current_class = class_match.group(1)
            note_seen = False
            continue
        if current_class and is_top_level_statement(line):
            current_class = None
            note_seen = False
            continue

        stripped = line.strip()
        if current_class and stripped == "# %s" % RUNTIME_UNSUPPORTED_NOTE:
            note_seen = True
            continue
        if current_class and stripped.startswith("@"):
            continue

        def_match = re.match(r"\s*def\s+([A-Za-z_]\w*)\(", line)
        if def_match and current_class:
            key = (current_class, def_match.group(1))
            if note_seen and key in missing:
                missing.remove(key)
            note_seen = False
            continue

        if stripped:
            note_seen = False

    if missing:
        class_name, method_name = sorted(missing)[0]
        raise AssertionError(
            "%s is missing runtime unsupported note for %s.%s"
            % (path, class_name, method_name)
        )


def assert_deferred_raw_methods(path, tree, checks):
    classes = class_map(tree)
    for class_name, method_name, argument_types, return_type in checks:
        assert_method_signature(
            path, classes, class_name, method_name, argument_types, return_type
        )


def assert_typedef_and_string_helpers(path, tree, checks):
    classes = class_map(tree)
    for class_name, method_name, argument_types, return_type in checks:
        assert_method_signature(
            path, classes, class_name, method_name, argument_types, return_type
        )


def assert_doc_typed_methods(path, tree, checks):
    classes = class_map(tree)
    for class_name, method_name, argument_types, return_type in checks:
        assert_method_signature(
            path, classes, class_name, method_name, argument_types, return_type
        )


def assert_pointer_helper_methods(path, tree, checks):
    classes = class_map(tree)
    for class_name, method_name, argument_types, return_type in checks:
        assert_method_signature(
            path, classes, class_name, method_name, argument_types, return_type
        )


def assert_unsupported_reference_methods(path, tree, checks):
    classes = class_map(tree)
    for class_name, method_name, argument_types, return_type in checks:
        assert_method_signature(
            path, classes, class_name, method_name, argument_types, return_type
        )


def assert_operator_helpers(path, tree, checks):
    classes = class_map(tree)
    for class_name, method_name, argument_types, return_type in checks:
        assert_method_signature(
            path, classes, class_name, method_name, argument_types, return_type
        )


def assert_multifield_helpers(path, tree, checks):
    classes = class_map(tree)
    for class_name, method_name, argument_types, return_type in checks:
        assert_method_signature(
            path, classes, class_name, method_name, argument_types, return_type
        )


def assert_python_helpers(path, tree, checks):
    classes = class_map(tree)
    for class_name, method_name, argument_types, return_type in checks:
        assert_method_signature(
            path, classes, class_name, method_name, argument_types, return_type
        )


def assert_extend_helpers(path, tree, checks):
    classes = class_map(tree)
    for class_name, method_name, argument_types, return_type in checks:
        assert_method_signature(
            path, classes, class_name, method_name, argument_types, return_type
        )


def assert_property_attributes(path, tree, checks):
    classes = class_map(tree)
    for class_name, attribute_name, attribute_type in checks:
        node = classes.get(class_name)
        if node is None:
            raise AssertionError("%s is missing %s" % (path, class_name))

        for item in node.body:
            if not isinstance(item, ast.AnnAssign):
                continue
            if (
                isinstance(item.target, ast.Name)
                and item.target.id == attribute_name
            ):
                if annotation_text(item.annotation) != attribute_type:
                    raise AssertionError(
                        "%s has unexpected %s.%s annotation"
                        % (path, class_name, attribute_name)
                    )
                break
        else:
            raise AssertionError(
                "%s is missing %s.%s" % (path, class_name, attribute_name)
            )


def assert_no_bare_multifield_setvalues(path, tree):
    classes = class_map(tree)
    for class_name, node in classes.items():
        if not class_name.startswith("SoMF"):
            continue
        for method in methods_named(node, "setValues"):
            if method.args.vararg is not None:
                raise AssertionError(
                    "%s has unresolved %s.setValues varargs" % (path, class_name)
                )


def assert_soqt_coin_duplicate_classes(path, tree):
    classes = class_map(tree)
    missing_classes = sorted(SOQT_COIN_DUPLICATE_CLASSES - set(classes))
    if missing_classes:
        raise AssertionError(
            "%s is missing expected SoQt Coin duplicate classes: %s"
            % (path, ", ".join(missing_classes))
        )

    checks = (
        ("SoType", "fromName", {"name": "SbName"}, "SoType"),
        ("SbString", "getString", {}, "str"),
        ("SbName", "getString", {}, "str"),
        ("SoEvent", "getPosition", {}, "SbVec2s"),
        ("SoField", "getTypeId", {}, "SoType"),
        ("SoMField", "getNum", {}, "int"),
    )
    for class_name, method_name, argument_types, return_type in checks:
        assert_method_signature(
            path, classes, class_name, method_name, argument_types, return_type
        )


def assert_callback_helpers(path, tree, checks):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            raise AssertionError("%s has a top-level __init__ helper" % path)

    classes = class_map(tree)
    for class_name, method_name, argument_types, return_type in checks:
        assert_method_signature(
            path, classes, class_name, method_name, argument_types, return_type
        )

    for class_name in SENSOR_CALLBACK_CLASSES:
        node = classes.get(class_name)
        if node is None:
            continue

        init_methods = methods_named(node, "__init__")
        if not any(len(method.args.args) == 1 for method in init_methods):
            raise AssertionError(
                "%s is missing %s empty constructor" % (path, class_name)
            )

        callback_type = "Callable[[Any, %s], None]" % class_name
        if not any(
            argument_annotations(method).get("func") == callback_type
            and argument_annotations(method).get("data") == "Any"
            and annotation_text(method.returns) == "None"
            for method in init_methods
        ):
            raise AssertionError(
                "%s is missing %s callback constructor" % (path, class_name)
            )


def assert_private_cast_stub(path, tree):
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            if any(alias.name == "Any" for alias in node.names):
                break
    else:
        raise AssertionError("%s does not import typing.Any" % path)

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "cast":
            continue
        if not node.args.vararg or node.args.vararg.arg != "args":
            raise AssertionError("%s cast() is missing *args" % path)
        if not node.args.kwarg or node.args.kwarg.arg != "kwargs":
            raise AssertionError("%s cast() is missing **kwargs" % path)
        return

    raise AssertionError("%s is missing cast()" % path)


def validate_stub_files(package_dir):
    missing = [
        relative
        for relative in REQUIRED_STUBS + ("py.typed",)
        if not os.path.exists(os.path.join(package_dir, relative))
    ]
    if missing:
        raise AssertionError("missing generated stub files: %s" % ", ".join(missing))

    for spec in STUB_SPECS:
        path = os.path.join(package_dir, spec.relative_path)
        text, tree = parse_stub(path)
        assert_generated_header(path, text)
        match spec.kind:
            case StubKind.PUBLIC:
                relative = spec.relative_path
                assert_no_bare_method_stubs(path, text)
                assert_swig_meta_setattr(path, tree)
                assert_swig_thisown_annotations(path, tree)
                assert_pointer_helper_classes(path, tree)
                assert_iter_container_classes(path, tree)
                assert_array_helpers(path, tree, ARRAY_METHOD_CHECKS.get(relative, ()))
                assert_unsupported_array_helpers(
                    path, tree, UNSUPPORTED_ARRAY_METHOD_CHECKS.get(relative, ())
                )
                assert_runtime_unsupported_methods(
                    path, tree, RUNTIME_UNSUPPORTED_METHOD_CHECKS.get(relative, ())
                )
                assert_runtime_unsupported_notes(
                    path, text, RUNTIME_UNSUPPORTED_METHOD_CHECKS.get(relative, ())
                )
                assert_deferred_raw_methods(
                    path, tree, DEFERRED_RAW_METHOD_CHECKS.get(relative, ())
                )
                assert_property_attributes(
                    path, tree, DEFERRED_RAW_ATTRIBUTE_CHECKS.get(relative, ())
                )
                assert_typedef_and_string_helpers(
                    path, tree, TYPEDEF_AND_STRING_METHOD_CHECKS.get(relative, ())
                )
                assert_doc_typed_methods(
                    path, tree, DOC_TYPED_METHOD_CHECKS.get(relative, ())
                )
                assert_pointer_helper_methods(
                    path, tree, POINTER_HELPER_METHOD_CHECKS.get(relative, ())
                )
                assert_unsupported_reference_methods(
                    path, tree, UNSUPPORTED_REFERENCE_METHOD_CHECKS.get(relative, ())
                )
                assert_operator_helpers(
                    path, tree, OPERATOR_METHOD_CHECKS.get(relative, ())
                )
                assert_multifield_helpers(
                    path, tree, MULTIFIELD_METHOD_CHECKS.get(relative, ())
                )
                assert_python_helpers(
                    path, tree, PYTHON_HELPER_METHOD_CHECKS.get(relative, ())
                )
                assert_extend_helpers(
                    path, tree, EXTEND_HELPER_METHOD_CHECKS.get(relative, ())
                )
                assert_property_attributes(
                    path, tree, PROPERTY_ATTRIBUTE_CHECKS.get(relative, ())
                )
                assert_no_bare_multifield_setvalues(path, tree)
                if relative == os.path.join("gui", "soqt.pyi"):
                    assert_soqt_coin_duplicate_classes(path, tree)
                assert_callback_helpers(
                    path, tree, CALLBACK_METHOD_CHECKS.get(relative, ())
                )
            case StubKind.PRIVATE:
                assert_private_cast_stub(path, tree)


def assert_committed_stub_files_match(generated_package_dir, committed_package_dir):
    expected = REQUIRED_STUBS + ("py.typed",)
    missing = []
    mismatched = []

    for relative in expected:
        generated_path = os.path.join(generated_package_dir, relative)
        committed_path = os.path.join(committed_package_dir, relative)
        if not os.path.exists(committed_path):
            missing.append(relative)
            continue

        with open(generated_path, "rb") as generated_file:
            generated = generated_file.read()
        with open(committed_path, "rb") as committed_file:
            committed = committed_file.read()
        if generated != committed:
            mismatched.append(relative)

    if missing:
        raise AssertionError(
            "missing committed stub files: %s" % ", ".join(missing)
        )
    if mismatched:
        raise AssertionError(
            "committed stub files differ from generated output: %s"
            % ", ".join(mismatched)
        )


def run_mypy_import_check(python_executable, package_dir):
    command = [python_executable, "-m", "mypy", "-c", MYPY_SNIPPET]
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    package_parent = os.path.dirname(package_dir)
    env["PYTHONPATH"] = (
        package_parent if not pythonpath else package_parent + os.pathsep + pythonpath
    )
    with tempfile.TemporaryDirectory() as cwd:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        raise AssertionError("mypy could not consume installed Pivy stubs")


def main():
    parser = argparse.ArgumentParser(description="Validate generated Pivy .pyi stubs")
    parser.add_argument(
        "--package-dir",
        default=os.path.join("build", "pivy"),
        help="generated build package directory to validate",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to run the mypy import check",
    )
    parser.add_argument(
        "--committed-package-dir",
        default="pivy",
        help="source package directory containing committed .pyi stubs",
    )
    parser.add_argument(
        "--skip-committed-check",
        action="store_true",
        help="skip comparing generated stubs against committed source stubs",
    )
    args = parser.parse_args()

    package_dir = os.path.abspath(args.package_dir)
    validate_stub_files(package_dir)
    if not args.skip_committed_check:
        committed_package_dir = os.path.abspath(args.committed_package_dir)
        assert_committed_stub_files_match(package_dir, committed_package_dir)
    run_mypy_import_check(args.python, package_dir)

    print("Pivy stubs validated")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print("error: %s" % exc, file=sys.stderr)
        sys.exit(1)
