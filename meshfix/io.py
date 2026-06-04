from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional


@dataclass
class Mesh:
    vertices: list[tuple[float, float, float]]
    faces: list[tuple[int, int, int]]
    source: Optional[Path] = None


def _clean_token_lines(path: Path) -> Iterator[list[str]]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.split("#", 1)[0].strip()
            if line:
                yield line.split()


def read_off(path: str | Path) -> Mesh:
    """Read an OFF mesh and fan-triangulate polygonal faces if needed."""
    path = Path(path)
    lines = _clean_token_lines(path)

    try:
        first = next(lines)
    except StopIteration as exc:
        raise ValueError(f"{path} is empty") from exc

    if first[0] != "OFF":
        raise ValueError(f"{path} is not an OFF file")

    if len(first) >= 4:
        counts = first[1:4]
    else:
        counts = next(lines)

    vertex_count, face_count, _ = (int(value) for value in counts[:3])

    vertices: list[tuple[float, float, float]] = []
    for _ in range(vertex_count):
        parts = next(lines)
        vertices.append((float(parts[0]), float(parts[1]), float(parts[2])))

    faces: list[tuple[int, int, int]] = []
    for _ in range(face_count):
        parts = next(lines)
        degree = int(parts[0])
        indices = [int(value) for value in parts[1 : 1 + degree]]
        if degree < 3:
            continue
        if degree == 3:
            faces.append((indices[0], indices[1], indices[2]))
            continue
        for i in range(1, degree - 1):
            faces.append((indices[0], indices[i], indices[i + 1]))

    return Mesh(vertices=vertices, faces=faces, source=path)


def write_off(mesh: Mesh, path: str | Path) -> None:
    """Write a triangular mesh as OFF."""
    path = Path(path)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("OFF\n")
        handle.write(f"{len(mesh.vertices)} {len(mesh.faces)} 0\n")
        for vertex in mesh.vertices:
            handle.write(f"{vertex[0]:.12g} {vertex[1]:.12g} {vertex[2]:.12g}\n")
        for face in mesh.faces:
            handle.write(f"3 {face[0]} {face[1]} {face[2]}\n")


def collect_off_files(paths: Iterable[str | Path]) -> list[Path]:
    """Collect OFF files from explicit file paths or directories."""
    files: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if path.is_dir():
            files.extend(sorted(path.rglob("*.off")))
        elif path.is_file() and path.suffix.lower() == ".off":
            files.append(path)
        else:
            raise FileNotFoundError(f"No OFF file found at {path}")
    return files

