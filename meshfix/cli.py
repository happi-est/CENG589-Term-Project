from __future__ import annotations

import argparse
import csv
from pathlib import Path

from meshfix.io import collect_off_files, read_off, write_off
from meshfix.quality import (
    CSV_HEADER,
    QUALITY_COLORS,
    analyze_mesh,
    classify_mesh_faces,
    count_labels,
    format_summary_table,
)
from meshfix.visualize import write_quality_ply
from meshfix.remesh import adaptive_remesh, format_remesh_stats, uniform_remesh
from meshfix.topology import analyze_topology, format_topology_table
from meshfix.cleanup import cleanup_degenerate, format_cleanup_stats
from meshfix.curvature import format_sizing_stats, sizing_field


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meshfix",
        description="Analyze and improve triangle mesh quality for the CENG589 project.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser(
        "analyze",
        help="Compute baseline quality metrics for OFF meshes.",
    )
    analyze.add_argument("paths", nargs="+", help="OFF files or directories containing OFF files.")
    analyze.add_argument("--csv", type=Path, help="Optional CSV output path.")
    analyze.add_argument("--needle-angle", type=float, default=5.0)
    analyze.add_argument("--cap-angle", type=float, default=175.0)
    analyze.add_argument("--aspect-threshold", type=float, default=0.05)

    colorize = subparsers.add_parser(
        "colorize",
        help="Export PLY files with bad triangles colored by quality label.",
    )
    colorize.add_argument("paths", nargs="+", help="OFF files or directories containing OFF files.")
    colorize.add_argument("--out", type=Path, help="Output PLY path. Only valid for one input file.")
    colorize.add_argument("--out-dir", type=Path, default=Path("outputs/figures"))
    colorize.add_argument("--needle-angle", type=float, default=5.0)
    colorize.add_argument("--cap-angle", type=float, default=175.0)
    colorize.add_argument("--aspect-threshold", type=float, default=0.05)

    view = subparsers.add_parser(
        "view-quality",
        help="Open an OFF mesh in Polyscope and color bad triangles interactively.",
    )
    view.add_argument("path", help="OFF file to inspect.")
    view.add_argument("--needle-angle", type=float, default=5.0)
    view.add_argument("--cap-angle", type=float, default=175.0)
    view.add_argument("--aspect-threshold", type=float, default=0.05)

    topology = subparsers.add_parser(
        "topology",
        help="Report boundary and non-manifold edge counts for OFF meshes.",
    )
    topology.add_argument("paths", nargs="+", help="OFF files or directories containing OFF files.")

    remesh = subparsers.add_parser(
        "remesh-uniform",
        help="Run a simple uniform isotropic remeshing loop.",
    )
    remesh.add_argument("path", help="OFF file to remesh.")
    remesh.add_argument("--out", type=Path, required=True, help="Output OFF path.")
    remesh.add_argument("--target-length", type=float)
    remesh.add_argument("--iterations", type=int, default=5)
    remesh.add_argument("--no-collapse", action="store_true")
    remesh.add_argument("--no-flip", action="store_true")
    remesh.add_argument("--no-smooth", action="store_true")
    remesh.add_argument("--flip", action="store_true")
    remesh.add_argument("--smooth", action="store_true")
    remesh.add_argument("--smooth-amount", type=float, default=0.1)
    remesh.add_argument("--no-project", action="store_true")

    cleanup = subparsers.add_parser(
        "cleanup-degenerate",
        help="Conservatively split edges belonging to bad triangles.",
    )
    cleanup.add_argument("path", help="OFF file to clean.")
    cleanup.add_argument("--out", type=Path, required=True, help="Output OFF path.")
    cleanup.add_argument("--iterations", type=int, default=3)
    cleanup.add_argument("--needle-angle", type=float, default=5.0)
    cleanup.add_argument("--cap-angle", type=float, default=175.0)
    cleanup.add_argument("--aspect-threshold", type=float, default=0.05)

    adaptive = subparsers.add_parser(
        "remesh-adaptive",
        help="Run curvature-adaptive isotropic remeshing.",
    )
    adaptive.add_argument("path", help="OFF file to remesh.")
    adaptive.add_argument("--out", type=Path, required=True, help="Output OFF path.")
    adaptive.add_argument("--epsilon", type=float, default=0.002)
    adaptive.add_argument("--min-length", type=float, default=0.025)
    adaptive.add_argument("--max-length", type=float, default=0.075)
    adaptive.add_argument("--iterations", type=int, default=5)
    return parser


def _run_analyze(args: argparse.Namespace) -> int:
    files = collect_off_files(args.paths)
    summaries = []
    for path in files:
        mesh = read_off(path)
        summaries.append(
            analyze_mesh(
                mesh,
                needle_angle_deg=args.needle_angle,
                cap_angle_deg=args.cap_angle,
                low_aspect_threshold=args.aspect_threshold,
            )
        )

    print(format_summary_table(summaries))

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(CSV_HEADER)
            writer.writerows(summary.as_csv_row() for summary in summaries)
        print(f"\nWrote {args.csv}")

    return 0


def _format_counts(counts: dict[str, int]) -> str:
    order = ["good", "needle", "low_aspect", "cap", "zero_area"]
    return ", ".join(f"{label}={counts.get(label, 0)}" for label in order)


def _run_colorize(args: argparse.Namespace) -> int:
    files = collect_off_files(args.paths)
    if args.out and len(files) != 1:
        raise ValueError("--out can only be used with a single OFF file")

    for path in files:
        mesh = read_off(path)
        out_path = args.out if args.out else args.out_dir / f"{path.stem}_quality.ply"
        counts = write_quality_ply(
            mesh,
            out_path,
            needle_angle_deg=args.needle_angle,
            cap_angle_deg=args.cap_angle,
            low_aspect_threshold=args.aspect_threshold,
        )
        print(f"Wrote {out_path} ({_format_counts(counts)})")
    return 0


def _run_view_quality(args: argparse.Namespace) -> int:
    try:
        import numpy as np
        import polyscope as ps
    except ImportError as exc:
        raise SystemExit(
            "Polyscope viewer needs the course virtualenv. Run this command with:\n"
            "/Users/esadmazi/Documents/Akademi/METU/Yüksek Lisans/25-26 Spring/"
            "CENG589 - DGP/termproject/venv/bin/python -m meshfix.cli view-quality <mesh.off>"
        ) from exc

    mesh = read_off(args.path)
    labels = classify_mesh_faces(
        mesh,
        needle_angle_deg=args.needle_angle,
        cap_angle_deg=args.cap_angle,
        low_aspect_threshold=args.aspect_threshold,
    )
    counts = count_labels(labels)
    label_to_value = {label: index for index, label in enumerate(QUALITY_COLORS)}
    values = np.array([label_to_value[label] for label in labels])
    colors = np.array(
        [[channel / 255.0 for channel in QUALITY_COLORS[label][:3]] for label in labels]
    )

    ps.init()
    ps_mesh = ps.register_surface_mesh(
        mesh.source.name if mesh.source else "mesh",
        np.array(mesh.vertices),
        np.array(mesh.faces),
    )
    ps_mesh.add_color_quantity("quality colors", colors, defined_on="faces", enabled=True)
    ps_mesh.add_scalar_quantity("quality label ids", values, defined_on="faces")
    print(_format_counts(counts))
    print("Legend: gray=good, red=needle, orange=low_aspect, purple=cap, black=zero_area")
    ps.show()
    return 0


def _run_topology(args: argparse.Namespace) -> int:
    files = collect_off_files(args.paths)
    summaries = [analyze_topology(read_off(path)) for path in files]
    print(format_topology_table(summaries))
    return 0


def _run_remesh_uniform(args: argparse.Namespace) -> int:
    mesh = read_off(args.path)
    before = analyze_mesh(mesh)
    result = uniform_remesh(
        mesh,
        target_length=args.target_length,
        iterations=args.iterations,
        do_collapse=not args.no_collapse,
        do_flip=args.flip and not args.no_flip,
        do_smooth=args.smooth and not args.no_smooth,
        smooth_amount=args.smooth_amount,
        project=not args.no_project,
        reference_mesh=mesh,
    )
    write_off(result.mesh, args.out)
    after = analyze_mesh(result.mesh)

    print(f"target_length={result.target_length:.6f}")
    print(format_remesh_stats(result.stats))
    print()
    print(format_summary_table([before, after]))
    print(f"\nWrote {args.out}")
    return 0


def _run_cleanup_degenerate(args: argparse.Namespace) -> int:
    mesh = read_off(args.path)
    before = analyze_mesh(
        mesh,
        needle_angle_deg=args.needle_angle,
        cap_angle_deg=args.cap_angle,
        low_aspect_threshold=args.aspect_threshold,
    )
    result = cleanup_degenerate(
        mesh,
        iterations=args.iterations,
        needle_angle_deg=args.needle_angle,
        cap_angle_deg=args.cap_angle,
        low_aspect_threshold=args.aspect_threshold,
    )
    write_off(result.mesh, args.out)
    after = analyze_mesh(
        result.mesh,
        needle_angle_deg=args.needle_angle,
        cap_angle_deg=args.cap_angle,
        low_aspect_threshold=args.aspect_threshold,
    )

    print(format_cleanup_stats(result.stats))
    print()
    print(format_summary_table([before, after]))
    print(f"\nWrote {args.out}")
    return 0


def _run_remesh_adaptive(args: argparse.Namespace) -> int:
    mesh = read_off(args.path)
    before = analyze_mesh(mesh)
    _, size_stats = sizing_field(
        mesh,
        epsilon=args.epsilon,
        min_length=args.min_length,
        max_length=args.max_length,
    )
    result = adaptive_remesh(
        mesh,
        epsilon=args.epsilon,
        min_length=args.min_length,
        max_length=args.max_length,
        iterations=args.iterations,
    )
    write_off(result.mesh, args.out)
    after = analyze_mesh(result.mesh)

    print(format_sizing_stats(size_stats))
    print(format_remesh_stats(result.stats))
    print()
    print(format_summary_table([before, after]))
    print(f"\nWrote {args.out}")
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "analyze":
        return _run_analyze(args)
    if args.command == "colorize":
        return _run_colorize(args)
    if args.command == "view-quality":
        return _run_view_quality(args)
    if args.command == "topology":
        return _run_topology(args)
    if args.command == "remesh-uniform":
        return _run_remesh_uniform(args)
    if args.command == "cleanup-degenerate":
        return _run_cleanup_degenerate(args)
    if args.command == "remesh-adaptive":
        return _run_remesh_adaptive(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
