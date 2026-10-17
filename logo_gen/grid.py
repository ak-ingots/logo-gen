"""
Sheet of camera angle variants for picking the view:
every --az combined with every --el.

  logo-gen-grid                                     # 15/32/50 x 15/28/45
  logo-gen-grid --az=15 --az=32 --az=50 --el=15 --el=28 --out=grid_3x2.png
  logo-gen-grid --az 15,32,50 --el 15,28 --r 0      # comma lists work too

Columns are azimuths, rows are elevations.
"""

import argparse
import io
import logging
import typing as t

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from logo_gen.render import CAMERA_R, PRESET, PRESETS, Camera, render_svg

GRID_AZ = [15, 32, 50]
GRID_EL = [15, 28, 45]
CELL = 256
CAPTION = 18


@dataclass(slots=True)
class GridArgs:
    azimuths: list[int]
    elevations: list[int]
    camera_r: int
    cell: int
    file_out: Path
    preset: str


def int_list(value: str) -> list[int]:
    """'15' -> [15]; '15,32,' -> [15, 32]."""
    return [int(v) for v in value.split(",") if v.strip()]


def flatten(groups: t.Optional[list[list[int]]], default: list[int]) -> list[int]:
    return [v for g in groups for v in g] if groups else default


def parse_cli_args() -> GridArgs:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--az",
        dest="azimuths",
        type=int_list,
        action="append",
        help=f"Azimuth in degrees, repeatable. {GRID_AZ} by default.",
    )
    ap.add_argument(
        "--el",
        dest="elevations",
        type=int_list,
        action="append",
        help=f"Elevation in degrees, repeatable. {GRID_EL} by default.",
    )
    ap.add_argument(
        "--r",
        dest="camera_r",
        type=int,
        default=CAMERA_R,
        help=f"Camera distance, 0 is orthographic. {CAMERA_R} by default.",
    )
    ap.add_argument(
        "--cell",
        type=int,
        default=CELL,
        help=f"Cell size in pixels. {CELL} by default.",
    )
    ap.add_argument(
        "--out",
        dest="file_out",
        type=Path,
        default=Path("grid.png"),
        help="Out file name. grid.png by default.",
    )
    ap.add_argument(
        "--preset",
        choices=PRESETS,
        default=PRESET,
        help=f"Scene preset. {PRESET} by default.",
    )
    ns = ap.parse_args()
    logging.debug("cli args: %s.", ns)
    return GridArgs(
        azimuths=flatten(ns.azimuths, GRID_AZ),
        elevations=flatten(ns.elevations, GRID_EL),
        camera_r=ns.camera_r,
        cell=ns.cell,
        file_out=ns.file_out,
        preset=ns.preset,
    )


def render_grid(args: GridArgs) -> Image.Image:
    import cairosvg  # needs the cairo system library

    stack = PRESETS[args.preset]()
    cell, row = args.cell, args.cell + CAPTION
    sheet = Image.new(
        "RGB", (cell * len(args.azimuths), row * len(args.elevations)), "white"
    )
    dr = ImageDraw.Draw(sheet)
    for j, el in enumerate(args.elevations):
        for i, az in enumerate(args.azimuths):
            camera = Camera(az, el, args.camera_r)
            png = cairosvg.svg2png(
                bytestring=render_svg(camera=camera, stack=stack, size=cell).encode()
            )
            im = Image.open(io.BytesIO(png)).convert("RGBA")
            sheet.paste(im, (i * cell, j * row + CAPTION), im)
            dr.text(
                (i * cell + 6, j * row + 3),
                f"az={az} el={el} r={args.camera_r}",
                fill="black",
            )
    return sheet


def main(args: GridArgs) -> None:
    file_out = args.file_out.with_stem(f"{args.file_out.stem}-{args.preset}")
    render_grid(args).save(file_out)
    logging.info(
        "%s  %dx%d  az=%s el=%s r=%s",
        file_out,
        len(args.azimuths),
        len(args.elevations),
        args.azimuths,
        args.elevations,
        args.camera_r,
    )


def cli() -> None:
    logging.basicConfig(level=logging.INFO)
    main(args=parse_cli_args())


if __name__ == "__main__":
    cli()
