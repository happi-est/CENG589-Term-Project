# Car3 Diagnostic Notes

This diagnostic tracks local bad-triangle regions through targeted cleanup.
Face IDs are not stable after split/collapse operations, so each case is tracked by the original bad triangle centroid.

Color legend: gray=good, red=needle, orange=low_aspect, purple=cap, black=zero_area, yellow=tracked local face.

## Global Progress

| step | vertices | faces | bad triangles | collapses | splits |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 93450 | 186896 | 23495 | 0 | 0 |
| 1 | 91406 | 182808 | 18500 | 2057 | 13 |
| 2 | 89550 | 179096 | 13749 | 1870 | 14 |
| 3 | 88141 | 176278 | 10331 | 1427 | 18 |
| 4 | 86960 | 173916 | 7269 | 1195 | 14 |
| 5 | 86135 | 172266 | 4900 | 838 | 13 |
| 6 | 85483 | 170962 | 2632 | 660 | 8 |
| 7 | 85098 | 170192 | 1226 | 399 | 14 |
| 8 | 84837 | 169670 | 453 | 278 | 17 |
| 9 | 84720 | 169436 | 195 | 141 | 24 |
| 10 | 84705 | 169406 | 162 | 46 | 31 |

## Selected Regions

### Region 1

- Seed face index: `17936`
- Seed label: `cap`
- Seed min/max angle: `1.084` / `175.841` degrees
- Seed aspect ratio: `0.260974`
- Patch timeline PLY: `regions/region_01_timeline.ply`
- Individual patch PLYs use steps: `0, 1, 3, 6, 10`

### Region 2

- Seed face index: `39860`
- Seed label: `needle`
- Seed min/max angle: `0.575` / `90.000` degrees
- Seed aspect ratio: `0.010027`
- Patch timeline PLY: `regions/region_02_timeline.ply`
- Individual patch PLYs use steps: `0, 1, 3, 6, 10`

### Region 3

- Seed face index: `87192`
- Seed label: `needle`
- Seed min/max angle: `0.795` / `129.028` degrees
- Seed aspect ratio: `0.017855`
- Patch timeline PLY: `regions/region_03_timeline.ply`
- Individual patch PLYs use steps: `0, 1, 3, 6, 10`

### Region 4

- Seed face index: `77475`
- Seed label: `needle`
- Seed min/max angle: `0.852` / `130.817` degrees
- Seed aspect ratio: `0.019643`
- Patch timeline PLY: `regions/region_04_timeline.ply`
- Individual patch PLYs use steps: `0, 1, 3, 6, 10`

