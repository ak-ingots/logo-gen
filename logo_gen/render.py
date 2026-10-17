"""
Ingot stack logo: honest 3D -> 2.5D projection with a camera in polar coordinates.

  logo-gen                               # default parameters
  logo-gen --az 35 --el 30 --r 900       # azimuth, elevation (degrees), distance
  logo-gen --r 0                         # r=0 -> orthographic, no perspective
  logo-gen --png 64 128 256 512 1024     # PNG sizes

Coordinates: y is up, +z is "front" (towards the viewer at az=0), +x is right.
az: camera rotation around the vertical axis, 0 = front, + = moving to the right.
el: angle above the horizon, 0 = side view, 90 = straight from above.
r : distance to the stack centre in model units. Smaller -> stronger perspective.

The stack is an arbitrary list of levels (bottom to top), each level is an arbitrary
list of ingots. Ingots of a level lie side by side (touching with their larger faces),
the level is centred on the world vertical axis and may be rotated around it as a whole.
"""

import argparse
import math
import logging
import typing as t

from dataclasses import dataclass, field
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen

LENGTH = 140
WIDTH = 66
HEIGHT = 46
INSET_LENGTH = 12
INSET_WIDTH = 9

GAP = 2
OUTLINE = 4

CAMERA_AZ = 38
CAMERA_EL = 28
CAMERA_R = 750

SIZE = 256
PAD = 8

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

Vec = tuple[float, float, float]
Quad = list[Vec]
Point = tuple[float, float]
Contour = list[Point]


@dataclass(slots=True)
class Colours:
    dark: str
    medium: str
    light: str
    contour: str
    highlight: str


@dataclass(slots=True)
class Ingot:
    colours: Colours
    text: t.Optional[str] = None
    length: int = LENGTH
    width: int = WIDTH
    height: int = HEIGHT
    inset_length: int = INSET_LENGTH
    inset_width: int = INSET_WIDTH


@dataclass(slots=True)
class Level:
    ingots: list[Ingot]
    rotation: int = 0


@dataclass(slots=True)
class Camera:
    az: int
    el: int
    r: int


C_GOLD = Colours("#D58A0A", "#F4B21B", "#FFDB4D", "#6E3F02", "#FFF4B8")
C_SILVER = Colours("#9EA6B2", "#C8CED7", "#F3F5F8", "#434A55", "#FFFFFF")
C_COPPER = Colours("#B0522A", "#D9743F", "#F7A97E", "#55210D", "#FFD9C2")
C_IRON = Colours("#555B64", "#737A83", "#A3A9B1", "#1C1F24", "#D3D7DC")
C_BRONZE = Colours("#946428", "#BB873B", "#E6B86E", "#422A0A", "#F8E0B0")
C_TITANIUM = Colours("#6A7CA2", "#8D9FC3", "#BCCAE3", "#273149", "#E6EEFB")

LIGHT = (0.30, 0.85, 0.45)


@dataclass(slots=True)
class CliArgs:
    camera_az: int
    camera_el: int
    camera_r: int
    file_out: Path
    png_sizes: list[int]
    preset: str


# ----------------------------------------------------------------- vectors
def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a: Vec, k: float) -> Vec:
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec, b: Vec) -> Vec:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(a: Vec) -> Vec:
    return mul(a, 1 / math.sqrt(dot(a, a)))


def avg(ps: t.Sequence[Vec]) -> Vec:
    sx, sy, sz = (sum(p[i] for p in ps) for i in range(3))
    return mul((sx, sy, sz), 1 / len(ps))


def lerp3(a: Vec, b: Vec, k: float) -> Vec:
    return add(a, mul(sub(b, a), k))


def rot_y(p: Vec, deg: float) -> Vec:
    """Rotation around the world vertical axis. +90 turns +x into -z."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c)


# ----------------------------------------------------------------- colours
def hexrgb(h: str) -> tuple[int, ...]:
    return tuple(int(h[i : i + 2], 16) for i in (1, 3, 5))


def rgbhex(c: t.Sequence[float]) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in c)


def mix(c1: str, c2: str, k: float) -> str:
    a, b = hexrgb(c1), hexrgb(c2)
    return rgbhex([a[i] + (b[i] - a[i]) * k for i in range(3)])


def shade(colours: Colours, n: Vec) -> str:
    lum = 0.35 + 0.65 * max(0.0, dot(n, norm(LIGHT)))
    stops = [
        (0.35, colours.dark),
        (0.74, colours.medium),
        (0.92, colours.light),
        (1.0, colours.highlight),
    ]
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if lum <= b:
            return mix(ca, cb, (lum - a) / (b - a))
    return colours.highlight


# ----------------------------------------------------------------- projection
class Projector:
    """Camera in polar coordinates around `target`, projects world points to 2D."""

    def __init__(self, camera: Camera, target: Vec):
        a, e = math.radians(camera.az), math.radians(camera.el)
        self.ortho = camera.r <= 0
        self.dist = camera.r if camera.r > 0 else 10000
        self.pos = add(
            target,
            (
                self.dist * math.cos(e) * math.sin(a),
                self.dist * math.sin(e),
                self.dist * math.cos(e) * math.cos(a),
            ),
        )
        self.f = norm(sub(target, self.pos))
        upw = (0, 1, 0) if abs(camera.el) < 89.9 else (0, 0, -1)
        self.r = norm(cross(self.f, upw))
        self.u = cross(self.r, self.f)

    def proj(self, p: Vec) -> tuple[float, float]:
        d = sub(p, self.pos)
        x, y, z = dot(d, self.r), dot(d, self.u), dot(d, self.f)
        k = 1 if self.ortho else self.dist / z
        return x * k, -y * k

    def depth(self, p: Vec) -> float:
        return dot(sub(p, self.pos), self.f)

    def sees(self, center: Vec, n: Vec) -> bool:
        return dot(n, sub(self.pos, center)) > 0


# ----------------------------------------------------------------- geometry
def face_normal(q: Quad) -> Vec:
    return norm(cross(sub(q[1], q[0]), sub(q[3], q[0])))


@dataclass(slots=True)
class PlacedIngot:
    """An ingot put into the world: its faces are already rotated and translated."""

    ingot: Ingot
    level: int
    rotation: float
    center: Vec
    offset: float  # position along the level transverse axis
    faces: dict[str, Quad]
    on_top: bool = False  # belongs to the topmost level
    visible: list[str] = field(default_factory=list)

    @property
    def length_axis(self) -> Vec:
        return rot_y((1, 0, 0), self.rotation)

    @property
    def transverse_axis(self) -> Vec:
        return rot_y((0, 0, 1), self.rotation)


def ingot_faces(
    ingot: Ingot, offset: float, y0: float, rotation: float
) -> dict[str, Quad]:
    """
    Truncated pyramid. In local coordinates the ingot lies along x at z=offset,
    then the whole thing is rotated around the world vertical axis.
    Returns {face_name: [4 points]} counter-clockwise when looked at from outside.
    Face names are local: front(+z) back(-z) right(+x) left(-x) top bottom.
    """
    lx, lz, ix, iz = ingot.length, ingot.width, ingot.inset_length, ingot.inset_width
    x0, x1, z0, z1 = -lx / 2, lx / 2, offset - lz / 2, offset + lz / 2
    y1 = y0 + ingot.height
    b = {"lf": (x0, y0, z1), "rf": (x1, y0, z1), "rb": (x1, y0, z0), "lb": (x0, y0, z0)}
    tp = {
        "lf": (x0 + ix, y1, z1 - iz),
        "rf": (x1 - ix, y1, z1 - iz),
        "rb": (x1 - ix, y1, z0 + iz),
        "lb": (x0 + ix, y1, z0 + iz),
    }
    faces = {
        "front": [b["lf"], b["rf"], tp["rf"], tp["lf"]],
        "right": [b["rf"], b["rb"], tp["rb"], tp["rf"]],
        "back": [b["rb"], b["lb"], tp["lb"], tp["rb"]],
        "left": [b["lb"], b["lf"], tp["lf"], tp["lb"]],
        "top": [tp["lf"], tp["rf"], tp["rb"], tp["lb"]],
        "bottom": [b["lb"], b["rb"], b["rf"], b["lf"]],
    }
    return {k: [rot_y(p, rotation) for p in q] for k, q in faces.items()}


def layout(stack: list[Level]) -> list[PlacedIngot]:
    """
    Levels are stacked without gravity:
    each one starts at the top of the tallest ingot below.
    """
    placed = []
    y0 = 0.0
    for lvl, level in enumerate(stack):
        if not level.ingots:
            continue
        total = sum(i.width for i in level.ingots) + GAP * (len(level.ingots) - 1)
        z = -total / 2
        for ingot in level.ingots:
            offset = z + ingot.width / 2
            z += ingot.width + GAP
            placed.append(
                PlacedIngot(
                    ingot=ingot,
                    level=lvl,
                    rotation=level.rotation,
                    offset=offset,
                    center=rot_y((0, y0 + ingot.height / 2, offset), level.rotation),
                    faces=ingot_faces(ingot, offset, y0, level.rotation),
                    on_top=lvl == len(stack) - 1,
                )
            )
        y0 += max(i.height for i in level.ingots)
    return placed


def text_axes(name: str, q: Quad, o: PlacedIngot, cam: Projector) -> tuple[Vec, Vec]:
    """(u, v): text line direction and letters' "up" on the face, readable outside."""
    if name == "top":
        u = o.length_axis
        if dot(u, cam.r) < 0:  # read left to right from the camera
            u = mul(u, -1)
        return u, cross((0, 1, 0), u)
    n = face_normal(q)
    u = norm(cross(mul(n, -1), (0, 1, 0)))  # "right" for the one looking at the face
    v = norm(sub(avg([q[2], q[3]]), avg([q[0], q[1]])))  # up along the face slope
    return u, v


def label_faces(o: PlacedIngot, cam: Projector) -> list[str]:
    """Text goes on the long side facing the camera; on the top level also on top."""
    sides = sorted(
        ("front", "back"),
        key=lambda k: -dot(face_normal(o.faces[k]), sub(cam.pos, avg(o.faces[k]))),
    )
    return [sides[0], "top"] if o.on_top else [sides[0]]


# ----------------------------------------------------------------- font
_font = TTFont(FONT)
_gs, _cmap = _font.getGlyphSet(), _font.getBestCmap()


class FlatPen(BasePen):  # type: ignore[misc]  # fontTools is untyped
    """Flattens glyph outlines into polylines."""

    def __init__(self, gs: t.Any, steps: int = 6) -> None:
        super().__init__(gs)
        self.contours: list[Contour] = []
        self.cur: Contour = []
        self.dx, self.steps = 0.0, steps

    def _moveTo(self, p: Point) -> None:
        self.cur = [(p[0] + self.dx, p[1])]

    def _lineTo(self, p: Point) -> None:
        self.cur.append((p[0] + self.dx, p[1]))

    def _qCurveToOne(self, p1: Point, p2: Point) -> None:
        p0 = self._getCurrentPoint()
        for i in range(1, self.steps + 1):
            k = i / self.steps
            m = 1 - k
            self.cur.append(
                (
                    m * m * p0[0] + 2 * m * k * p1[0] + k * k * p2[0] + self.dx,
                    m * m * p0[1] + 2 * m * k * p1[1] + k * k * p2[1],
                )
            )

    def _curveToOne(self, p1: Point, p2: Point, p3: Point) -> None:
        p0 = self._getCurrentPoint()
        for i in range(1, self.steps + 1):
            k = i / self.steps
            m = 1 - k
            x, y = (
                m**3 * p0[j]
                + 3 * m * m * k * p1[j]
                + 3 * m * k * k * p2[j]
                + k**3 * p3[j]
                + (self.dx if j == 0 else 0)
                for j in (0, 1)
            )
            self.cur.append((x, y))

    def _closePath(self) -> None:
        if self.cur:
            self.contours.append(self.cur)
        self.cur = []

    _endPath = _closePath


def label_outline(text: str) -> tuple[list[Contour], tuple[float, ...]]:
    pen = FlatPen(_gs)
    for ch in text:
        g = _gs[_cmap[ord(ch)]]
        g.draw(pen)
        pen.dx += g.width
    xs = [p[0] for c in pen.contours for p in c]
    ys = [p[1] for c in pen.contours for p in c]
    return pen.contours, (min(xs), min(ys), max(xs), max(ys))


def label_3d(text: str, q: Quad, u: Vec, v: Vec, scale: float = 1.0) -> list[list[Vec]]:
    """Text outlines in 3D, fitted into face q with margins."""
    contours, (x0, y0, x1, y1) = label_outline(text)
    flen = (math.dist(q[0], q[1]) + math.dist(q[2], q[3])) / 2
    fhgt = math.dist(avg([q[0], q[1]]), avg([q[2], q[3]]))
    if abs(dot(u, sub(q[1], q[0]))) < abs(
        dot(u, sub(q[3], q[0]))
    ):  # the line goes across the winding
        flen, fhgt = fhgt, (math.dist(q[1], q[2]) + math.dist(q[3], q[0])) / 2
    k = min(flen * 0.78 / (x1 - x0), fhgt * 0.62 / (y1 - y0)) * scale
    c = add(avg(q), mul(face_normal(q), 0.01))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return [
        [add(c, add(mul(u, (gx - cx) * k), mul(v, (gy - cy) * k))) for gx, gy in cnt]
        for cnt in contours
    ]


# ----------------------------------------------------------------- shadow
def convex_hull(ps: list[tuple[float, float]]) -> list[tuple[float, float]]:
    ps = sorted(set(ps))
    if len(ps) < 3:
        return ps

    def half(seq: t.Iterable[Point]) -> list[Point]:
        h: list[Point] = []
        for p in seq:
            while (
                len(h) >= 2
                and (h[-1][0] - h[-2][0]) * (p[1] - h[-2][1])
                - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0])
                <= 0
            ):
                h.pop()
            h.append(p)
        return h[:-1]

    return half(ps) + half(reversed(ps))


def floor_shadow(
    placed: list[PlacedIngot], margin: float = 8, shift: tuple[float, float] = (4, 2)
) -> Quad:
    """Footprint of the whole stack on the floor, inflated and shifted off the light."""
    hull = convex_hull([(p[0], p[2]) for o in placed for p in o.faces["bottom"]])
    cx, cz = sum(p[0] for p in hull) / len(hull), sum(p[1] for p in hull) / len(hull)
    out = []
    for x, z in hull:
        d = math.hypot(x - cx, z - cz) or 1
        out.append(
            (
                x + (x - cx) / d * margin + shift[0],
                0.0,
                z + (z - cz) / d * margin + shift[1],
            )
        )
    return out


# ----------------------------------------------------------------- render
def render_svg(camera: Camera, stack: list[Level], size: int = SIZE) -> str:
    placed = layout(stack)
    top_y = max(o.faces["top"][0][1] for o in placed)
    cam = Projector(camera, (0, top_y * 0.45, 0))
    shadow = floor_shadow(placed)

    # drawing order: levels from the far one (relative to the camera's height),
    # then inside a level the ingots farthest from the camera along the transverse
    # axis go first.
    def order(o: PlacedIngot) -> tuple[int, float, float]:
        cam_t = dot(cam.pos, o.transverse_axis)
        return (
            (o.level if camera.el >= 0 else -o.level),
            -abs(cam_t - o.offset),
            -cam.depth(o.center),
        )

    placed.sort(key=order)

    pts2d = [cam.proj(p) for p in shadow]
    for o in placed:
        o.visible = [k for k, q in o.faces.items() if cam.sees(avg(q), face_normal(q))]
        for k in o.visible:
            pts2d += [cam.proj(p) for p in o.faces[k]]

    minx, maxx = min(p[0] for p in pts2d), max(p[0] for p in pts2d)
    miny, maxy = min(p[1] for p in pts2d), max(p[1] for p in pts2d)
    pad = PAD * size / 256
    s = (size - 2 * pad) / max(maxx - minx, maxy - miny)
    ox = pad + ((size - 2 * pad) - (maxx - minx) * s) / 2 - minx * s
    oy = pad + ((size - 2 * pad) - (maxy - miny) * s) / 2 - miny * s
    sc = size / 256

    def pt(p: Vec) -> str:
        x, y = cam.proj(p)
        return f"{x*s+ox:.2f},{y*s+oy:.2f}"

    def poly(q: Quad) -> str:
        return " ".join(pt(p) for p in q)

    def path(contours: list[list[Vec]]) -> str:
        return " ".join("M" + " L".join(pt(p) for p in c) + "Z" for c in contours)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size}" height="{size}">',
        f"<title>Ingot stack (az={camera.az}, el={camera.el}, r={camera.r})</title>",
        f'<polygon points="{poly(shadow)}" fill="#000" opacity=".13" '
        f'stroke="#000" stroke-opacity=".05" '
        f'stroke-width="{8*sc:.1f}" stroke-linejoin="round"/>',
    ]

    for o in placed:
        col = o.ingot.colours
        out.append(f'<g class="ingot level-{o.level}">')
        # 1) outline: visible faces with a thick stroke
        for k in o.visible:
            out.append(
                f'<polygon points="{poly(o.faces[k])}" fill="{col.contour}" '
                f'stroke="{col.contour}" stroke-width="{OUTLINE*sc:.2f}" '
                'stroke-linejoin="round"/>'
            )
        # 2) faces filled according to the light
        for k in o.visible:
            q = o.faces[k]
            fill = shade(col, face_normal(q))
            out.append(
                f'<polygon points="{poly(q)}" fill="{fill}" stroke="{fill}" '
                f'stroke-width=".4" stroke-linejoin="round"/>'
            )
            # highlights on the top face, along the ingot length
            if k == "top":
                p0, p1, p2, p3 = q  # lf rf rb lb
                for s0, s1, op in ((0.05, 0.14, 0.75), (0.18, 0.21, 0.5)):
                    strip = [
                        lerp3(p0, p1, s0 + 0.02),
                        lerp3(p0, p1, s1 + 0.02),
                        lerp3(p3, p2, s1 - 0.03),
                        lerp3(p3, p2, s0 - 0.03),
                    ]
                    out.append(
                        f'<polygon points="{poly(strip)}" fill="{col.highlight}" '
                        f'opacity="{op}"/>'
                    )
        # 3) thin inner edges
        for k in o.visible:
            out.append(
                f'<polygon points="{poly(o.faces[k])}" fill="none" '
                f'stroke="{col.contour}" stroke-width="{1.4*sc:.2f}" '
                'stroke-linejoin="round" opacity=".45"/>'
            )
        # 4) embossed labels
        if o.ingot.text:
            for k in label_faces(o, cam):
                if k not in o.visible:
                    continue
                q = o.faces[k]
                u, v = text_axes(k, q, o, cam)
                d = path(label_3d(o.ingot.text, q, u, v, 0.85 if k == "top" else 1.0))
                base = shade(col, face_normal(q))
                out += [
                    f'<path d="{d}" transform="translate({0.8*sc:.2f},{1.2*sc:.2f})" '
                    f'fill="{col.highlight}" opacity=".85"/>',
                    f'<path d="{d}" transform="translate({-0.6*sc:.2f},{-0.9*sc:.2f})" '
                    f'fill="{col.contour}" opacity=".7"/>',
                    f'<path d="{d}" fill="{mix(base, col.contour, .38)}"/>',
                ]
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out)


def parse_cli_args() -> CliArgs:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--az",
        dest="camera_az",
        type=int,
        default=CAMERA_AZ,
        help=f"Azimuth in degrees, 0 is the front. {CAMERA_AZ} by default.",
    )
    ap.add_argument(
        "--el",
        dest="camera_el",
        type=int,
        default=CAMERA_EL,
        help=f"Elevation above the horizon in degrees. {CAMERA_EL} by default.",
    )
    ap.add_argument(
        "--r",
        dest="camera_r",
        type=int,
        default=CAMERA_R,
        help=f"Camera distance, 0 is orthographic. {CAMERA_R} by default.",
    )
    ap.add_argument(
        "--out",
        dest="file_out",
        type=Path,
        default=Path("logo3d"),
        help="Output file name without an extension, -<preset> is appended.",
    )
    ap.add_argument(
        "--png",
        dest="png_sizes",
        nargs="*",
        type=int,
        default=[],
        help="PNG sizes in pixels, none by default.",
    )
    ap.add_argument(
        "--preset",
        choices=PRESETS,
        default=PRESET,
        help=f"Scene preset. {PRESET} by default.",
    )
    ns = ap.parse_args()
    logging.debug("cli args: %s.", ns)
    return CliArgs(**vars(ns))


def build_stack() -> list[Level]:
    I11 = Ingot(colours=C_BRONZE)
    I12 = Ingot(colours=C_GOLD, text="core")

    I21 = Ingot(colours=C_TITANIUM)
    I22 = Ingot(colours=C_IRON, text="sql")

    I31 = Ingot(colours=C_COPPER, text="grpc")
    I32 = Ingot(colours=C_SILVER, text="auth")

    stack = [
        Level(ingots=[I11, I12]),
        Level(ingots=[I21, I22], rotation=90),
        Level(ingots=[I31, I32], rotation=180),
    ]
    return stack


def build_pyramid() -> list[Level]:
    # labels go on the front (last) ingot of each level: the others are hidden
    I11 = Ingot(colours=C_BRONZE)
    I12 = Ingot(colours=C_TITANIUM)
    I13 = Ingot(colours=C_GOLD, text="core")

    I21 = Ingot(colours=C_IRON)
    I22 = Ingot(colours=C_COPPER, text="grpc")

    I31 = Ingot(colours=C_SILVER, text="auth")

    stack = [
        Level(ingots=[I11, I12, I13]),
        Level(ingots=[I21, I22]),
        Level(ingots=[I31]),
    ]
    return stack


PRESETS: dict[str, t.Callable[[], list[Level]]] = {
    "stack": build_stack,
    "pyramid": build_pyramid,
}
PRESET = "stack"


def main(args: CliArgs) -> None:
    camera = Camera(args.camera_az, args.camera_el, args.camera_r)
    stack = PRESETS[args.preset]()
    base = f"{args.file_out}-{args.preset}"

    svg = render_svg(camera=camera, stack=stack)
    Path(f"{base}.svg").write_text(svg)
    logging.info("%s.svg  az=%s el=%s r=%s", base, camera.az, camera.el, camera.r)

    if not args.png_sizes:
        return

    import cairosvg  # needs the cairo system library, only for PNGs

    for px in filter(None, args.png_sizes):
        cairosvg.svg2png(
            bytestring=render_svg(camera=camera, stack=stack, size=px).encode(),
            write_to=f"{base}@{px}.png",
        )
        logging.info("%s@%s.png", base, px)


def cli() -> None:
    logging.basicConfig(level=logging.INFO)
    main(args=parse_cli_args())


if __name__ == "__main__":
    cli()
