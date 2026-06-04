# CENG589 Term Project Submission Notes

## Recommended files to submit

Submit two artifacts:

1. `report.pdf`
2. `EsadMazi_CENG589_Project.zip`

The PDF should be compiled from:

```text
report/report.tex
report/references.bib
report/figures/*.png
```

The project zip should include:

```text
README.md
SUBMISSION.md
meshfix/
docs/
report/
outputs/meshes/joint_adaptive_final.off
outputs/meshes/car1_cleanup.off
outputs/meshes/car4_cleanup.off
outputs/experiment_summary.csv
outputs/joint_adaptive_final_metrics.csv
outputs/car4_cleanup_metrics.csv
```

## How to compile the report

The report PDF was compiled locally with Tectonic. To recompile:

```bash
cd report
tectonic report.tex
```

If using a traditional LaTeX distribution, use:

Local LaTeX command sequence:

```bash
cd report
pdflatex report.tex
bibtex report
pdflatex report.tex
pdflatex report.tex
```

Alternative: upload the entire `report/` directory to Overleaf and set
`report.tex` as the main file.

## How to reproduce the main results

From the project root:

```bash
python3 -m meshfix.cli analyze \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/joint_input.off" \
  outputs/meshes/joint_adaptive_final.off \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/cars/car1.off" \
  outputs/meshes/car1_cleanup.off \
  "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/CENG589 - DGP/termproject/cars/car4.off" \
  outputs/meshes/car4_cleanup.off
```

Topology check:

```bash
python3 -m meshfix.cli topology \
  outputs/meshes/joint_adaptive_final.off \
  outputs/meshes/car1_cleanup.off \
  outputs/meshes/car4_cleanup.off
```

## Notes

- Some intermediate trial outputs are intentionally not part of the clean
  submission package.
- The report discusses these failed/intermediate attempts as observations, but
  the submitted outputs focus on the final selected results.
