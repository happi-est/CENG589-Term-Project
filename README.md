# CENG589 Mesh Quality Project

This package contains the Python implementation, a dependency-free C++17 core
port, report sources, input meshes, selected outputs, and diagnostic scripts for
the CENG589 Digital Geometry Processing term project.

The project studies skinny/degenerate triangles in OFF meshes. It measures
triangle quality, visualizes bad triangles, applies targeted cleanup operations,
and reports the shape-vs-quality trade-off observed during remeshing.

## Quick Start

Create/activate a Python environment and install optional visualization
dependencies:

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Most metric and cleanup commands use only the standard library. The viewer
scripts need `numpy` and `polyscope`; report figure rendering also needs
`matplotlib` and `Pillow`.

Run the command-line tool:

```bash
venv/bin/python run_meshfix.py --help
```

Equivalent module form:

```bash
venv/bin/python -m meshfix.cli --help
```

Build the C++ port:

```bash
cd cpp
make clean && make
cd ..
```

Run the C++ executable:

```bash
cpp/build/meshfix_cpp analyze \
  inputs/joint_input.off \
  outputs/meshes/joint_adaptive_final.off
```

## Core Commands

Analyze input and output meshes:

```bash
venv/bin/python run_meshfix.py analyze \
  inputs/joint_input.off \
  inputs/joint_output.off \
  inputs/cars \
  --csv outputs/metrics/reproduced_baseline_metrics.csv
```

Color bad triangles as PLY:

```bash
venv/bin/python run_meshfix.py colorize \
  inputs/joint_input.off \
  --out outputs/figures/joint_input_quality.ply
```

Topology check:

```bash
venv/bin/python run_meshfix.py topology \
  outputs/meshes/joint_adaptive_final.off \
  outputs/meshes/joint_input_direct_adaptive_cleanup_i8.off \
  outputs/meshes/car3_targeted_cleanup.off
```

Equivalent C++ metric/topology commands:

```bash
cpp/build/meshfix_cpp analyze \
  inputs/joint_input.off \
  outputs/meshes/joint_adaptive_final.off \
  outputs/meshes/car3_targeted_cleanup.off \
  --csv outputs/cpp/cpp_smoke_metrics.csv

cpp/build/meshfix_cpp topology \
  outputs/meshes/joint_adaptive_final.off \
  outputs/meshes/car3_targeted_cleanup.off
```

C++ targeted cleanup example:

```bash
cpp/build/meshfix_cpp cleanup-degenerate \
  inputs/cars/car3.off \
  --out outputs/cpp/car3_cpp_cleanup.off \
  --iterations 10
```

The C++ cleanup is an independent port of the same targeted rule set. It is
deterministic and dependency-free; because it is a separate implementation, the
exact final mesh can differ slightly from the Python output while preserving the
same measurement logic and cleanup behavior.

## Reproduce Main Joint Experiments

Uniform-based pipeline:

```bash
venv/bin/python run_meshfix.py remesh-uniform \
  inputs/joint_input.off \
  --target-length 0.045 \
  --iterations 8 \
  --out outputs/meshes/joint_uniform_safe.off

venv/bin/python run_meshfix.py cleanup-degenerate \
  outputs/meshes/joint_uniform_safe.off \
  --iterations 10 \
  --out outputs/meshes/joint_cleanup_targeted_i10.off

venv/bin/python run_meshfix.py remesh-adaptive \
  outputs/meshes/joint_cleanup_targeted_i10.off \
  --epsilon 0.002 \
  --min-length 0.025 \
  --max-length 0.075 \
  --iterations 5 \
  --out outputs/meshes/joint_cleanup_adaptive.off

venv/bin/python run_meshfix.py cleanup-degenerate \
  outputs/meshes/joint_cleanup_adaptive.off \
  --iterations 5 \
  --out outputs/meshes/joint_adaptive_final.off
```

No-uniform follow-up experiment:

```bash
venv/bin/python run_meshfix.py remesh-adaptive \
  inputs/joint_input.off \
  --epsilon 0.002 \
  --min-length 0.025 \
  --max-length 0.075 \
  --iterations 5 \
  --out outputs/meshes/joint_input_direct_adaptive.off

venv/bin/python run_meshfix.py cleanup-degenerate \
  outputs/meshes/joint_input_direct_adaptive.off \
  --iterations 8 \
  --out outputs/meshes/joint_input_direct_adaptive_cleanup_i8.off
```

The uniform-based result reaches zero bad triangles but deforms the joint shape
more visibly. The no-uniform candidate preserves shape better but leaves 16 bad
triangles under the current thresholds.

## Reproduce Car Cleanup

```bash
venv/bin/python run_meshfix.py cleanup-degenerate \
  inputs/cars/car1.off \
  --iterations 10 \
  --out outputs/meshes/car1_targeted_cleanup.off

venv/bin/python run_meshfix.py cleanup-degenerate \
  inputs/cars/car2.off \
  --iterations 10 \
  --out outputs/meshes/car2_targeted_cleanup.off

venv/bin/python run_meshfix.py cleanup-degenerate \
  inputs/cars/car3.off \
  --iterations 10 \
  --out outputs/meshes/car3_targeted_cleanup.off

venv/bin/python run_meshfix.py cleanup-degenerate \
  inputs/cars/car4.off \
  --iterations 10 \
  --out outputs/meshes/car4_targeted_cleanup.off
```

Collect metrics:

```bash
venv/bin/python run_meshfix.py analyze \
  inputs/cars/car1.off inputs/cars/car2.off inputs/cars/car3.off inputs/cars/car4.off \
  outputs/meshes/car1_targeted_cleanup.off \
  outputs/meshes/car2_targeted_cleanup.off \
  outputs/meshes/car3_targeted_cleanup.off \
  outputs/meshes/car4_targeted_cleanup.off \
  --csv outputs/metrics/car_targeted_cleanup_metrics.csv
```

## Visualization

View car input/cleanup quality side by side:

```bash
venv/bin/python scripts/view_quality_compare.py --all
```

View joint input, instructor reference, uniform-based final, and no-uniform
candidate:

```bash
venv/bin/python scripts/view_joint_no_uniform.py --mode quality
venv/bin/python scripts/view_joint_no_uniform.py --mode wireframe
```

Generate and view the car3 local diagnostic:

```bash
venv/bin/python scripts/car3_diagnostic.py --out-dir outputs/car3_diagnostic_v3
venv/bin/python scripts/view_car3_diagnostic.py --out-dir outputs/car3_diagnostic_v3 --all
```

Render report PNGs from car3 diagnostic PLY patches:

```bash
python3 scripts/render_car3_diagnostic_figures.py --out-dir outputs/car3_diagnostic_v3
```

## Report

The report source is in `report/report.tex`. It was compiled with Tectonic:

```bash
cd report
tectonic report.tex
```

The compiled PDF is available as:

```text
report/report.pdf
```

## Directory Map

```text
meshfix/          Python implementation
cpp/              C++17 core port and native executable source
scripts/          Diagnostic and visualization helpers
inputs/           Provided OFF meshes
outputs/          Selected meshes, metrics, and diagnostic outputs
report/           LaTeX report and figures
```
