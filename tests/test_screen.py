import unittest
from c64u_bridge.screen import screen_code_to_ascii, format_screen


class TestScreen(unittest.TestCase):
    def test_screen_code_to_ascii(self):
        self.assertEqual(screen_code_to_ascii(0), "@")
        self.assertEqual(screen_code_to_ascii(1), "A")
        self.assertEqual(screen_code_to_ascii(26), "Z")
        self.assertEqual(screen_code_to_ascii(32), " ")
        self.assertEqual(screen_code_to_ascii(48), "0")
        self.assertEqual(screen_code_to_ascii(57), "9")
        # Inverted characters
        self.assertEqual(screen_code_to_ascii(129), "A")

    def test_format_screen(self):
        # Construct 1000 bytes with "HELLO" at top left
        screen_data = bytearray(1000)
        screen_data[0:5] = bytes([8, 5, 12, 12, 15])  # H, E, L, L, O in screen codes
        for i in range(5, 1000):
            screen_data[i] = 32  # Space

        output = format_screen(bytes(screen_data))
        lines = output.splitlines()
        self.assertEqual(len(lines), 27)  # 25 rows + 2 border lines
        self.assertEqual(lines[0], "+" + "-" * 40 + "+")
        self.assertTrue(lines[1].startswith("|HELLO"))
        self.assertEqual(lines[-1], "+" + "-" * 40 + "+")


if __name__ == "__main__":
    unittest.main()
