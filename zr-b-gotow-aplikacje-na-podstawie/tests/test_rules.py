import unittest

from app.formats import FORMATS, allowed_target, conversion_warning, target_options
from app.media import detect_format, safe_original_name
from app.security import constant_time_equal, digest, otp


class FormatRulesTests(unittest.TestCase):
    def test_each_format_has_exactly_two_targets_in_own_category(self):
        for source, definition in FORMATS.items():
            choices = target_options(source)
            self.assertEqual(len(choices), 2)
            self.assertTrue(all(item.category == definition.category for item in choices))
            self.assertNotIn(source, {item.code for item in choices})

    def test_rejects_cross_category_and_same_format(self):
        self.assertFalse(allowed_target("mp3", "mp4"))
        self.assertFalse(allowed_target("png", "png"))
        self.assertTrue(allowed_target("mov", "gif"))

    def test_warns_about_lossy_or_non_restorative_paths(self):
        self.assertIn("stratnym", conversion_warning("flac", "mp3"))
        self.assertIn("nie odzyska", conversion_warning("mp3", "flac"))


class SignatureTests(unittest.TestCase):
    def test_recognizes_supported_signatures(self):
        cases = {
            b"fLaC\x00\x00\x00\x00": "flac",
            b"ID3\x04\x00\x00": "mp3",
            b"RIFF\x00\x00\x00\x00WAVE": "wav",
            b"\xff\xd8\xff\xe0": "jpg",
            b"\x89PNG\r\n\x1a\n": "png",
            b"GIF89a": "gif",
            b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isom": "mp4",
            b"\x00\x00\x00\x18ftypqt  \x00\x00\x00\x00qt  ": "mov",
            b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1": "heic",
        }
        for signature, expected in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(detect_format(signature), expected)

    def test_rejects_unknown_and_sanitizes_download_name(self):
        self.assertIsNone(detect_format(b"not a media file"))
        self.assertEqual(safe_original_name("../raport:2026?.mp4"), "raport_2026_.mp4")


class SecurityTests(unittest.TestCase):
    def test_hashed_values_compare_without_plaintext(self):
        value = otp()
        self.assertRegex(value, r"^\d{6}$")
        self.assertNotEqual(value, digest(value))
        self.assertTrue(constant_time_equal(digest(value), digest(value)))


if __name__ == "__main__":
    unittest.main()
