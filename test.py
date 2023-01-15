import unittest

import fairyfishgui


class TestMove(unittest.TestCase):
    def test_coordinate_moves(self):
        move = fairyfishgui.Move('e2e4,e4e6')
        self.assertEqual(move.from_sq(), 'e2')
        self.assertEqual(move.to_sq(), 'e4')
        self.assertEqual(move.gating_sq(), 'e6')

        move = fairyfishgui.Move('h7h8q')
        self.assertEqual(move.from_sq(), 'h7')
        self.assertEqual(move.to_sq(), 'h8')
        with self.assertRaises(AssertionError):
            move.gating_sq()

        move = fairyfishgui.Move('a10b10+')
        self.assertEqual(move.from_sq(), 'a10')
        self.assertEqual(move.to_sq(), 'b10')

    def test_drop_moves(self):
        move = fairyfishgui.Move('Q@a1')
        self.assertEqual(move.from_sq(), 'Q@')
        self.assertEqual(move.to_sq(), 'a1')

        move = fairyfishgui.Move('R@b10')
        self.assertEqual(move.from_sq(), 'R@')
        self.assertEqual(move.to_sq(), 'b10')

        move = fairyfishgui.Move('+P@a1')
        self.assertEqual(move.from_sq(), 'P@')
        self.assertEqual(move.to_sq(), 'a1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
