function(set_swig_properties NAME)
    set_property(SOURCE ${NAME} PROPERTY CPLUSPLUS ON)
    set_property(SOURCE ${NAME} PROPERTY SWIG_FLAGS "-includeall")
    set_property(SOURCE ${NAME} APPEND PROPERTY SWIG_FLAGS "-py3")
    set_property(SOURCE ${NAME} APPEND PROPERTY SWIG_FLAGS "-D__PIVY__")
    if(DISABLE_SWIG_WARNINGS)
        set_property(SOURCE ${NAME} APPEND PROPERTY SWIG_FLAGS
            "-w302,306,307,312,314,325,361,362,467,389,503,509,510")
    endif(DISABLE_SWIG_WARNINGS)
endfunction()

file(GLOB_RECURSE PIVY_COIN_PUBLIC_HEADERS CONFIGURE_DEPENDS
    "${Coin_INCLUDE_DIR}/Inventor/*.h")
set(PIVY_COIN_SWIG_DEPENDS
    "${PROJECT_SOURCE_DIR}/interfaces/coin_header_includes.h"
    ${PIVY_COIN_PUBLIC_HEADERS})
if (Coin_GENERATED_INCLUDE_DIR)
    file(GLOB_RECURSE PIVY_COIN_GENERATED_HEADERS CONFIGURE_DEPENDS
        "${Coin_GENERATED_INCLUDE_DIR}/Inventor/*.h")
    list(APPEND PIVY_COIN_SWIG_DEPENDS ${PIVY_COIN_GENERATED_HEADERS})
endif()

# Track the %included .i typemaps so editing one re-runs SWIG.
file(GLOB_RECURSE PIVY_SWIG_INTERFACE_FILES CONFIGURE_DEPENDS
    "${PROJECT_SOURCE_DIR}/interfaces/*.i"
    "${PROJECT_SOURCE_DIR}/Inventor/*.i"
    "${PROJECT_SOURCE_DIR}/VolumeViz/*.i")
list(APPEND PIVY_COIN_SWIG_DEPENDS ${PIVY_SWIG_INTERFACE_FILES})

function(configure_pivy_module_target TARGET_NAME OUTPUT_DIR)
    set_target_properties(${TARGET_NAME} PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY "${OUTPUT_DIR}"
        RUNTIME_OUTPUT_DIRECTORY "${OUTPUT_DIR}"
        AUTOMOC OFF
        AUTOUIC OFF
        AUTORCC OFF
    )

    # Make sure that on Windows, if the build is Debug mode, the appropriate suffix
    # gets added to the *.pyd file -- generally it's "_d", but to be thorough and
    # future proof, ask the python intepreter what it expects.
    if(WIN32)
        execute_process(
            COMMAND ${Python_EXECUTABLE} -c
                "import importlib.machinery as m; print(m.EXTENSION_SUFFIXES[-1])"
            OUTPUT_VARIABLE PIVY_EXTENSION_SUFFIX
            OUTPUT_STRIP_TRAILING_WHITESPACE)
        if(PIVY_EXTENSION_SUFFIX)
            set_target_properties(${TARGET_NAME} PROPERTIES
                SUFFIX "${PIVY_EXTENSION_SUFFIX}")
        endif()
    endif()

    foreach(CONFIG IN LISTS CMAKE_CONFIGURATION_TYPES)
        string(TOUPPER "${CONFIG}" CONFIG_UPPER)
        set_target_properties(${TARGET_NAME} PROPERTIES
            LIBRARY_OUTPUT_DIRECTORY_${CONFIG_UPPER} "${OUTPUT_DIR}"
            RUNTIME_OUTPUT_DIRECTORY_${CONFIG_UPPER} "${OUTPUT_DIR}"
        )
    endforeach()
endfunction()

function(configure_pivy_module_rpath TARGET_NAME)
    # Keep build-tree imports working via $ORIGIN, but let embedded consumers
    # override the install RUNPATH to match their final package layout.
    cmake_policy(SET CMP0068 NEW)  # Use RUNPATH instead of RPATH, default from CMake 3.9
    set_target_properties(${TARGET_NAME} PROPERTIES
        BUILD_RPATH "$ORIGIN"
        INSTALL_RPATH "${PIVY_MODULE_INSTALL_RPATH}"
        INSTALL_RPATH_USE_LINK_PATH FALSE
    )
endfunction()

set_swig_properties(coin.i)
set_property(SOURCE coin.i APPEND PROPERTY DEPENDS "${PIVY_COIN_SWIG_DEPENDS}")

# remember: the order of the includes is important!
# swig needs the generated headers first (these headers are replacing the origin Inventor headers)
set_property(SOURCE coin.i PROPERTY INCLUDE_DIRECTORIES "${PROJECT_SOURCE_DIR}")
set_property(SOURCE coin.i APPEND PROPERTY INCLUDE_DIRECTORIES "${PROJECT_SOURCE_DIR}/fake_headers")
set_property(SOURCE coin.i APPEND PROPERTY INCLUDE_DIRECTORIES "${Coin_INCLUDE_DIR}")
if (Coin_GENERATED_INCLUDE_DIR)
    set_property(SOURCE coin.i APPEND PROPERTY INCLUDE_DIRECTORIES "${Coin_GENERATED_INCLUDE_DIR}")
endif()

swig_add_library(pivy_coin
    LANGUAGE python
    OUTPUT_DIR "${PIVY_PACKAGE_OUTPUT_DIR}"
    OUTFILE_DIR "${CMAKE_CURRENT_BINARY_DIR}"
    SOURCES coin.i)
set_target_properties(pivy_coin PROPERTIES OUTPUT_NAME coin)
configure_pivy_module_target(pivy_coin "${PIVY_PACKAGE_OUTPUT_DIR}")
add_dependencies(pivy pivy_coin)

if (APPLE)
    set_target_properties(pivy_coin PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
endif()

if (MSVC)
    set_target_properties(pivy_coin PROPERTIES COMPILE_FLAGS "/bigobj")
endif ()

target_include_directories(pivy_coin
    PUBLIC
    ${Coin_INCLUDE_DIR}
    ${Python_INCLUDE_DIRS}
    PRIVATE
    ${PROJECT_SOURCE_DIR}/interfaces
    )

target_link_libraries(pivy_coin PUBLIC Coin::Coin Python::Module)
install(TARGETS pivy_coin DESTINATION "${PIVY_PACKAGE_INSTALL_DIR}")
configure_pivy_module_rpath(pivy_coin)

if(PIVY_BUILD_SOQT)

    set_swig_properties(soqt.i)
    set_property(SOURCE soqt.i APPEND PROPERTY DEPENDS "${PIVY_COIN_SWIG_DEPENDS}")

    # remember: the order of the includes is important!
    # swig needs the generated headers first (these headers are replacing the origin Inventor headers)
    set_property(SOURCE soqt.i PROPERTY INCLUDE_DIRECTORIES "${CMAKE_SOURCE_DIR}")
    set_property(SOURCE soqt.i APPEND PROPERTY INCLUDE_DIRECTORIES "${CMAKE_SOURCE_DIR}/fake_headers")
    set_property(SOURCE soqt.i APPEND PROPERTY INCLUDE_DIRECTORIES "${SoQt_INCLUDE_DIRS}")
    set_property(SOURCE soqt.i APPEND PROPERTY INCLUDE_DIRECTORIES "${Coin_INCLUDE_DIR}")


    swig_add_library(soqt
        LANGUAGE python
        OUTPUT_DIR "${PIVY_PACKAGE_OUTPUT_DIR}/gui"
        OUTFILE_DIR "${CMAKE_CURRENT_BINARY_DIR}"
        SOURCES soqt.i)
    configure_pivy_module_target(soqt "${PIVY_PACKAGE_OUTPUT_DIR}/gui")
    add_dependencies(pivy soqt)

    if (APPLE)
        set_target_properties(soqt PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
    endif()

    if (MSVC)
        set_target_properties(pivy_coin PROPERTIES COMPILE_FLAGS "/bigobj")
    endif ()

    if (PIVY_USE_QT6)
        set(QT_INC_DIRS ${Qt6Gui_INCLUDE_DIRS} ${Qt6Widgets_INCLUDE_DIRS})
    else ()
        set(QT_INC_DIRS ${Qt5Gui_INCLUDE_DIRS} ${Qt5Widgets_INCLUDE_DIRS})
    endif ()

    target_include_directories(soqt
        PUBLIC
        ${Coin_INCLUDE_DIR}
        ${SoQt_INCLUDE_DIRS}
        ${QT_INC_DIRS}
        ${Python_INCLUDE_DIRS}
        PRIVATE
        ${PROJECT_SOURCE_DIR}/interfaces
        )

    target_link_libraries(soqt PUBLIC SoQt::SoQt Python::Module)
    install(TARGETS soqt DESTINATION "${PIVY_PACKAGE_INSTALL_DIR}/gui")
    configure_pivy_module_rpath(soqt)
endif()
