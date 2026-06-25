# C++ meshfix port

This folder contains a dependency-free C++17 port of the core project code.

The Python implementation remains the main research implementation because it also contains
visualization, diagnostic scripts, and report-generation utilities. The C++ version focuses on
the reproducible algorithmic core requested for submission:

- OFF mesh reading and writing
- triangle quality metrics
- topology checks
- targeted degenerate-triangle cleanup

Build from the project root:

```sh
cd cpp
make
```

If the executable is already up to date, `make` may print:

```text
make: Nothing to be done for `all'.
```

This is not an error; it means `cpp/build/meshfix_cpp` already exists and the
source file has not changed. To force a clean rebuild:

```sh
cd cpp
make clean
make
```

Example commands from the project root:

```sh
cpp/build/meshfix_cpp analyze inputs/joint_input.off outputs/meshes/joint_adaptive_final.off
cpp/build/meshfix_cpp topology outputs/meshes/joint_adaptive_final.off
cpp/build/meshfix_cpp cleanup-degenerate inputs/cars/car3.off --out outputs/cpp/car3_cpp_cleanup.off --iterations 10
```

The targeted cleanup follows the same high-level rule as the Python version:

1. Measure all triangle angles, aspect ratios, and areas.
2. Mark needle-like triangles for shortest-edge collapse.
3. Mark cap-like triangles for longest-edge split.
4. Collapse only manifold, non-boundary, locally safe edges.
5. Split marked cap edges.
6. Remove degenerate and duplicate faces.
7. Repeat for the requested number of iterations.
