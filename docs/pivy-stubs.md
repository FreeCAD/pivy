# Pivy Stubs

## Editor and Checker Smoke Test

The generated `pivy.coin` and `pivy.gui.soqt` `.pyi` files are committed next
to the package so editors can use them directly from a checkout. After pixi has
created the environment, VS Code can use the checked-in `.vscode` workspace
settings directly. Open the repository root, install the recommended Python and
Pylance extensions when prompted, and use
`Terminal > Run Task... > Pivy: typecheck stubs`.

The workspace points the Python extension at the pixi environment:

- POSIX: `.pixi/envs/default/bin/python`
- Windows: `.pixi\envs\default\python.exe`

Pyright/Pylance should then resolve `from pivy import coin` and
`from pivy.gui import soqt` from the committed stubs. The same smoke check can
be run without an editor:

```sh
pixi run typecheck_stubs
```

That task runs both:

```sh
pixi run typecheck_stubs_pyright
pixi run typecheck_stubs_pyrefly
```

`pixi run test_stubs` still validates the generated build stubs, runs the mypy
import check, and compares the generated files against the committed source
stubs to catch drift.

## Stub TODOs

## Runtime-Unsupported SWIG Surfaces

The generated `.pyi` files intentionally leave some APIs as `Incomplete` when
the current SWIG wrapper exposes a raw C pointer surface instead of a normal
Python value. These should not be typed as `Callable`, `Sequence`, or `Any`
until the binding grows a Python-level wrapper or typemap.

Known callback-pointer surfaces:

- `SoError.setHandlerCallback`
- `SoDebugError.setHandlerCallback`
- `SoMemoryError.setHandlerCallback`
- `SoReadError.setHandlerCallback`
- `SoSensor.setFunction`
- `SoDataSensor.setDeleteCallback`
- `SoGLImage.setEndFrameCallback`

Known pointer-buffer surfaces:

- `SoMFDouble.getValues`
- `SoMFDouble.setValues`

High-volume `Incomplete` clusters that still need SWIG-side work:

- Class-specific static `createInstance()` methods where SWIG reports
  `void *`. Runtime returns a raw `SwigPyObject` pointer, unlike the
  Python-level `SoType.createInstance()` helper which is already typed as
  `SoBase | SoField | SoPath | None`.
- Raw callback registration tables and function-pointer fields, including
  `addMethod` action dispatch hooks, `SoActionMethodList`, `SbHeapFuncs`, and
  `SbOctTreeFuncs`.
- Raw `FILE *`, buffer, and select-loop entry points such as `output`,
  `SoInput.setFilePointer`, `SoOutput.setFilePointer`, binary array readers,
  and binary array writers.
- Image and texture byte-buffer APIs such as `SbImage`, `SoSFImage`,
  `SoSFImage3`, and `SoMultiTextureImageElement`.

Representative surfaces now validator-guarded to stay `Incomplete`:

- Callback and function-table surfaces:
  `SoActionMethodList.{addMethod,__setitem__,__getitem__,get}`,
  `SoQt.setFatalErrorHandler`,
  `SoQtComponent.setWindowCloseCallback`,
  `SoQtViewer.{addStartCallback,addFinishCallback,removeStartCallback,removeFinishCallback}`,
  `SoQtPopupMenu.{addMenuSelectionCallback,removeMenuSelectionCallback}`,
  `SbHeapFuncs.*`, and `SbOctTreeFuncs.*`.
- Raw file and buffer surfaces:
  `SoInput.{setFilePointer,getCurFile,setBuffer,readBinaryArray}`,
  `SoOutput.{setFilePointer,getFilePointer,setBuffer,getBuffer}`.
- Raw image and texture byte buffers:
  `SbImage.{__init__,addReadImageCB,scheduleReadFile,getValue}`,
  `SoSFImage.{startEditing,setValue}`,
  `SoSFImage3.{getValue,startEditing,setValue}`,
  `SoMultiTextureImageElement.{getDefault,set,get}`.
- Abstract storage surfaces:
  `SoMField.values`, `SbHeap.{add,extractMin,buildHeap}`,
  and `SbOctTree.{addItem,findItems}`.

## Remaining By-Reference Gaps

Some non-const reference parameters are now split into two buckets:

- Helper-backed refs that the current wrapper already accepts through pointer
  proxy classes. These are typed in `.pyi` today, for example `charp`,
  `intp`, `floatp`, `doublep`, `longp`, and `SbBool &` via `intp`.
- Reference params that still have no honest Python helper surface. These now
  stay `Incomplete` instead of pretending to be plain `int` or `bool`.

Representative unsupported scalar-ref surfaces:

- `SbTime.getValue(time_t & sec, long & usec)`
- `SoInput.readHex(uint32_t & l)`
- `SoInput.read(unsigned int & i)`
- `SoInput.read(short & s)`
- `SoInput.read(unsigned short & s)`
- `SoOutput.getAvailableCompressionMethods(unsigned int & num)`
- short/unsigned-short box and vector out-params such as
  `SbBox2s.getBounds(...)` and `SbVec4us.getValue(...)`

Representative unsupported enum-ref surfaces:

- `SoPolygonOffsetElement.{get,getDefault}` with `Style &`
- `SoDepthBufferElement.get(...)` with `DepthWriteFunction &`
- `SoShapeHintsElement.get(...)` with shape-hint enum refs
- `SoMultiTextureImageElement.get(...)` with `Wrap &` and `Model &`

TODO: add SWIG typemaps or Python wrapper helpers for these families before
tightening the stubs. Until then, `Incomplete` is the least misleading type.

Known fixed-width integer array surfaces:

- `SbVec2b`, `SbVec2i32`, `SbVec3b`, `SbVec3i32`, `SbVec4b`, `SbVec4ub`,
  `SbVec4s`, `SbVec4us`, `SbVec4i32`, and `SbVec4ui32` sequence constructors
  and `setValue` overloads
- `SbMatrix.LUDecomposition`
- `SbDPMatrix.LUDecomposition`
- `SoSFVec2s.setValue`
- `SoSFVec3s.setValue`
- `SoMFVec2s.set1Value`
- `SoMFVec2s.setValue`
- `SoMFVec3s.set1Value`
- `SoMFVec3s.setValue`

TODO: Add SWIG-side support before tightening these stubs. For callbacks, add
explicit Python-callable overloads or typemaps that retain the callback and
userdata safely. For `SoMFDouble`, add a bounded Python sequence wrapper or a
`double const *` typemap that accepts Python float sequences without exposing
pointer-shaped values. For fixed-width integer arrays, add typemaps that accept
Python integer sequences for the wrapped C array overloads.
