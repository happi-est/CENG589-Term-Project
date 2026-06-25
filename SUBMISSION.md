# CENG589 Term Project Submission Notes

## Files to Submit

Submit these two top-level artifacts:

```text
submission/report.pdf
submission/EsadMazi_CENG589_Project.zip
```

The zip contains:

```text
README.md
SUBMISSION.md
requirements.txt
run_meshfix.py
meshfix/
cpp/
scripts/
inputs/
outputs/
report/
```

## Python Code and Launcher

The Python source code is under `meshfix/`. The executable-style Python launcher
is:

```text
run_meshfix.py
```

Example:

```bash
venv/bin/python run_meshfix.py analyze \
  inputs/joint_input.off \
  outputs/meshes/joint_adaptive_final.off
```

The same command can also be run as:

```bash
venv/bin/python -m meshfix.cli analyze \
  inputs/joint_input.off \
  outputs/meshes/joint_adaptive_final.off
```

## C++ Port and Native Executable

The C++17 port is under:

```text
cpp/
```

It includes source code, a Makefile, and a compiled macOS executable:

```text
cpp/meshfix_cpp.cpp
cpp/Makefile
cpp/build/meshfix_cpp
```

Build from source:

```bash
cd cpp
make
cd ..
```

Example C++ metric command:

```bash
cpp/build/meshfix_cpp analyze \
  inputs/joint_input.off \
  outputs/meshes/joint_adaptive_final.off
```

Example C++ cleanup command:

```bash
cpp/build/meshfix_cpp cleanup-degenerate \
  inputs/cars/car3.off \
  --out outputs/cpp/car3_cpp_cleanup.off \
  --iterations 10
```

The C++ code ports the core OFF I/O, quality analysis, topology analysis, and
targeted degenerate-triangle cleanup. The Python implementation remains the main
research pipeline because it also includes visualization, adaptive/uniform
experiments, and diagnostic figure generation.

## Dependencies

Install Python dependencies with:

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Notes:

- metric analysis and most cleanup operations are pure Python;
- interactive viewers require `numpy` and `polyscope`;
- report diagnostic PNG rendering requires `matplotlib` and `Pillow`.

## Report Compilation

The report PDF was compiled locally with Tectonic:

```bash
cd report
tectonic report.tex
```

If using a traditional LaTeX distribution:

```bash
cd report
pdflatex report.tex
bibtex report
pdflatex report.tex
pdflatex report.tex
```

## Reproduce Main Metrics

From the package root:

```bash
venv/bin/python run_meshfix.py analyze \
  inputs/joint_input.off \
  inputs/joint_output.off \
  outputs/meshes/joint_adaptive_final.off \
  outputs/meshes/joint_input_direct_adaptive_cleanup_i8.off \
  outputs/meshes/car1_targeted_cleanup.off \
  outputs/meshes/car2_targeted_cleanup.off \
  outputs/meshes/car3_targeted_cleanup.off \
  outputs/meshes/car4_targeted_cleanup.off \
  --csv outputs/metrics/reproduced_summary.csv
```

Topology check:

```bash
venv/bin/python run_meshfix.py topology \
  outputs/meshes/joint_adaptive_final.off \
  outputs/meshes/joint_input_direct_adaptive_cleanup_i8.off \
  outputs/meshes/car1_targeted_cleanup.off \
  outputs/meshes/car2_targeted_cleanup.off \
  outputs/meshes/car3_targeted_cleanup.off \
  outputs/meshes/car4_targeted_cleanup.off
```

## Car3 Diagnostic

Generate the diagnostic:

```bash
venv/bin/python scripts/car3_diagnostic.py --out-dir outputs/car3_diagnostic_v3
```

View the local patch timelines:

```bash
venv/bin/python scripts/view_car3_diagnostic.py --out-dir outputs/car3_diagnostic_v3 --all
```

Render report figures:

```bash
python3 scripts/render_car3_diagnostic_figures.py --out-dir outputs/car3_diagnostic_v3
```

## Current Status

- Python implementation: included.
- Python launcher: included as `run_meshfix.py`.
- C++ port / native executable: included under `cpp/`.
