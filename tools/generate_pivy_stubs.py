#!/usr/bin/env python

import argparse
from dataclasses import dataclass
from enum import Enum
import keyword
import os
import re
import shutil
import subprocess
import sys


DEF_RE = re.compile(
    r"^(?P<indent>\s*)def\s+(?P<name>[A-Za-z_]\w*)"
    r"\((?P<args>.*)\)(?:\s*->\s*(?P<return>[^:]+))?:\s*(?P<body>\.\.\.)?$"
)
SIGNATURE_RE = re.compile(
    r"^(?P<name>[A-Za-z_][\w]*)\((?P<args>.*)\)(?:\s*->\s*(?P<return>.+))?$"
)


@dataclass(frozen=True)
class CppParameter:
    name: str
    type: str
    default: str | None


@dataclass(frozen=True)
class SwigSignature:
    name: str
    args: list[CppParameter]
    return_type: str | None


class PyObjectArgumentRole(Enum):
    CALLBACK = "callback"
    HANDLE = "handle"
    USERDATA = "userdata"
    OTHER = "other"


try:
    # Support both module imports and direct script execution from build tooling.
    from tools.pivy_stub_generation_data import (
        BOOL_SEQUENCE_ARRAY_PARAMETERS,
        BOOL_TYPES,
        CALLBACK_DATA_PARAMETER_NAMES,
        CALLBACK_HANDLE_PARAMETER_NAMES,
        CALLBACK_PARAMETER_NAMES,
        CALLBACK_TYPE_SIGNATURES,
        COMPARISON_METHODS,
        EXTEND_HELPER_METHOD_TYPES,
        FLOAT_TYPES,
        FUNCTION_POINTER_TYPE_SIGNATURES,
        GENERATED_HEADER,
        INPLACE_DIVISION_METHODS,
        INT_TYPES,
        KNOWN_ITER_ELEMENT_TYPES,
        MATRIX_CPP_TYPES,
        MATRIX_ROW_RETURN_TYPES,
        MATRIX_SEQUENCE_PARAMETERS,
        MATRIX_VALUE_RETURN_TYPES,
        MULTIFIELD_SETVALUES_TYPES,
        POINTER_HELPER_TYPES,
        PRIVATE_EXTENSION_STUB,
        PYTHON_HELPER_METHOD_TYPES,
        RUNTIME_UNSUPPORTED_METHOD_NOTES,
        RUNTIME_UNSUPPORTED_NOTE,
        SCALAR_POINTER_HELPER_PARAMETERS,
        SCALAR_REFERENCE_HELPER_TYPES,
        SENSOR_CALLBACK_CLASSES,
        SEQUENCE_ARRAY_PARAMETERS,
        SEQUENCE_POINTER_PARAMETERS,
        SEQUENCE_VALUE_RETURN_TYPES,
        STRING_POINTER_PARAMETERS,
    )
except ImportError:
    from pivy_stub_generation_data import (
        BOOL_SEQUENCE_ARRAY_PARAMETERS,
        BOOL_TYPES,
        CALLBACK_DATA_PARAMETER_NAMES,
        CALLBACK_HANDLE_PARAMETER_NAMES,
        CALLBACK_PARAMETER_NAMES,
        CALLBACK_TYPE_SIGNATURES,
        COMPARISON_METHODS,
        EXTEND_HELPER_METHOD_TYPES,
        FLOAT_TYPES,
        FUNCTION_POINTER_TYPE_SIGNATURES,
        GENERATED_HEADER,
        INPLACE_DIVISION_METHODS,
        INT_TYPES,
        KNOWN_ITER_ELEMENT_TYPES,
        MATRIX_CPP_TYPES,
        MATRIX_ROW_RETURN_TYPES,
        MATRIX_SEQUENCE_PARAMETERS,
        MATRIX_VALUE_RETURN_TYPES,
        MULTIFIELD_SETVALUES_TYPES,
        POINTER_HELPER_TYPES,
        PRIVATE_EXTENSION_STUB,
        PYTHON_HELPER_METHOD_TYPES,
        RUNTIME_UNSUPPORTED_METHOD_NOTES,
        RUNTIME_UNSUPPORTED_NOTE,
        SCALAR_POINTER_HELPER_PARAMETERS,
        SCALAR_REFERENCE_HELPER_TYPES,
        SENSOR_CALLBACK_CLASSES,
        SEQUENCE_ARRAY_PARAMETERS,
        SEQUENCE_POINTER_PARAMETERS,
        SEQUENCE_VALUE_RETURN_TYPES,
        STRING_POINTER_PARAMETERS,
    )


def stub_path(output_dir, module):
    return os.path.join(output_dir, *module.split(".")) + ".pyi"


def private_stub_path(output_dir, module):
    components = module.split(".")
    components[-1] = "_" + components[-1]
    return os.path.join(output_dir, *components) + ".pyi"


def normalize_cpp_type(cpp_type):
    cleaned = cpp_type.strip()
    cleaned = cleaned.replace(":: ", "::")
    cleaned = re.sub(r"\b(class|struct|enum)\s+", "", cleaned)
    cleaned = re.sub(r"\b(const|volatile)\b", "", cleaned)
    cleaned = cleaned.replace("*", " * ").replace("&", " & ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def base_cpp_type(cpp_type):
    normalized = normalize_cpp_type(cpp_type)
    return normalized.replace("*", "").replace("&", "").strip()


EXTERNAL_STUB_MODULES = ("pivy.coin",)
REPLACE_EXTERNAL_CLASS_MODULES = {
    "pivy.gui.soqt": EXTERNAL_STUB_MODULES,
}


def scalar_cpp_type_to_python(cpp_type):
    if cpp_type in BOOL_TYPES:
        return "bool"
    if cpp_type in FLOAT_TYPES:
        return "float"
    if cpp_type in INT_TYPES:
        return "int"
    return None


def cpp_array_type_to_python(cpp_type):
    normalized = normalize_cpp_type(cpp_type)
    dimensions = re.findall(r"\[\s*(\d*)\s*\]", normalized)
    if not dimensions:
        return None

    base = re.sub(r"\s*\[\s*\d*\s*\]", "", normalized).strip()
    element_type = None
    if base in FLOAT_TYPES:
        if dimensions[0] == "":
            if len(dimensions) == 1 or not all(dimensions[1:]):
                return None
        elif not all(dimensions):
            return None
        element_type = "float"
    if element_type is None:
        return None

    sequence_type = element_type
    for _ in dimensions:
        sequence_type = "Sequence[%s]" % sequence_type
    return sequence_type


def cpp_type_to_python(
    cpp_type,
    class_names,
    is_return=False,
    external_class_modules=None,
    used_external_types=None,
):
    raw = cpp_type.strip()
    if not raw:
        return "Incomplete"

    if "(*" in raw or "(*)" in raw:
        return "Incomplete"

    array_type = cpp_array_type_to_python(raw)
    if array_type:
        return array_type

    normalized = normalize_cpp_type(raw)
    base = base_cpp_type(raw)
    if not base:
        return "Incomplete"

    if "[" in normalized and "]" in normalized:
        return "Incomplete"

    is_pointer = "*" in normalized
    is_reference = "&" in normalized
    if (
        is_reference
        and not is_pointer
        and "const" not in raw
        and (base in BOOL_TYPES or base in FLOAT_TYPES or base in INT_TYPES or "::" in base)
    ):
        return "Incomplete"

    if base == "void":
        return "None" if is_return and not is_pointer else "Incomplete"

    if base in {"char", "wchar_t"}:
        if not is_pointer or "const" in raw or base == "wchar_t":
            return "str"
        return "Incomplete"

    if is_pointer and (
        base in BOOL_TYPES or base in FLOAT_TYPES or base in INT_TYPES
    ):
        return "Incomplete"

    if base in BOOL_TYPES:
        return "bool"
    if base in FLOAT_TYPES:
        return "float"
    if base in INT_TYPES:
        return "int"
    if base in {"FILE", "PyObject", "timeval"}:
        return "Incomplete"

    if base in class_names:
        return base

    if external_class_modules and base in external_class_modules:
        if used_external_types is not None:
            used_external_types.add(base)
        return base

    if "::" in base:
        nested_name = base.rsplit("::", 1)[-1]
        if is_pointer and re.search(
            r"(CB|Callback|Func|Handler|Method)", nested_name, re.I
        ):
            return "Incomplete"
        return "int"

    if re.search(r"(CB|Callback|Func|Handler|Method)$", base, re.I):
        return "Incomplete"

    return "Incomplete"


def callback_cpp_type_to_python(cpp_type):
    compact = re.sub(r"\s+", "", normalize_cpp_type(cpp_type))
    if compact in FUNCTION_POINTER_TYPE_SIGNATURES:
        return FUNCTION_POINTER_TYPE_SIGNATURES[compact]

    return CALLBACK_TYPE_SIGNATURES.get(base_cpp_type(cpp_type))


def sequence_parameter_type(class_name, method_name, cpp_arg):
    sequence_type = SEQUENCE_POINTER_PARAMETERS.get(
        (class_name, method_name, cpp_arg.name)
    )
    if sequence_type:
        return sequence_type

    bool_sequence_array_type = BOOL_SEQUENCE_ARRAY_PARAMETERS.get(
        (class_name, method_name, cpp_arg.name)
    )
    if bool_sequence_array_type:
        sequence_type, expected_dimension = bool_sequence_array_type
        normalized = normalize_cpp_type(cpp_arg.type)
        base = re.sub(r"\s*\[\s*\d*\s*\]", "", normalized).strip()
        dimensions = re.findall(r"\[\s*(\d*)\s*\]", normalized)
        if base in BOOL_TYPES and dimensions == [expected_dimension]:
            return sequence_type

    sequence_array_type = SEQUENCE_ARRAY_PARAMETERS.get(
        (class_name, method_name, cpp_arg.name)
    )
    if sequence_array_type:
        sequence_type, expected_dimension = sequence_array_type
        normalized = normalize_cpp_type(cpp_arg.type)
        base = re.sub(r"\s*\[\s*\d*\s*\]", "", normalized).strip()
        dimensions = re.findall(r"\[\s*(\d*)\s*\]", normalized)
        if base in {"short", "short int"} and dimensions == [expected_dimension]:
            return sequence_type

    sequence_type = MATRIX_SEQUENCE_PARAMETERS.get(
        (class_name, method_name, cpp_arg.name)
    )
    if (
        sequence_type
        and base_cpp_type(cpp_arg.type) in MATRIX_CPP_TYPES
        and "*" not in normalize_cpp_type(cpp_arg.type)
    ):
        return sequence_type

    return None


def string_pointer_parameter_type(class_name, method_name, cpp_arg):
    if (class_name, method_name, cpp_arg.name) not in STRING_POINTER_PARAMETERS:
        return None

    normalized = normalize_cpp_type(cpp_arg.type)
    if base_cpp_type(cpp_arg.type) == "char" and "*" in normalized:
        return "str"

    return None


def scalar_pointer_helper_parameter_type(class_name, method_name, cpp_arg):
    helper_type = SCALAR_POINTER_HELPER_PARAMETERS.get(
        (class_name, method_name, cpp_arg.name)
    )
    if helper_type:
        normalized = normalize_cpp_type(cpp_arg.type)
        if (
            "*" in normalized
            and "&" not in normalized
            and normalized.count("*") == 1
            and "[" not in normalized
            and "const" not in cpp_arg.type
        ):
            return helper_type

    normalized = normalize_cpp_type(cpp_arg.type)
    if "&" not in normalized or "*" in normalized or "[" in normalized:
        return None
    if "const" in cpp_arg.type:
        return None

    return SCALAR_REFERENCE_HELPER_TYPES.get(base_cpp_type(cpp_arg.type))


def pyobject_argument_role(name):
    match name:
        case _ if name in CALLBACK_PARAMETER_NAMES:
            return PyObjectArgumentRole.CALLBACK
        case _ if name in CALLBACK_HANDLE_PARAMETER_NAMES:
            return PyObjectArgumentRole.HANDLE
        case _ if name in CALLBACK_DATA_PARAMETER_NAMES:
            return PyObjectArgumentRole.USERDATA
        case _:
            return PyObjectArgumentRole.OTHER


def infer_python_callback_types(signatures):
    callback_types = {}
    handle_types = {}
    pyobject_positions = set()
    pyobject_handle_positions = set()

    for signature in signatures:
        cpp_args = drop_self_argument(signature.args)
        for position, cpp_arg in enumerate(cpp_args, start=1):
            callback_type = callback_cpp_type_to_python(cpp_arg.type)
            if callback_type:
                callback_types.setdefault(position, callback_type)
                continue

            if base_cpp_type(cpp_arg.type) != "PyObject":
                continue

            match pyobject_argument_role(cpp_arg.name):
                case PyObjectArgumentRole.CALLBACK:
                    pyobject_positions.add(position)
                case PyObjectArgumentRole.HANDLE:
                    pyobject_handle_positions.add(position)
                case _:
                    pass

    callback_types = {
        position: callback_type
        for position, callback_type in callback_types.items()
        if position in pyobject_positions or position in pyobject_handle_positions
    }
    handle_types = {
        position: "tuple[%s, Any]" % callback_types[position]
        for position in pyobject_handle_positions
        if position in callback_types
    }
    return callback_types, handle_types


def is_c_callback_signature(signature, callback_types):
    cpp_args = drop_self_argument(signature.args)
    for position, cpp_arg in enumerate(cpp_args, start=1):
        if position in callback_types and callback_cpp_type_to_python(cpp_arg.type):
            return True
    return False


def register_annotation_types(
    annotation,
    class_names,
    external_class_modules,
    used_external_types,
):
    if not external_class_modules or used_external_types is None:
        return

    for name in re.findall(r"\b[A-Z][A-Za-z_]\w*\b", annotation):
        if name in class_names:
            continue
        if name in external_class_modules:
            used_external_types.add(name)


def drop_self_argument(cpp_args):
    if cpp_args and cpp_args[0].name in {"self", "cls"}:
        return cpp_args[1:]
    return cpp_args


def split_top_level(text, separator=","):
    pieces = []
    start = 0
    depth = 0
    pairs = {"(": ")", "[": "]", "<": ">"}
    closers = {")", "]", ">"}

    for index, char in enumerate(text):
        if char in pairs:
            depth += 1
        elif char in closers and depth:
            depth -= 1
        elif char == separator and depth == 0:
            pieces.append(text[start:index].strip())
            start = index + 1

    tail = text[start:].strip()
    if tail:
        pieces.append(tail)
    return pieces


def split_default(text):
    depth = 0
    pairs = {"(": ")", "[": "]", "<": ">"}
    closers = {")", "]", ">"}

    for index, char in enumerate(text):
        if char in pairs:
            depth += 1
        elif char in closers and depth:
            depth -= 1
        elif char == "=" and depth == 0:
            return text[:index].strip(), text[index + 1 :].strip()
    return text.strip(), None


def sanitize_parameter_name(name, used_names, fallback):
    if not re.match(r"^[A-Za-z_]\w*$", name):
        name = fallback
    if keyword.iskeyword(name):
        name += "_"

    base = name
    suffix = 2
    while name in used_names:
        name = "%s_%d" % (base, suffix)
        suffix += 1

    used_names.add(name)
    return name


def parse_cpp_parameter(parameter, position):
    parameter, default = split_default(parameter)
    match = re.search(r"([A-Za-z_]\w*)$", parameter)
    if not match or not parameter[: match.start()].strip():
        return CppParameter("arg%d" % position, parameter, default)

    return CppParameter(
        match.group(1),
        parameter[: match.start()].strip(),
        default,
    )


def parse_swig_signature(signature, expected_name):
    match = SIGNATURE_RE.match(signature.strip())
    if not match or match.group("name") != expected_name:
        return None

    args = [
        parse_cpp_parameter(parameter, index)
        for index, parameter in enumerate(split_top_level(match.group("args")), start=1)
    ]
    return SwigSignature(match.group("name"), args, match.group("return"))


def read_signature_docstring(lines, start, expected_name):
    if start >= len(lines):
        return None

    stripped = lines[start].strip()
    quote = None
    if stripped.startswith('"""'):
        quote = '"""'
    elif stripped.startswith("'''"):
        quote = "'''"
    else:
        return None

    if stripped != quote and stripped.endswith(quote):
        content = stripped[3:-3].strip()
        signatures = [content] if content else []
        end = start + 1
    elif stripped == quote:
        signatures = []
        end = start + 1
        while end < len(lines) and lines[end].strip() != quote:
            content = lines[end].strip()
            if content:
                signatures.append(content)
            end += 1
        if end >= len(lines):
            return None
        end += 1
    else:
        return None

    parsed = [
        parse_swig_signature(signature, expected_name) for signature in signatures
    ]
    if not parsed or any(signature is None for signature in parsed):
        return None

    return parsed, end


def render_python_signature(
    def_match,
    signature,
    class_names,
    class_name=None,
    external_class_modules=None,
    used_external_types=None,
    callback_types=None,
    callback_handle_types=None,
):
    indent = def_match.group("indent")
    name = def_match.group("name")
    header_args = split_top_level(def_match.group("args"))
    used_names = set()
    python_args = []
    cpp_args = signature.args
    callback_types = callback_types or {}
    callback_handle_types = callback_handle_types or {}
    is_callback_context = bool(callback_types or callback_handle_types)

    if header_args and header_args[0] in {"self", "cls"}:
        python_args.append(header_args[0])
        used_names.add(header_args[0])
        if cpp_args and cpp_args[0].name in {"self", "cls"}:
            cpp_args = cpp_args[1:]

    for position, cpp_arg in enumerate(cpp_args, start=1):
        parameter_name = sanitize_parameter_name(
            cpp_arg.name, used_names, "arg%d" % position
        )
        parameter_type = None
        cpp_base = base_cpp_type(cpp_arg.type)
        if cpp_base == "PyObject":
            match pyobject_argument_role(cpp_arg.name):
                case PyObjectArgumentRole.CALLBACK:
                    parameter_type = callback_types.get(position)
                case PyObjectArgumentRole.HANDLE:
                    parameter_type = callback_handle_types.get(position)
                case _:
                    pass
        if parameter_type is None:
            parameter_type = sequence_parameter_type(class_name, name, cpp_arg)
        if parameter_type is None:
            parameter_type = string_pointer_parameter_type(class_name, name, cpp_arg)
        if parameter_type is None:
            parameter_type = scalar_pointer_helper_parameter_type(
                class_name, name, cpp_arg
            )
        if (
            parameter_type is None
            and is_callback_context
            and pyobject_argument_role(cpp_arg.name) == PyObjectArgumentRole.USERDATA
            and cpp_base in {"PyObject", "void"}
        ):
            parameter_type = "Any"
        if parameter_type is None:
            parameter_type = cpp_type_to_python(
                cpp_arg.type,
                class_names,
                external_class_modules=external_class_modules,
                used_external_types=used_external_types,
            )
        register_annotation_types(
            parameter_type, class_names, external_class_modules, used_external_types
        )
        if cpp_arg.default == "None":
            parameter_type += " | None"

        rendered = "%s: %s" % (parameter_name, parameter_type)
        if cpp_arg.default is not None:
            rendered += " = ..."
        python_args.append(rendered)

    if name == "__init__":
        return_type = "None"
    elif name in COMPARISON_METHODS:
        return_type = "bool"
    else:
        cpp_return = signature.return_type
        if (
            name in {"getValue", "getHSVValue"}
            and class_name in SEQUENCE_VALUE_RETURN_TYPES
            and not cpp_args
        ):
            return_type = SEQUENCE_VALUE_RETURN_TYPES[class_name]
        elif (
            name == "getValue"
            and class_name in MATRIX_VALUE_RETURN_TYPES
            and not cpp_args
        ):
            return_type = MATRIX_VALUE_RETURN_TYPES[class_name]
        elif name == "__getitem__" and class_name in MATRIX_ROW_RETURN_TYPES:
            return_type = MATRIX_ROW_RETURN_TYPES[class_name]
        elif cpp_return and name == "addEventCallback" and callback_types:
            return_type = "tuple[%s, Any]" % next(iter(callback_types.values()))
        elif cpp_return:
            return_type = cpp_type_to_python(
                cpp_return,
                class_names,
                is_return=True,
                external_class_modules=external_class_modules,
                used_external_types=used_external_types,
            )
        else:
            return_type = "None"
        register_annotation_types(
            return_type, class_names, external_class_modules, used_external_types
        )

    return "%sdef %s(%s) -> %s: ..." % (
        indent,
        name,
        ", ".join(python_args),
        return_type,
    )


def pop_decorators(lines, indent):
    decorators = []
    while lines and lines[-1].startswith(indent + "@"):
        decorators.insert(0, lines.pop())
    return decorators


def render_unique_python_signatures(
    def_match,
    signatures,
    class_names,
    class_name,
    external_class_modules,
    used_external_types,
):
    rendered_signatures = []
    seen = set()
    callback_types, callback_handle_types = infer_python_callback_types(signatures)

    for signature in signatures:
        if is_c_callback_signature(signature, callback_types):
            continue

        line = render_python_signature(
            def_match,
            signature,
            class_names,
            class_name=class_name,
            external_class_modules=external_class_modules,
            used_external_types=used_external_types,
            callback_types=callback_types,
            callback_handle_types=callback_handle_types,
        )
        if line in seen:
            continue
        seen.add(line)
        rendered_signatures.append(line)

    return rendered_signatures


def render_overload_block(def_match, rendered_signatures, decorators):
    indent = def_match.group("indent")
    rendered = []

    for line in rendered_signatures:
        rendered.extend(decorators)
        rendered.append("%s@overload" % indent)
        rendered.append(line)

    return rendered


def collect_class_names(text):
    return set(re.findall(r"^class\s+([A-Za-z_]\w*)", text, flags=re.MULTILINE))


def collect_module_class_names(output_dir, module):
    path = stub_path(output_dir, module)
    if not os.path.exists(path):
        return set()

    with open(path) as stub_file:
        return collect_class_names(stub_file.read())


def collect_external_class_modules(output_dir, module, local_class_names):
    external_class_modules = {}
    for external_module in EXTERNAL_STUB_MODULES:
        if external_module == module:
            continue

        external_class_names = collect_module_class_names(output_dir, external_module)
        for class_name in external_class_names - local_class_names:
            external_class_modules[class_name] = external_module

    return external_class_modules


def external_duplicate_class_modules(output_dir, module, local_class_names):
    duplicate_class_modules = {}
    for external_module in REPLACE_EXTERNAL_CLASS_MODULES.get(module, ()):
        if external_module == module:
            continue

        external_class_names = collect_module_class_names(output_dir, external_module)
        for class_name in external_class_names & local_class_names:
            if class_name[:1].isupper():
                duplicate_class_modules[class_name] = external_module

    return duplicate_class_modules


def collect_class_blocks(text):
    lines = text.splitlines()
    blocks = {}
    index = 0

    while index < len(lines):
        line = lines[index]
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if not class_match:
            index += 1
            continue

        start = index
        index += 1
        while index < len(lines) and not is_top_level_statement(lines[index]):
            index += 1

        blocks[class_match.group(1)] = "\n".join(lines[start:index]).rstrip()

    return blocks


def collect_module_class_blocks(output_dir, module):
    path = stub_path(output_dir, module)
    if not os.path.exists(path):
        return {}

    with open(path) as stub_file:
        return collect_class_blocks(stub_file.read())


def external_duplicate_class_blocks(output_dir, module, local_class_names):
    duplicate_class_modules = external_duplicate_class_modules(
        output_dir, module, local_class_names
    )
    duplicate_class_blocks = {}
    for external_module in sorted(set(duplicate_class_modules.values())):
        module_blocks = collect_module_class_blocks(output_dir, external_module)
        for class_name, duplicate_module in duplicate_class_modules.items():
            if duplicate_module == external_module and class_name in module_blocks:
                duplicate_class_blocks[class_name] = module_blocks[class_name]

    return duplicate_class_blocks


def replace_class_blocks(text, replacement_blocks):
    if not replacement_blocks:
        return text, set()

    lines = text.splitlines()
    updated = []
    replaced = set()
    index = 0

    while index < len(lines):
        line = lines[index]
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        class_name = class_match.group(1) if class_match else None
        if class_name not in replacement_blocks:
            updated.append(line)
            index += 1
            continue

        updated.extend(replacement_blocks[class_name].splitlines())
        replaced.add(class_name)

        index += 1
        while index < len(lines) and not is_top_level_statement(lines[index]):
            index += 1

        if index < len(lines) and updated and updated[-1] != "":
            updated.append("")

    return "\n".join(updated) + "\n", replaced


def replace_external_duplicate_classes(text, module, output_dir, local_class_names):
    return replace_class_blocks(
        text, external_duplicate_class_blocks(output_dir, module, local_class_names)
    )


def collect_referenced_external_types(text, class_names, external_class_modules):
    used_external_types = set()
    for name in re.findall(r"\b[A-Z][A-Za-z_]\w*\b", text):
        if name in class_names:
            continue
        if name in external_class_modules:
            used_external_types.add(name)
    return used_external_types


def wrapper_path(output_dir, module):
    return os.path.join(output_dir, *module.split(".")) + ".py"


def property_doc_type_to_python(
    doc,
    class_names,
    external_class_modules,
    used_external_types,
):
    if ":" not in doc:
        return None

    doc_type = doc.split(":", 1)[1].strip()
    if doc_type.startswith("p.f("):
        return None

    array_match = re.match(r"a\(\d+\)\.([A-Za-z_]\w*)$", doc_type)
    if array_match:
        doc_type = array_match.group(1)

    if doc_type.startswith("p."):
        base = doc_type[2:]
        if base in class_names:
            return "%s | None" % base
        if base in external_class_modules:
            used_external_types.add(base)
            return "%s | None" % base
        return None

    if doc_type in BOOL_TYPES:
        return "bool"
    if doc_type in FLOAT_TYPES:
        return "float"
    if doc_type in INT_TYPES:
        return "int"
    if doc_type.startswith("enum ") or "::" in doc_type:
        return "int"
    if doc_type in class_names:
        return doc_type
    if doc_type in external_class_modules:
        used_external_types.add(doc_type)
        return doc_type

    return None


def collect_property_doc_types(
    output_dir,
    module,
    class_names,
    external_class_modules,
    used_external_types,
):
    path = wrapper_path(output_dir, module)
    if not os.path.exists(path):
        return {}

    property_types = {}
    current_class = None
    with open(path) as wrapper_file:
        for raw_line in wrapper_file:
            line = raw_line.rstrip("\n")
            class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
            if class_match:
                current_class = class_match.group(1)
                continue
            if current_class and is_top_level_statement(line):
                current_class = None
                continue

            if not current_class:
                continue

            property_match = re.match(
                r"\s*(?P<name>[A-Za-z_]\w*)\s*=\s*property\(.*"
                r"doc=r?\"\"\"(?P<doc>.*?)\"\"\"\)",
                line,
            )
            if not property_match:
                continue

            annotation = property_doc_type_to_python(
                property_match.group("doc"),
                class_names,
                external_class_modules,
                used_external_types,
            )
            if annotation:
                property_types[(current_class, property_match.group("name"))] = (
                    annotation
                )

    return property_types


def normalize_property_attributes(text, property_types):
    if not property_types:
        return text

    lines = text.splitlines()
    updated = []
    current_class = None

    for line in lines:
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if class_match:
            current_class = class_match.group(1)
        elif current_class and is_top_level_statement(line):
            current_class = None

        attr_match = re.match(
            r"(?P<indent>\s*)(?P<name>[A-Za-z_]\w*):\s*Incomplete\s*$",
            line,
        )
        if current_class and attr_match:
            annotation = property_types.get((current_class, attr_match.group("name")))
            if annotation:
                updated.append(
                    "%s%s: %s"
                    % (
                        attr_match.group("indent"),
                        attr_match.group("name"),
                        annotation,
                    )
                )
                continue

        updated.append(line)

    return "\n".join(updated) + "\n"


def add_type_imports(text, used_external_types, external_class_modules):
    if not used_external_types:
        return text

    lines = text.splitlines()
    for module in sorted(set(external_class_modules.values())):
        names = sorted(
            name
            for name in used_external_types
            if external_class_modules.get(name) == module
        )
        if not names:
            continue

        import_line = "from %s import %s" % (module, ", ".join(names))
        if import_line in lines:
            continue

        for index, line in enumerate(lines):
            prefix = "from %s import " % module
            if line.startswith(prefix):
                existing = [
                    item.strip()
                    for item in line[len(prefix) :].split(",")
                    if item.strip()
                ]
                lines[index] = prefix + ", ".join(sorted(set(existing + names)))
                break
        else:
            insert_at = 0
            while insert_at < len(lines) and (
                lines[insert_at].startswith("from ")
                or lines[insert_at].startswith("import ")
            ):
                insert_at += 1
            lines.insert(insert_at, import_line)

    return "\n".join(lines) + "\n"


def add_typing_import(text, name):
    if not re.search(r"\b%s\b" % re.escape(name), text) or re.search(
        r"^from typing import .*?\b%s\b" % re.escape(name),
        text,
        flags=re.MULTILINE,
    ):
        return text

    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("from typing import "):
            imports = [
                item.strip()
                for item in line[len("from typing import ") :].split(",")
                if item.strip()
            ]
            imports.append(name)
            lines[index] = "from typing import " + ", ".join(sorted(imports))
            return "\n".join(lines) + "\n"

    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("from ") or lines[insert_at].startswith("import ")
    ):
        insert_at += 1

    lines.insert(insert_at, "from typing import %s" % name)
    return "\n".join(lines) + "\n"


def add_overload_import(text):
    return add_typing_import(text, "overload")


def add_missing_imports(text):
    if (
        "builtin_function_or_method" not in text
        or "BuiltinFunctionType as builtin_function_or_method" in text
    ):
        return text

    lines = text.splitlines()
    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("from ") or lines[insert_at].startswith("import ")
    ):
        insert_at += 1

    lines.insert(
        insert_at, "from types import BuiltinFunctionType as builtin_function_or_method"
    )
    return "\n".join(lines) + "\n"


def add_generated_header(text):
    if text.startswith(GENERATED_HEADER):
        return text

    lines = text.splitlines()
    while lines and lines[0].startswith("# Generated by "):
        lines.pop(0)

    return GENERATED_HEADER + "\n".join(lines) + "\n"


def remove_swig_meta_classmethod(text):
    lines = text.splitlines()
    updated = []
    in_swig_meta = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if line.startswith("class "):
            in_swig_meta = line.startswith("class _SwigNonDynamicMeta(")

        if (
            in_swig_meta
            and stripped == "@classmethod"
            and index + 1 < len(lines)
            and re.match(r"\s*def __setattr__\(cls, name", lines[index + 1])
        ):
            continue

        updated.append(line)

    return "\n".join(updated) + "\n"


def normalize_swig_helpers(text):
    lines = text.splitlines()
    updated = []
    current_pointer_helper = None

    for line in lines:
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if class_match:
            class_name = class_match.group(1)
            current_pointer_helper = (
                class_name if class_name in POINTER_HELPER_TYPES else None
            )

        if re.match(r"\s*thisown:\s*Incomplete\s*$", line):
            updated.append(line.replace("Incomplete", "bool"))
            continue

        if current_pointer_helper:
            indent = line[: len(line) - len(line.lstrip())]
            value_type = POINTER_HELPER_TYPES[current_pointer_helper]
            if re.match(
                r"\s*def assign\(self, value[^)]*\)(?:\s*->\s*[^:]+)?: \.\.\.$",
                line,
            ):
                updated.append(
                    "%sdef assign(self, value: %s) -> None: ..."
                    % (indent, value_type)
                )
                continue
            if re.match(r"\s*def value\(self\)(?:\s*->\s*[^:]+)?: \.\.\.$", line):
                updated.append("%sdef value(self) -> %s: ..." % (indent, value_type))
                continue
            if re.match(r"\s*def cast\(self\)(?:\s*->\s*[^:]+)?: \.\.\.$", line):
                updated.append("%sdef cast(self) -> Any: ..." % indent)
                continue
            if re.match(
                r"\s*def frompointer\(t[^)]*\)(?:\s*->\s*[^:]+)?: \.\.\.$",
                line,
            ):
                updated.append(
                    "%sdef frompointer(t: Any) -> %s: ..."
                    % (indent, current_pointer_helper)
                )
                continue

        updated.append(line)

    return "\n".join(updated) + "\n"


def is_top_level_statement(line):
    return bool(line) and not line.startswith((" ", "\t", "#"))


def collect_container_element_types(lines):
    element_types = {}
    current_class = None

    for line in lines:
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if class_match:
            current_class = class_match.group(1)
            if current_class in KNOWN_ITER_ELEMENT_TYPES:
                element_types[current_class] = KNOWN_ITER_ELEMENT_TYPES[current_class]
            continue

        if not current_class:
            continue

        if is_top_level_statement(line):
            current_class = None
            continue

        getitem_match = re.match(
            r"\s*def __getitem__\(self, [^)]+\) -> (?P<type>[^:]+): \.\.\.$",
            line,
        )
        if getitem_match:
            element_type = getitem_match.group("type")
            if element_type == "Incomplete" and current_class == "SbPList":
                element_type = "Any"
            if element_type not in {"None", "Incomplete"}:
                element_types[current_class] = element_type

    return element_types


def collect_iter_classes(lines):
    iter_classes = set()
    current_class = None

    for line in lines:
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if class_match:
            current_class = class_match.group(1)
            continue

        if current_class and is_top_level_statement(line):
            current_class = None
            continue

        if current_class and re.match(r"\s*def __iter__\(self\)", line):
            iter_classes.add(current_class)

    return iter_classes


def should_add_iter_method(class_name, element_types, iter_classes):
    return (
        class_name is not None
        and class_name not in iter_classes
        and class_name.endswith("List")
        and class_name in element_types
    )


def render_iter_method(class_name, element_types):
    return "    def __iter__(self) -> Iterator[%s]: ..." % element_types[class_name]


def append_iter_method(lines, class_name, element_types):
    if lines and lines[-1] == "":
        lines.pop()
    lines.append(render_iter_method(class_name, element_types))
    lines.append("")


def rewrite_container_method(line, element_type):
    item_methods = ("append", "find", "insert", "removeItem", "set", "__setitem__")
    for method_name in item_methods:
        pattern = (
            r"(?P<prefix>\s*def %s\([^)]*?,\s*"
            r"(?P<name>[A-Za-z_]\w*): )Incomplete(?P<suffix>[^)]*\).*)$"
        ) % re.escape(method_name)
        match = re.match(pattern, line)
        if match:
            return match.group("prefix") + element_type + match.group("suffix")

    for method_name in ("get", "__getitem__"):
        pattern = r"(?P<prefix>\s*def %s\([^)]*\) -> )Incomplete(?P<suffix>: \.\.\.)$"
        match = re.match(pattern % re.escape(method_name), line)
        if match:
            return match.group("prefix") + element_type + match.group("suffix")

    iter_match = re.match(
        r"(?P<indent>\s*)def __iter__\(self\)(?: -> [^:]+)?: \.\.\.$", line
    )
    if iter_match:
        return "%sdef __iter__(self) -> Iterator[%s]: ..." % (
            iter_match.group("indent"),
            element_type,
        )

    return line


def normalize_container_helpers(text):
    lines = text.splitlines()
    element_types = collect_container_element_types(lines)
    iter_classes = collect_iter_classes(lines)
    updated = []
    current_class = None

    for line in lines:
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if class_match:
            if should_add_iter_method(current_class, element_types, iter_classes):
                append_iter_method(updated, current_class, element_types)
            current_class = class_match.group(1)
        elif current_class and is_top_level_statement(line):
            if should_add_iter_method(current_class, element_types, iter_classes):
                append_iter_method(updated, current_class, element_types)
            current_class = None

        if current_class in element_types:
            line = rewrite_container_method(line, element_types[current_class])

        updated.append(line)

    if should_add_iter_method(current_class, element_types, iter_classes):
        append_iter_method(updated, current_class, element_types)

    return "\n".join(updated) + "\n"


def render_sensor_init_methods(class_name):
    callback_type = "Callable[[Any, %s], None]" % class_name
    return [
        "    @overload",
        "    def __init__(self) -> None: ...",
        "    @overload",
        "    def __init__(self, func: %s, data: Any) -> None: ..." % callback_type,
    ]


def normalize_callback_helpers(text):
    lines = text.splitlines()
    updated = []
    current_class = None

    for line in lines:
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if class_match:
            current_class = class_match.group(1)
        elif current_class and is_top_level_statement(line):
            current_class = None

        if current_class is None and re.match(r"^def __init__\(self, \*args\)", line):
            continue

        if (
            current_class in SENSOR_CALLBACK_CLASSES
            and re.match(r"\s*def __init__\(self, \*args\) -> None: \.\.\.$", line)
        ):
            updated.extend(render_sensor_init_methods(current_class))
            continue

        updated.append(line)

    return "\n".join(updated) + "\n"


def is_scalar_division_class(class_name):
    return class_name is not None and (
        class_name.startswith("SbVec") or class_name == "SbColor4f"
    )


def render_operator_helper(line, class_name):
    match = re.match(
        r"(?P<indent>\s*)def (?P<name>__[A-Za-z]+__)\(self, \*args\): \.\.\.$",
        line,
    )
    if match:
        indent = match.group("indent")
        method_name = match.group("name")
        if (
            is_scalar_division_class(class_name)
            and method_name in INPLACE_DIVISION_METHODS
        ):
            return [
                "%sdef %s(self, d: float) -> %s: ..."
                % (indent, method_name, class_name)
            ]

        if class_name == "SbTime":
            if method_name in INPLACE_DIVISION_METHODS:
                return [
                    "%sdef %s(self, d: float) -> SbTime: ..."
                    % (indent, method_name)
                ]
            if method_name == "__truediv__":
                return [
                    "%s@overload" % indent,
                    "%sdef __truediv__(self, tm: SbTime) -> float: ..." % indent,
                    "%s@overload" % indent,
                    "%sdef __truediv__(self, d: float) -> float: ..." % indent,
                ]

    match = re.match(r"(?P<indent>\s*)def __imul__\(self, other\): \.\.\.$", line)
    if match and class_name == "SbRotation":
        return [
            "%sdef __imul__(self, other: SbRotation) -> SbRotation: ..."
            % match.group("indent")
        ]

    return None


def normalize_operator_helpers(text):
    lines = text.splitlines()
    updated = []
    current_class = None

    for line in lines:
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if class_match:
            current_class = class_match.group(1)
        elif current_class and is_top_level_statement(line):
            current_class = None

        rendered = render_operator_helper(line, current_class)
        if rendered is not None:
            updated.extend(rendered)
            continue

        updated.append(line)

    return "\n".join(updated) + "\n"


def render_multifield_setvalues(indent, value_types):
    lines = []
    for value_type in value_types:
        if len(value_types) > 1:
            lines.append("%s@overload" % indent)
        lines.append(
            (
                "%sdef setValues("
                "self, start: int, num: int, values: Sequence[%s]"
                ") -> None: ..."
            )
            % (indent, value_type)
        )
    return lines


def normalize_multifield_helpers(text):
    lines = text.splitlines()
    updated = []
    current_class = None

    for line in lines:
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if class_match:
            current_class = class_match.group(1)
        elif current_class and is_top_level_statement(line):
            current_class = None

        match = re.match(r"(?P<indent>\s*)def setValues\(self, \*args\): \.\.\.$", line)
        if match and current_class in MULTIFIELD_SETVALUES_TYPES:
            updated.extend(
                render_multifield_setvalues(
                    match.group("indent"), MULTIFIELD_SETVALUES_TYPES[current_class]
                )
            )
            continue

        updated.append(line)

    return "\n".join(updated) + "\n"


def normalize_python_helpers(text):
    lines = text.splitlines()
    updated = []
    current_class = None

    for line in lines:
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if class_match:
            current_class = class_match.group(1)
        elif current_class and is_top_level_statement(line):
            current_class = None

        match = re.match(
            r"(?P<indent>\s*)def (?P<name>[A-Za-z_]\w*)\([^)]*\): \.\.\.$",
            line,
        )
        signature = PYTHON_HELPER_METHOD_TYPES.get(
            (current_class, match.group("name")) if match else None
        )
        if signature is not None:
            args, return_type = signature
            updated.append(
                "%sdef %s(%s) -> %s: ..."
                % (match.group("indent"), match.group("name"), args, return_type)
            )
            continue

        updated.append(line)

    return "\n".join(updated) + "\n"


def normalize_extend_helpers(text):
    lines = text.splitlines()
    updated = []
    current_class = None

    for line in lines:
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if class_match:
            current_class = class_match.group(1)
        elif current_class and is_top_level_statement(line):
            current_class = None

        match = DEF_RE.match(line)
        signature = EXTEND_HELPER_METHOD_TYPES.get(
            (
                current_class,
                match.group("name"),
                match.group("args").strip(),
            )
            if match
            else None
        )
        if signature is not None:
            args, return_type = signature
            updated.append(
                "%sdef %s(%s) -> %s: ..."
                % (match.group("indent"), match.group("name"), args, return_type)
            )
            continue

        updated.append(line)

    return "\n".join(updated) + "\n"


def append_runtime_unsupported_note(updated, indent):
    note = "%s# %s" % (indent, RUNTIME_UNSUPPORTED_NOTE)
    if not updated or updated[-1] != note:
        updated.append(note)


def add_runtime_unsupported_notes(text, module):
    targets = RUNTIME_UNSUPPORTED_METHOD_NOTES.get(module)
    if not targets:
        return text

    lines = text.splitlines()
    updated = []
    current_class = None
    index = 0

    while index < len(lines):
        line = lines[index]
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if class_match:
            current_class = class_match.group(1)
            updated.append(line)
            index += 1
            continue
        if current_class and is_top_level_statement(line):
            current_class = None
            updated.append(line)
            index += 1
            continue

        decorators = []
        while current_class and index < len(lines) and re.match(r"\s*@", lines[index]):
            decorators.append(lines[index])
            index += 1

        if decorators:
            if index < len(lines):
                def_match = DEF_RE.match(lines[index])
                if (
                    def_match
                    and (current_class, def_match.group("name")) in targets
                ):
                    append_runtime_unsupported_note(
                        updated, def_match.group("indent")
                    )
                updated.extend(decorators)
                updated.append(lines[index])
                index += 1
                continue
            updated.extend(decorators)
            continue

        def_match = DEF_RE.match(line)
        if (
            def_match
            and current_class
            and (current_class, def_match.group("name")) in targets
        ):
            append_runtime_unsupported_note(updated, def_match.group("indent"))

        updated.append(line)
        index += 1

    return "\n".join(updated) + "\n"


def postprocess_stub(path, module, output_dir):
    if not os.path.exists(path):
        return 0

    with open(path) as stub_file:
        original = stub_file.read()

    class_names = collect_class_names(original)
    external_class_modules = collect_external_class_modules(
        output_dir, module, class_names
    )
    used_external_types = set()
    lines = original.splitlines()
    updated = []
    converted = 0
    index = 0
    current_class = None

    while index < len(lines):
        line = lines[index]
        class_match = re.match(r"^class\s+([A-Za-z_]\w*)", line)
        if class_match:
            current_class = class_match.group(1)
        elif current_class and is_top_level_statement(line):
            current_class = None

        def_match = DEF_RE.match(line)
        if not def_match:
            updated.append(line)
            index += 1
            continue

        signature_docstring = read_signature_docstring(
            lines, index + 1, def_match.group("name")
        )
        if not signature_docstring:
            updated.append(line)
            index += 1
            continue

        signatures, end = signature_docstring
        if len(signatures) == 1:
            updated.append(
                render_python_signature(
                    def_match,
                    signatures[0],
                    class_names,
                    class_name=current_class,
                    external_class_modules=external_class_modules,
                    used_external_types=used_external_types,
                )
            )
            converted += 1
        else:
            decorators = pop_decorators(updated, def_match.group("indent"))
            rendered_signatures = render_unique_python_signatures(
                def_match,
                signatures,
                class_names,
                current_class,
                external_class_modules,
                used_external_types,
            )
            if len(rendered_signatures) == 1:
                updated.extend(decorators)
                updated.append(rendered_signatures[0])
            else:
                updated.extend(
                    render_overload_block(def_match, rendered_signatures, decorators)
                )
            converted += len(rendered_signatures)
        index = end

    processed = "\n".join(updated) + "\n"
    processed, replaced_classes = replace_external_duplicate_classes(
        processed, module, output_dir, class_names
    )
    if replaced_classes:
        used_external_types.update(
            collect_referenced_external_types(
                processed, class_names, external_class_modules
            )
        )
    processed = normalize_operator_helpers(processed)
    processed = normalize_multifield_helpers(processed)
    processed = normalize_python_helpers(processed)
    processed = normalize_extend_helpers(processed)
    processed = normalize_property_attributes(
        processed,
        collect_property_doc_types(
            output_dir,
            module,
            class_names,
            external_class_modules,
            used_external_types,
        ),
    )
    processed = add_overload_import(processed)
    processed = add_missing_imports(processed)
    processed = add_type_imports(processed, used_external_types, external_class_modules)
    processed = normalize_swig_helpers(processed)
    processed = normalize_container_helpers(processed)
    processed = normalize_callback_helpers(processed)
    processed = remove_swig_meta_classmethod(processed)
    processed = add_runtime_unsupported_notes(processed, module)
    processed = add_typing_import(processed, "Any")
    processed = add_typing_import(processed, "Callable")
    processed = add_typing_import(processed, "Iterator")
    processed = add_typing_import(processed, "Sequence")
    processed = add_generated_header(processed)
    if processed != original:
        with open(path, "w") as stub_file:
            stub_file.write(processed)

    return converted


def write_private_extension_stub(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as stub_file:
        stub_file.write(PRIVATE_EXTENSION_STUB)


def run_stubgen(stubgen, module, output_dir, env):
    target = stub_path(output_dir, module)
    if os.path.exists(target):
        os.remove(target)

    command = [
        stubgen,
        "--ignore-errors",
        "--include-docstrings",
        "--inspect-mode",
        "-m",
        module,
        "-o",
        output_dir,
    ]
    result = subprocess.run(command, cwd=output_dir, env=env)
    if result.returncode != 0:
        print("warning: failed to generate stub for %s" % module, file=sys.stderr)
        return False

    if not os.path.exists(target):
        print("warning: stubgen did not create %s" % target, file=sys.stderr)
        return False

    converted = postprocess_stub(target, module, output_dir)
    if converted:
        print("postprocessed %d signatures in %s" % (converted, target))

    write_private_extension_stub(private_stub_path(output_dir, module))

    return True


def main():
    parser = argparse.ArgumentParser(description="Generate Pivy .pyi stubs")
    parser.add_argument("--stubgen")
    parser.add_argument("--output", required=True)
    parser.add_argument("--stamp", required=True)
    parser.add_argument("--module", action="append", required=True)
    args = parser.parse_args()

    stubgen = args.stubgen or shutil.which("stubgen")
    output_dir = os.path.abspath(args.output)
    stamp = os.path.abspath(args.stamp)
    package_dir = os.path.join(output_dir, "pivy")

    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        output_dir if not pythonpath else output_dir + os.pathsep + pythonpath
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    generated = []
    if not stubgen:
        print("warning: stubgen was not found", file=sys.stderr)
    else:
        for module in args.module:
            if run_stubgen(stubgen, module, output_dir, env):
                generated.append(module)

    py_typed = os.path.join(package_dir, "py.typed")
    if generated:
        os.makedirs(package_dir, exist_ok=True)
        with open(py_typed, "w"):
            pass
    elif os.path.exists(py_typed):
        os.remove(py_typed)

    os.makedirs(os.path.dirname(stamp), exist_ok=True)
    with open(stamp, "w") as stamp_file:
        stamp_file.write("\n".join(generated))
        stamp_file.write("\n")

    for dirpath, dirnames, _ in os.walk(package_dir):
        if "__pycache__" in dirnames:
            shutil.rmtree(os.path.join(dirpath, "__pycache__"))
            dirnames.remove("__pycache__")

    if not generated:
        print("warning: no Pivy stubs were generated", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
