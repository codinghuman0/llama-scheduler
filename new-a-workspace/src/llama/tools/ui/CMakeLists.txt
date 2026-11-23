# Retained assets from the validated runtime; no network or Node build required.
add_library(llama-ui STATIC frozen-ui.cpp frozen-ui.h)
set_target_properties(llama-ui PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_compile_features(llama-ui PRIVATE cxx_std_17)
target_include_directories(llama-ui PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
