import unittest

import fairyfishgui


class TestMove(unittest.TestCase):
    def test_coordinate_moves(self):
        move = fairyfishgui.Move('e2e4,e4e6')
        self.assertEqual(move.from_sq, 'e2')
        self.assertEqual(move.to_sq, 'e4')
        self.assertEqual(move.to_sq2, 'e6')

        move = fairyfishgui.Move('h7h8q')
        self.assertEqual(move.from_sq, 'h7')
        self.assertEqual(move.to_sq, 'h8')
        self.assertEqual(move.to_sq2, None)

        move = fairyfishgui.Move('a10b10+')
        self.assertEqual(move.from_sq, 'a10')
        self.assertEqual(move.to_sq, 'b10')
        self.assertEqual(move.to_sq2, None)

    def test_drop_moves(self):
        move = fairyfishgui.Move('Q@a1')
        self.assertEqual(move.from_sq, 'Q@')
        self.assertEqual(move.to_sq, 'a1')
        self.assertEqual(move.to_sq2, None)

        move = fairyfishgui.Move('R@b10')
        self.assertEqual(move.from_sq, 'R@')
        self.assertEqual(move.to_sq, 'b10')
        self.assertEqual(move.to_sq2, None)

        move = fairyfishgui.Move('+P@a1')
        self.assertEqual(move.from_sq, 'P@')
        self.assertEqual(move.to_sq, 'a1')
        self.assertEqual(move.to_sq2, None)

    def test_move_filtering(self):
        move = fairyfishgui.Move('e7e8q')
        self.assertTrue(move.contains(['e7', 'e8']))
        self.assertTrue(move.contains(['e8', 'e7']))
        self.assertFalse(move.contains(['e7', 'e7']))
        self.assertFalse(move.contains(['e8', 'e8']))

        move = fairyfishgui.Move('+P@a10')
        self.assertTrue(move.contains(['P@', 'a10']))
        self.assertTrue(move.contains(['P@']))
        self.assertFalse(move.contains(['a1']))  # substring

        move = fairyfishgui.Move('e2e4,e4e6')
        self.assertTrue(move.contains(['e2', 'e4', 'e6']))
        self.assertTrue(move.contains(['e4', 'e2', 'e6']))
        self.assertTrue(move.contains(['e2', 'e4', 'e4']))
        self.assertTrue(move.contains(['e4', 'e2', 'e4', 'e6']))
        self.assertFalse(move.contains(['e2', 'e4', 'e2']))
        self.assertFalse(move.contains(['e2', 'e4', 'e4', 'e4']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
