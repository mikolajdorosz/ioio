import unittest
from pathlib import Path

from app.formats import FORMATS, allowed_target, conversion_warning, target_options
from app.media import detect_format, ffmpeg_command, pcm_codec, safe_original_name
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
        self.assertIsNone(detect_format(b"%PDF-1.7"))
        self.assertIsNone(detect_format(b""))
        self.assertEqual(safe_original_name("../raport:2026?.mp4"), "raport_2026_.mp4")
        self.assertEqual(safe_original_name(None), "plik")

    def test_jpeg_is_not_mistaken_for_raw_mp3_frame(self):
        # JPEG zaczyna się od FF D8, a ramka MP3 od FF Ex/FF Fx.
        self.assertEqual(detect_format(b"\xff\xd8\xff\xdb"), "jpg")
        self.assertEqual(detect_format(b"\xff\xfb\x90\x64"), "mp3")


class FfmpegProfileTests(unittest.TestCase):
    source = Path("in.bin")
    destination = Path("out.bin")

    def command(self, source_format: str, target: str, bit_depth=None) -> list[str]:
        return ffmpeg_command(self.source, self.destination, source_format, target, bit_depth)

    def test_only_local_protocols_and_no_stdin(self):
        command = self.command("mp4", "gif")
        self.assertIn("-nostdin", command)
        self.assertEqual(command[command.index("-protocol_whitelist") + 1], "file,pipe")
        self.assertEqual(command[-1], str(self.destination))

    def test_audio_profiles(self):
        self.assertIn("flac", self.command("wav", "flac"))
        mp3 = self.command("flac", "mp3")
        self.assertEqual(mp3[mp3.index("-b:a") + 1], "320k")
        self.assertIn("libmp3lame", mp3)

    def test_wav_keeps_source_bit_depth(self):
        self.assertEqual(pcm_codec(None), "pcm_s16le")
        self.assertEqual(pcm_codec(16), "pcm_s16le")
        self.assertEqual(pcm_codec(24), "pcm_s24le")
        self.assertEqual(pcm_codec(32), "pcm_s32le")
        self.assertIn("pcm_s24le", self.command("flac", "wav", 24))

    def test_video_profiles(self):
        gif = self.command("mp4", "gif")
        self.assertIn("-an", gif)
        self.assertIn("palettegen=stats_mode=full", " ".join(gif))

        mp4 = self.command("gif", "mp4")
        self.assertIn("libx264", mp4)
        self.assertEqual(mp4[mp4.index("-crf") + 1], "18")
        self.assertEqual(mp4[mp4.index("-b:a") + 1], "256k")
        self.assertEqual(mp4[mp4.index("-pix_fmt") + 1], "yuv420p")
        self.assertIn("scale=trunc(iw/2)*2:trunc(ih/2)*2", mp4)

        remux = self.command("mp4", "mov")
        self.assertEqual(remux[remux.index("-c") + 1], "copy")
        self.assertNotIn("libx264", remux)
        self.assertIn("libx264", self.command("gif", "mov"))


class SecurityTests(unittest.TestCase):
    def test_hashed_values_compare_without_plaintext(self):
        value = otp()
        self.assertRegex(value, r"^\d{6}$")
        self.assertNotEqual(value, digest(value))
        self.assertTrue(constant_time_equal(digest(value), digest(value)))


if __name__ == "__main__":
    unittest.main()
