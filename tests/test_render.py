import unittest

from pathlib import Path

from logo_gen.render import (
    HEIGHT,
    Camera,
    Ingot,
    Level,
    Projector,
    C_GOLD,
    build_pyramid,
    build_stack,
    layout,
    render_svg,
)

ROOT = Path(__file__).resolve().parent.parent


class FinalLogoTest(unittest.TestCase):
    def test_final_logo_is_reproducible(self) -> None:
        # the camera of `make logo`
        svg = render_svg(Camera(50, 25, 750), build_pyramid())
        self.assertEqual(svg, (ROOT / "final-pyramid.svg").read_text())


class LayoutTest(unittest.TestCase):
    def test_levels_stack_on_top_of_each_other(self) -> None:
        placed = layout(build_pyramid())
        self.assertEqual([o.level for o in placed], [0, 0, 0, 1, 1, 2])
        bottoms = {o.level: o.faces["bottom"][0][1] for o in placed}
        self.assertEqual(bottoms, {0: 0, 1: HEIGHT, 2: 2 * HEIGHT})

    def test_only_the_top_level_is_on_top(self) -> None:
        placed = layout(build_stack())
        self.assertEqual([o.on_top for o in placed], [False] * 4 + [True] * 2)

    def test_empty_levels_are_skipped(self) -> None:
        placed = layout([Level([]), Level([Ingot(C_GOLD)])])
        self.assertEqual(len(placed), 1)
        self.assertEqual(placed[0].faces["bottom"][0][1], 0)


class ProjectorTest(unittest.TestCase):
    def test_front_camera_sees_front_not_back(self) -> None:
        cam = Projector(Camera(0, 0, 750), (0, 0, 0))
        self.assertTrue(cam.sees((0, 0, 1), (0, 0, 1)))
        self.assertFalse(cam.sees((0, 0, -1), (0, 0, -1)))

    def test_orthographic_ignores_depth(self) -> None:
        cam = Projector(Camera(0, 0, 0), (0, 0, 0))
        self.assertEqual(cam.proj((10, 5, 100)), cam.proj((10, 5, -100)))


class RenderTest(unittest.TestCase):
    def test_svg_size_and_one_group_per_ingot(self) -> None:
        svg = render_svg(Camera(38, 28, 750), build_stack(), size=64)
        self.assertIn('width="64" height="64"', svg)
        self.assertEqual(svg.count('<g class="ingot'), 6)


if __name__ == "__main__":
    unittest.main()
