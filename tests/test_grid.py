import unittest

from logo_gen.grid import flatten, int_list


class GridArgsTest(unittest.TestCase):
    def test_int_list(self) -> None:
        self.assertEqual(int_list("15"), [15])
        self.assertEqual(int_list("15,32,"), [15, 32])

    def test_flatten_repeated_options(self) -> None:
        self.assertEqual(flatten([[15], [32, 50]], [1]), [15, 32, 50])
        self.assertEqual(flatten(None, [1, 2]), [1, 2])


if __name__ == "__main__":
    unittest.main()
