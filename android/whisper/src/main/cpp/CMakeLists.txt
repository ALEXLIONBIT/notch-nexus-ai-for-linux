# NEXUS: whisper.cpp per sentire il nome dell'agente ("Ehi Marco") sul telefono.
# ggml è compilato DENTRO libnexuswhisper.so con i simboli nascosti: così non si scontra con il ggml
# del motore dei modelli (modulo llama), che è un'altra versione.
cmake_minimum_required(VERSION 3.22)
project(nexuswhisper C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_C_VISIBILITY_PRESET hidden)
set(CMAKE_CXX_VISIBILITY_PRESET hidden)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

include(FetchContent)
FetchContent_Declare(whisper URL https://github.com/ggml-org/whisper.cpp/archive/refs/tags/v1.9.6.tar.gz)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(GGML_NATIVE OFF CACHE BOOL "" FORCE)
set(GGML_OPENMP OFF CACHE BOOL "" FORCE)
set(GGML_LLAMAFILE OFF CACHE BOOL "" FORCE)
set(GGML_BACKEND_DL OFF CACHE BOOL "" FORCE)
if(ANDROID_ABI STREQUAL "armeabi-v7a")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -mfpu=neon-vfpv4 -mfloat-abi=softfp" CACHE STRING "" FORCE)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -mfpu=neon-vfpv4 -mfloat-abi=softfp" CACHE STRING "" FORCE)
endif()
FetchContent_MakeAvailable(whisper)

add_library(nexuswhisper SHARED nexus_whisper.cpp)
target_link_libraries(nexuswhisper whisper android log)
target_link_options(nexuswhisper PRIVATE "-Wl,--exclude-libs,ALL" "-Wl,-Bsymbolic")
