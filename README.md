# logo-gen

![Ingots logo](final-pyramid@256.png)

"Ingot stack" logo generator of the Ingots ecosystem: an honest 3D scene projected
by a camera in polar coordinates, rendered to SVG and a set of PNGs.

The ecosystem logo is `final-pyramid.svg` with `final-pyramid@{128,256,512}.png`;
`make logo` rebuilds it with the camera it was picked with
(`--preset pyramid --az 50 --el 25 --r 750`).

- `logo-gen` (`logo_gen/render.py`) — renders the logo (SVG + PNG).
- `logo-gen-grid` (`logo_gen/grid.py`) — a sheet of camera angle variants for
  picking the view.

## Installation

Python 3.15 and [uv](https://docs.astral.sh/uv/). Linux only, with the cairo
library (`libcairo2`, used by `cairosvg` for PNGs; SVGs render without it)
and the DejaVu Sans Mono Bold font at
`/usr/share/fonts/truetype/dejavu/` (`fonts-dejavu-mono`):

```sh
sudo apt install libcairo2 fonts-dejavu-mono
```

```sh
uv sync              # .venv with the project and the dev tools
```

Commands run through `uv run` (or activate `.venv`).

## Logo: `logo-gen`

```sh
uv run logo-gen                            # logo3d-stack.svg with the default camera
uv run logo-gen --png 64 128 256 512 1024  # + logo3d-stack@64.png ... @1024.png
uv run logo-gen --az 35 --el 30 --r 900    # another view
uv run logo-gen --r 0                      # orthographic projection
uv run logo-gen --out logo --png 512       # logo-stack.svg, logo-stack@512.png
uv run logo-gen --preset pyramid           # logo3d-pyramid.svg
```

| Option   | Default  | Meaning                                                         |
|----------|----------|-----------------------------------------------------------------|
| `--az`   | 38       | azimuth, degrees: 0 — front, + — moving to the right            |
| `--el`   | 28       | angle above the horizon: 0 — side view, 90 — straight from above |
| `--r`    | 750      | distance to the stack; smaller — stronger perspective; 0 — ortho |
| `--out`  | `logo3d` | output file name without an extension; `-<preset>` is appended  |
| `--png`  | —        | space-separated PNG sizes; omitted — no PNGs are made           |
| `--preset` | `stack` | scene preset: `stack` or `pyramid`                            |

## Camera angle grid: `logo-gen-grid`

Each `--az` is a column, each `--el` is a row; the grid doesn't have to be square.

```sh
uv run logo-gen-grid                                      # 15/32/50 × 15/28/45 -> grid-stack.png
uv run logo-gen-grid --az=15 --az=32 --az=50 --el=15 --el=28 --out=grid_3x2.png
                                                          # grid_3x2-stack.png
uv run logo-gen-grid --az 15,32,50 --el 15,28 --r 0       # comma lists, ortho
uv run logo-gen-grid --az 30 --el 10,20,30,40 --cell 384  # 1×4 column, 384px cells
uv run logo-gen-grid --preset pyramid                     # grid-pyramid.png
```

## Scene

Scenes are presets in `logo_gen/render.py`, picked with `--preset`:

- `stack` — `build_stack()`, a 2-2-2 column with levels turned by 0/90/180°;
- `pyramid` — `build_pyramid()`, a 3-2-1 pyramid: `core` at the bottom, `grpc` in the
  middle, `auth` on top.

A new preset is a function returning `list[Level]`, registered in `PRESETS`.
A stack is a list of levels from bottom to top, a level is a list of ingots. Ingots
of a level lie side by side, the level is centred on the vertical axis and may be
rotated as a whole by `rotation` degrees. There is no gravity. An ingot's text goes
on the side face turned towards the camera, and on the top level also on its top face.

```python
# brick column 2-2-2-2
stack = [Level([Ingot(C_GOLD), Ingot(C_SILVER)], rotation=90 * (i % 2)) for i in range(4)]

# pyramid 4-3-2-1
stack = [Level([Ingot(C_BRONZE, text="ab") for _ in range(n)]) for n in (4, 3, 2, 1)]
```

## Development

```sh
make            # list of targets
make check      # lint + test, what `make check` of ingots-libs runs
make lint       # black --check, flake8, mypy --strict
make test       # unittest, incl. the check that the final logo is reproducible
make format     # black
make logo       # rebuild final-pyramid.svg + PNGs
make clean      # caches
```
