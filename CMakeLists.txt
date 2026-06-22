cmake_minimum_required(VERSION 3.18...3.30)
project(pivy_cmake_setup CXX)

file(READ "${PROJECT_SOURCE_DIR}/pivy/pivy_meta.py" _pivy_meta)
string(REGEX MATCH "__version__[ \t]*=[ \t]*[\"']([^\"']+)[\"']"
    _pivy_version_match "${_pivy_meta}")
if (NOT _pivy_version_match)
    message(FATAL_ERROR "Could not determine Pivy version: __version__ not found")
endif()
set(PIVY_VERSION "${CMAKE_MATCH_1}" CACHE INTERNAL "Pivy version string")

if (NOT DEFINED CMAKE_POLICY_VERSION_MINIMUM)
    set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
endif()

option(DISABLE_SWIG_WARNINGS "if on no swig warnings are shown" OFF)
option(PIVY_USE_QT6 "Prefer Qt6 over Qt5 if available" OFF)
option(PIVY_USE_SOQT "Generate bindings for SoQt" ON)
option(PIVY_GENERATE_PYI "Generate .pyi stubs with mypy.stubgen when available" ON)
set(PIVY_PACKAGE_OUTPUT_DIR "${PROJECT_BINARY_DIR}/pivy"
    CACHE PATH "Build-tree output directory for the importable pivy package")

find_package(SWIG 4.0.0 REQUIRED)
include(${SWIG_USE_FILE})

if (NOT TARGET Coin)
    find_package(Coin CONFIG REQUIRED)
else()
    set(Coin_FOUND 1)
    get_target_property(Coin_LIB_DIR Coin LIBRARY_OUTPUT_DIRECTORY)
    if(DEFINED COIN_VERSION)
        set(Coin_VERSION "${COIN_VERSION}")
    else()
        set(Coin_VERSION "unknown")
    endif()

    set(Coin_INCLUDE_DIR ${Coin_SOURCE_DIR}/include)
    set(Coin_GENERATED_INCLUDE_DIR ${Coin_BINARY_DIR}/include)

    if(NOT TARGET Coin::Coin)
        add_library(Coin::Coin ALIAS Coin)
    endif()
endif()
set(PIVY_BUILD_SOQT OFF)
if(PIVY_USE_SOQT)
    find_package(SoQt CONFIG)
    if(SoQt_FOUND)
        set(PIVY_BUILD_SOQT ON)
    endif()
endif()

if(PIVY_BUILD_SOQT)
    if (PIVY_USE_QT6)
        find_package(Qt6 COMPONENTS Core Widgets Gui REQUIRED)
    else (PIVY_USE_QT6)
        find_package(Qt5 COMPONENTS Core Widgets Gui REQUIRED)
    endif (PIVY_USE_QT6)
endif()

find_package(Python REQUIRED COMPONENTS Interpreter Development)

if (NOT PIVY_Python_SITEARCH)
    SET(PIVY_Python_SITEARCH ${Python_SITEARCH})
endif()

file(TO_CMAKE_PATH "${PIVY_Python_SITEARCH}" PIVY_Python_SITEARCH)
file(TO_CMAKE_PATH "${PIVY_PACKAGE_OUTPUT_DIR}" PIVY_PACKAGE_OUTPUT_DIR)
get_filename_component(PIVY_PACKAGE_PARENT_DIR "${PIVY_PACKAGE_OUTPUT_DIR}" DIRECTORY)

if (Python_FOUND)
	MESSAGE(STATUS "Python_FOUND: TRUE")
	MESSAGE(STATUS "PIVY_Python_SITEARCH: ${PIVY_Python_SITEARCH}")
endif()

if (Coin_FOUND)
	MESSAGE(STATUS "COIN_FOUND: TRUE")
	MESSAGE(STATUS "COIN_INCLUDE_DIR: ${Coin_INCLUDE_DIR}")
	MESSAGE(STATUS "COIN_LIB_DIR: ${Coin_LIB_DIR}")
	MESSAGE(STATUS "COIN_VERSION: ${Coin_VERSION}")
endif()

if(PIVY_BUILD_SOQT)
	MESSAGE(STATUS "SOQT_FOUND: True")
	MESSAGE(STATUS "SOQT_INCLUDE_DIRS: ${SoQt_INCLUDE_DIRS}")
	MESSAGE(STATUS "SOQT_LIB_DIRS: ${SoQt_LIBRARY_DIRS}")
	MESSAGE(STATUS "SOQT_VERSION: ${SoQt_VERSION}")
endif()

# SWIGIFY HEADERS
# doing this with the origin python functions

execute_process(COMMAND ${Python_EXECUTABLE} ${PROJECT_SOURCE_DIR}/install_helpers.py ${PROJECT_SOURCE_DIR} ${Coin_INCLUDE_DIR})


# copy the python module
include(TargetCopyFiles.cmake)

add_custom_target(pivy ALL)
add_copy_directory(pivy ${PROJECT_SOURCE_DIR}/pivy
    DESTINATION "${PIVY_PACKAGE_OUTPUT_DIR}"
    GLOB "*.py" "*.pyi" "py.typed"
)

add_subdirectory(interfaces)

if(PIVY_GENERATE_PYI)
    find_program(PIVY_STUBGEN_EXECUTABLE NAMES stubgen)

    if(PIVY_STUBGEN_EXECUTABLE)
        set(PIVY_STUB_MODULES pivy.coin)
        set(PIVY_STUB_TARGETS pivy coin)

        if(PIVY_BUILD_SOQT)
            list(APPEND PIVY_STUB_MODULES pivy.gui.soqt)
            list(APPEND PIVY_STUB_TARGETS soqt)
        endif()

        set(PIVY_STUBGEN_ARGS)
        foreach(PIVY_STUB_MODULE IN LISTS PIVY_STUB_MODULES)
            list(APPEND PIVY_STUBGEN_ARGS --module ${PIVY_STUB_MODULE})
        endforeach()

        set(PIVY_STUB_OUTPUTS ${PIVY_PACKAGE_OUTPUT_DIR}/py.typed)
        foreach(PIVY_STUB_MODULE IN LISTS PIVY_STUB_MODULES)
            string(REPLACE "." "/" PIVY_STUB_MODULE_PATH ${PIVY_STUB_MODULE})
            get_filename_component(PIVY_STUB_MODULE_DIR
                ${PIVY_STUB_MODULE_PATH} DIRECTORY
            )
            get_filename_component(PIVY_STUB_MODULE_NAME
                ${PIVY_STUB_MODULE_PATH} NAME
            )
            list(APPEND PIVY_STUB_OUTPUTS
                ${PIVY_PACKAGE_PARENT_DIR}/${PIVY_STUB_MODULE_PATH}.pyi
            )
            set(PIVY_STUB_PRIVATE_OUTPUT
                ${PIVY_PACKAGE_PARENT_DIR}/${PIVY_STUB_MODULE_DIR}/_${PIVY_STUB_MODULE_NAME}.pyi
            )
            list(APPEND PIVY_STUB_OUTPUTS
                ${PIVY_STUB_PRIVATE_OUTPUT}
            )
        endforeach()

        set(PIVY_STUB_PREPARE_COMMANDS
            COMMAND ${CMAKE_COMMAND} -E make_directory ${PIVY_PACKAGE_OUTPUT_DIR}
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                $<TARGET_FILE:coin>
                ${PIVY_PACKAGE_OUTPUT_DIR}/$<TARGET_FILE_NAME:coin>
        )
        set(PIVY_STUB_CLEANUP_COMMANDS
            COMMAND ${CMAKE_COMMAND} -E rm -f
                ${PIVY_PACKAGE_OUTPUT_DIR}/$<TARGET_FILE_NAME:coin>
        )

        if(PIVY_BUILD_SOQT)
            list(APPEND PIVY_STUB_PREPARE_COMMANDS
                COMMAND ${CMAKE_COMMAND} -E make_directory ${PIVY_PACKAGE_OUTPUT_DIR}/gui
                COMMAND ${CMAKE_COMMAND} -E copy_if_different
                    $<TARGET_FILE:soqt>
                    ${PIVY_PACKAGE_OUTPUT_DIR}/gui/$<TARGET_FILE_NAME:soqt>
            )
            list(APPEND PIVY_STUB_CLEANUP_COMMANDS
                COMMAND ${CMAKE_COMMAND} -E rm -f
                    ${PIVY_PACKAGE_OUTPUT_DIR}/gui/$<TARGET_FILE_NAME:soqt>
            )
        endif()

        add_custom_command(
            OUTPUT ${PIVY_PACKAGE_OUTPUT_DIR}/.pyi-stamp
            BYPRODUCTS ${PIVY_STUB_OUTPUTS}
            ${PIVY_STUB_PREPARE_COMMANDS}
            COMMAND ${Python_EXECUTABLE}
                ${CMAKE_SOURCE_DIR}/tools/generate_pivy_stubs.py
                --stubgen ${PIVY_STUBGEN_EXECUTABLE}
                --output ${PIVY_PACKAGE_PARENT_DIR}
                --stamp ${PIVY_PACKAGE_OUTPUT_DIR}/.pyi-stamp
                ${PIVY_STUBGEN_ARGS}
            ${PIVY_STUB_CLEANUP_COMMANDS}
            DEPENDS ${CMAKE_SOURCE_DIR}/tools/generate_pivy_stubs.py
            WORKING_DIRECTORY ${PIVY_PACKAGE_PARENT_DIR}
            COMMENT "Generating Pivy .pyi stubs"
            VERBATIM
            COMMAND_EXPAND_LISTS
        )

        add_custom_target(pivy_stubs ALL
            DEPENDS ${PIVY_PACKAGE_OUTPUT_DIR}/.pyi-stamp
        )
        add_dependencies(pivy_stubs ${PIVY_STUB_TARGETS})
    else()
        message(WARNING "stubgen is not available; Pivy .pyi stubs will not be generated")
    endif()
endif()

install(DIRECTORY
    "${PIVY_PACKAGE_OUTPUT_DIR}/"
    DESTINATION "${PIVY_Python_SITEARCH}/pivy"
    FILES_MATCHING
    PATTERN "*.py"
    PATTERN "*.so"
    PATTERN "*.dylib"
    PATTERN "*.dll"
    PATTERN "*.pyd"
    PATTERN "*.pyi"
    PATTERN "py.typed"
    )
