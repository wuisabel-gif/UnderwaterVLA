import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image
from image_source import make_image_source, ScreenSource, encode_image


class ImageSourceTests(unittest.TestCase):
    def test_screen_spec(self):
        self.assertIsInstance(make_image_source("screen"), ScreenSource)
        self.assertIsInstance(make_image_source(""), ScreenSource)

    def test_bad_spec(self):
        with self.assertRaises(ValueError):
            make_image_source("nonsense")

    def test_encode_image_roundtrip(self):
        img = Image.new("RGB", (8, 4), (10, 20, 30))
        with tempfile.TemporaryDirectory() as d:
            b64, filename = encode_image(img, save_dir=d)
            self.assertTrue(os.path.exists(filename))
            self.assertTrue(len(b64) > 0)
            self.assertEqual(Image.open(filename).size, (8, 4))


if __name__ == "__main__":
    unittest.main()
