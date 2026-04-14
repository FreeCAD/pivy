"""Declarative normalization data for the Pivy stub generator."""

BOOL_TYPES = {"bool", "SbBool"}
FLOAT_TYPES = {"double", "float"}
INT_TYPES = {
    "int",
    "int8_t",
    "int16_t",
    "int32_t",
    "int64_t",
    "long",
    "long int",
    "long long",
    "SbUniqueId",
    "short",
    "short int",
    "signed char",
    "signed int",
    "size_t",
    "time_t",
    "uint8_t",
    "uint16_t",
    "uint32_t",
    "uint64_t",
    "unsigned",
    "unsigned char",
    "unsigned int",
    "unsigned long",
    "unsigned long int",
    "unsigned long long",
    "unsigned short",
    "unsigned short int",
}
COMPARISON_METHODS = {
    "__eq__",
    "__ge__",
    "__gt__",
    "__le__",
    "__lt__",
    "__ne__",
}
POINTER_HELPER_TYPES = {
    "charp": "str",
    "intp": "int",
    "longp": "int",
    "floatp": "float",
    "doublep": "float",
}
SCALAR_POINTER_HELPER_PARAMETERS = {
    ("SoQt", "getVersionInfo", "major"): "intp",
    ("SoQt", "getVersionInfo", "minor"): "intp",
    ("SoQt", "getVersionInfo", "micro"): "intp",
}
SCALAR_REFERENCE_HELPER_TYPES = {
    "SbBool": "intp",
    "char": "charp",
    "double": "doublep",
    "float": "floatp",
    "int": "intp",
    "long": "longp",
}
SEQUENCE_POINTER_PARAMETERS = {
    ("SbColor", "__init__", "rgb"): "Sequence[float]",
    ("SbColor4f", "__init__", "rgba"): "Sequence[float]",
    ("SoQt", "init", "argv"): "Sequence[str]",
}
SEQUENCE_ARRAY_PARAMETERS = {
    ("SbVec2s", "__init__", "v"): ("Sequence[int]", "2"),
    ("SbVec2s", "setValue", "v"): ("Sequence[int]", "2"),
    ("SbVec3s", "__init__", "v"): ("Sequence[int]", "3"),
    ("SbVec3s", "setValue", "v"): ("Sequence[int]", "3"),
}
BOOL_SEQUENCE_ARRAY_PARAMETERS = {
    ("SoQtViewer", "setAnaglyphStereoColorMasks", "left"): ("Sequence[bool]", "3"),
    ("SoQtViewer", "setAnaglyphStereoColorMasks", "right"): ("Sequence[bool]", "3"),
}
MATRIX_SEQUENCE_PARAMETERS = {
    ("SbDPMatrix", "__init__", "matrix"): "Sequence[Sequence[float]]",
    ("SbDPMatrix", "setValue", "m"): "Sequence[Sequence[float]]",
    ("SbMatrix", "__init__", "matrix"): "Sequence[Sequence[float]]",
    ("SbMatrix", "setValue", "m"): "Sequence[Sequence[float]]",
}
MATRIX_CPP_TYPES = {"SbDPMat", "SbMat"}
SEQUENCE_VALUE_RETURN_TYPES = {
    "SbColor": "Sequence[float]",
    "SbColor4f": "Sequence[float]",
    "SbDPRotation": "Sequence[float]",
    "SbRotation": "Sequence[float]",
    "SbVec2d": "Sequence[float]",
    "SbVec2f": "Sequence[float]",
    "SbVec2s": "Sequence[int]",
    "SbVec3d": "Sequence[float]",
    "SbVec3f": "Sequence[float]",
    "SbVec4d": "Sequence[float]",
    "SbVec4f": "Sequence[float]",
}
MATRIX_VALUE_RETURN_TYPES = {
    "SbDPMatrix": "Sequence[Sequence[float]]",
    "SbMatrix": "Sequence[Sequence[float]]",
}
MATRIX_ROW_RETURN_TYPES = {
    "SbMatrix": "Sequence[float]",
}
STRING_POINTER_PARAMETERS = {
    ("SbName", "__eq__", "u"),
    ("SbName", "__nq__", "u"),
    ("SbString", "__eq__", "u"),
    ("SbString", "__nq__", "u"),
}
INPLACE_DIVISION_METHODS = {"__idiv__", "__itruediv__"}
MULTIFIELD_SETVALUES_TYPES = {
    "SoMFBool": ("bool",),
    "SoMFColor": ("SbColor", "SbVec3f", "Sequence[float]"),
    "SoMFEngine": ("SoEngine",),
    "SoMFEnum": ("int",),
    "SoMFFloat": ("float",),
    "SoMFInt32": ("int",),
    "SoMFMatrix": ("SbMatrix",),
    "SoMFName": ("SbName | str",),
    "SoMFNode": ("SoNode",),
    "SoMFPath": ("SoPath",),
    "SoMFPlane": ("SbPlane",),
    "SoMFRotation": ("SbRotation", "Sequence[float]"),
    "SoMFShort": ("int",),
    "SoMFString": ("SbString | str",),
    "SoMFTime": ("SbTime",),
    "SoMFUInt32": ("int",),
    "SoMFUShort": ("int",),
    "SoMFVec2f": ("SbVec2f", "Sequence[float]"),
    "SoMFVec3d": ("SbVec3d", "Sequence[float]"),
    "SoMFVec3f": ("SbVec3f", "Sequence[float]"),
    "SoMFVec4f": ("SbVec4f", "Sequence[float]"),
}
PYTHON_HELPER_METHOD_TYPES = {
    ("_SwigNonDynamicMeta", "__setattr__"): (
        "cls, name: str, value: Any",
        "None",
    ),
    ("SoBase", "__nonzero__"): ("self", "bool"),
    ("SoBaseKit", "__getattr__"): ("self, name: str", "Any"),
    ("SoBaseKit", "__setattr__"): ("self, name: str, value: Any", "None"),
    ("SoEngine", "__getattr__"): ("self, name: str", "Any"),
    ("SoEngine", "__setattr__"): ("self, name: str, value: Any", "None"),
    ("SoFieldContainer", "__dir__"): ("self", "list[str]"),
    ("SoFieldContainer", "__getattr__"): ("self, name: str", "Any"),
    ("SoFieldContainer", "__setattr__"): ("self, name: str, value: Any", "None"),
    ("SoGroup", "__iadd__"): ("self, other: SoNode | Sequence[SoNode]", "SoGroup"),
    ("SoGroup", "__isub__"): ("self, other: SoNode | Sequence[SoNode]", "SoGroup"),
    ("SoGroup", "getByName"): ("self, name: SbName | str", "SoNode | None"),
    ("SoNodeKitPath", "index"): ("self", "Iterator[int]"),
    ("SoPath", "index"): ("self", "Iterator[int]"),
}
EXTEND_HELPER_METHOD_TYPES = {
    ("SoCallbackAction", "getMaterial", "self, index: int = ..."): (
        "self, index: int = ...",
        "tuple[SbColor, SbColor, SbColor, SbColor, float, float]",
    ),
    ("SoFieldContainer", "getFieldName", "self, field: SoField"): (
        "self, field: SoField",
        "str | None",
    ),
    ("SoSensorManager", "isTimerSensorPending", "self"): (
        "self",
        "SbTime | None",
    ),
    ("SoType", "createInstance", "self"): (
        "self",
        "SoBase | SoField | SoPath | None",
    ),
    ("SbMatrix", "getTransform", "self"): (
        "self",
        "tuple[SbVec3f, SbRotation, SbVec3f, SbRotation]",
    ),
    ("SbMatrix", "getTransform", "self, center: SbVec3f"): (
        "self, center: SbVec3f",
        "tuple[SbVec3f, SbRotation, SbVec3f, SbRotation]",
    ),
    ("SbViewVolume", "projectPointToLine", "self, SbVec3f: Incomplete"): (
        "self, pt: SbVec2f",
        "tuple[SbVec3f, SbVec3f]",
    ),
    ("SbViewVolume", "projectToScreen", "self, arg1: SbVec3f"): (
        "self, src: SbVec3f",
        "SbVec3f",
    ),
}
CALLBACK_PARAMETER_NAMES = {
    "callback",
    "cb",
    "f",
    "func",
    "function",
    "pyfunc",
    "sensorQueueChangedCB",
}
CALLBACK_DATA_PARAMETER_NAMES = {
    "callbackdata",
    "cbuserdata",
    "closure",
    "data",
    "user",
    "userdata",
    "userData",
}
CALLBACK_HANDLE_PARAMETER_NAMES = {"tuple"}
CALLBACK_TYPE_SIGNATURES = {
    "ScXMLStateChangeCB": (
        "Callable[[Any, ScXMLStateMachine, str, bool, bool], None]"
    ),
    "ScXMLStateMachineDeleteCB": "Callable[[Any, ScXMLStateMachine], None]",
    "SoCallbackAction::SoCallbackActionCB": (
        "Callable[[Any, SoCallbackAction, SoNode], int]"
    ),
    "SoCallbackCB": "Callable[[Any, SoAction], None]",
    "SoDraggerCB": "Callable[[Any, SoDragger], None]",
    "SoEventCallbackCB": "Callable[[Any, SoEventCallback], None]",
    "SoGLPreRenderCB": "Callable[[Any, SoGLRenderAction], None]",
    "SoGLRenderAction::SoGLRenderAbortCB": "Callable[[Any], int]",
    "SoGLRenderPassCB": "Callable[[Any], None]",
    "SoIntersectionDetectionAction::SoIntersectionCB": (
        "Callable[[Any, SoIntersectingPrimitive, SoIntersectingPrimitive], int]"
    ),
    "SoIntersectionDetectionAction::SoIntersectionFilterCB": (
        "Callable[[Any, SoPath, SoPath], bool]"
    ),
    "SoIntersectionDetectionAction::SoIntersectionVisitationCB": (
        "Callable[[Any, SoPath], int]"
    ),
    "SoLineSegmentCB": (
        "Callable[[Any, SoCallbackAction, SoPrimitiveVertex, "
        "SoPrimitiveVertex], None]"
    ),
    "SoPointCB": "Callable[[Any, SoCallbackAction, SoPrimitiveVertex], None]",
    "SoRenderManagerRenderCB": "Callable[[Any, SoRenderManager], None]",
    "SoSceneManagerRenderCB": "Callable[[Any, SoSceneManager], None]",
    "SoSelectionClassCB": "Callable[[Any, SoSelection], None]",
    "SoSelectionPathCB": "Callable[[Any, SoPath], None]",
    "SoSelectionPickCB": "Callable[[Any, SoPickedPoint], SoPath]",
    "SoTriangleCB": (
        "Callable[[Any, SoCallbackAction, SoPrimitiveVertex, "
        "SoPrimitiveVertex, SoPrimitiveVertex], None]"
    ),
    "SoQtRenderAreaEventCB": "Callable[[Any, QEvent], Any]",
}
FUNCTION_POINTER_TYPE_SIGNATURES = {
    "void(*)(void*)": "Callable[[Any], None]",
}
SENSOR_CALLBACK_CLASSES = {
    "SoAlarmSensor",
    "SoDelayQueueSensor",
    "SoFieldSensor",
    "SoIdleSensor",
    "SoNodeSensor",
    "SoOneShotSensor",
    "SoPathSensor",
    "SoTimerQueueSensor",
    "SoTimerSensor",
}
KNOWN_ITER_ELEMENT_TYPES = {
    "SbIntList": "int",
    "SbName": "str",
    "SbPList": "Any",
    "SbString": "str",
    "SbVec2d": "float",
    "SbVec2f": "float",
    "SbVec2s": "int",
    "SbVec3d": "float",
    "SbVec3f": "float",
    "SbVec3s": "int",
    "SbVec4d": "float",
    "SbVec4f": "float",
    "SoMField": "Any",
    "SoNodeKitPath": "SoNode",
    "SoPath": "SoNode",
}
RUNTIME_UNSUPPORTED_NOTE = (
    "NOTE: SWIG exposes raw C pointers here; keep Incomplete until a "
    "Python-level wrapper exists."
)
RUNTIME_UNSUPPORTED_METHOD_NOTES = {
    "pivy.coin": {
        ("SoDataSensor", "setDeleteCallback"),
        ("SoDebugError", "setHandlerCallback"),
        ("SoError", "setHandlerCallback"),
        ("SoGLImage", "setEndFrameCallback"),
        ("SoMFDouble", "getValues"),
        ("SoMFDouble", "setValues"),
        ("SoMemoryError", "setHandlerCallback"),
        ("SoReadError", "setHandlerCallback"),
        ("SoSensor", "setFunction"),
    },
    "pivy.gui.soqt": {
        ("SoDebugError", "setHandlerCallback"),
        ("SoError", "setHandlerCallback"),
    },
}
GENERATED_HEADER = (
    "# SPDX-License-Identifier: ISC\n"
    "# Generated from local Pivy stubgen output; lightly normalized for checker use.\n"
    "\n"
)
PRIVATE_EXTENSION_STUB = (
    GENERATED_HEADER
    + "from typing import Any\n"
    + "\n"
    + "def cast(*args: Any, **kwargs: Any) -> Any: ...\n"
)

