"""Offline authoring checks: no speech service, model, speaker or learner state."""
import array
import asyncio
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("neural_audio", ROOT / "scripts/generate_neural_audio.py")
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


def fixture():
    return {"engine": "edge-tts", "voice": "zh-CN-XiaoxiaoNeural", "rate": "-5%", "pitch": "+0Hz",
            "clips": [{"chapter": "logic", "walkthrough_id": None, "title": "原理", "filename": "logic.mp3", "text": "解释概率。"},
                      {"chapter": "case", "walkthrough_id": None, "title": "案例", "filename": "case.mp3", "text": "先看一个例子。"}]}


class NeuralAudioTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "web/media/topic/audio"
        self.output.mkdir(parents=True)
        self.root_patch = patch.object(audio, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def seed_old(self):
        for filename in ("logic.mp3", "case.mp3", "metadata.json", "generation-record.json"):
            (self.output / filename).write_bytes(b"old-" + filename.encode())
        return self.snapshot()

    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.output.iterdir() if p.is_file()}

    def fake_synthesis(self, clip, destination):
        destination.write_bytes((clip["text"].encode() + b"MP3") * 256)

    @staticmethod
    def decoded(*unused):
        return {"decoded_seconds": 12.5, "rms_pcm16": 900, "sample_rate": 24000,
                "channels": 1, "decoded_frames": 300000, "peak_pcm16": 2000, "nonzero_fraction": .8}

    def generate(self, synthesize=None, data=None):
        with patch.object(audio, "verify_decoded", side_effect=self.decoded):
            return audio.generate(data or fixture(), self.output, "ffmpeg", "test-version",
                                  synthesize or self.fake_synthesis)

    def test_later_synthesis_failure_preserves_every_old_file(self):
        original = self.seed_old()
        calls = []
        def fail_second(clip, destination):
            calls.append(clip["filename"])
            if len(calls) == 2:
                raise RuntimeError("synthetic speech failure")
            self.fake_synthesis(clip, destination)
        with self.assertRaisesRegex(RuntimeError, "synthetic speech failure"):
            self.generate(fail_second)
        self.assertEqual(calls, ["logic.mp3", "case.mp3"])
        self.assertEqual(self.snapshot(), original)
        self.assertFalse(any(p.is_dir() for p in self.output.iterdir()))

    def test_later_decode_failure_preserves_every_old_file(self):
        original = self.seed_old()
        with patch.object(audio, "verify_decoded", side_effect=[self.decoded(), ValueError("bad second audio")]):
            with self.assertRaisesRegex(ValueError, "bad second audio"):
                audio.generate(fixture(), self.output, "ffmpeg", "test-version", self.fake_synthesis)
        self.assertEqual(self.snapshot(), original)

    def test_publish_failure_rolls_back_already_replaced_files(self):
        original = self.seed_old()
        replace = audio.os.replace
        calls = []
        def fail_metadata_once(source, target):
            calls.append(Path(target).name)
            if Path(target).name == "metadata.json" and calls.count("metadata.json") == 1:
                raise OSError("synthetic disk failure")
            return replace(source, target)
        with patch.object(audio.os, "replace", side_effect=fail_metadata_once):
            with self.assertRaisesRegex(OSError, "synthetic disk failure"):
                self.generate()
        self.assertEqual(self.snapshot(), original)

    def test_cache_needs_matching_fingerprint_and_actual_file_hash(self):
        metadata = self.generate()
        self.assertEqual(metadata["voice"], "合成中文女声（晓晓 · Microsoft Edge Neural）")
        self.assertNotIn("Tingting", metadata["voice"])
        self.assertEqual(metadata["clips"][0]["src"], "/media/topic/audio/logic.mp3")
        with patch.object(audio, "verify_decoded", side_effect=self.decoded) as decode:
            audio.generate(fixture(), self.output, "ffmpeg", "test-version",
                           lambda *_: self.fail("Matching cache must not call the speech service"))
            self.assertEqual(decode.call_count, 2)
        (self.output / "logic.mp3").write_bytes(b"tampered")
        called = []
        def regenerate(clip, destination):
            called.append(clip["filename"])
            self.fake_synthesis(clip, destination)
        self.generate(regenerate)
        self.assertEqual(called, ["logic.mp3"])
        data = fixture()
        data["clips"][1]["text"] = "已修改的文本。"
        called.clear()
        self.generate(regenerate, data)
        self.assertEqual(called, ["case.mp3"])
        record = json.loads((self.output / "generation-record.json").read_text())
        self.assertEqual(record["clips"]["logic.mp3"]["sha256"], hashlib.sha256((self.output / "logic.mp3").read_bytes()).hexdigest())

    def test_outside_and_symlink_outputs_are_rejected_before_synthesis(self):
        self.output.joinpath("escape").symlink_to(self.root, target_is_directory=True)
        for output in (self.root / "outside", self.output / "escape/audio"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                audio.generate(fixture(), output, "ffmpeg", "test", lambda *_: self.fail("must not synthesize"))
        outside = self.root / "private-file"
        outside.write_text("untouched")
        (self.output / "logic.mp3").symlink_to(outside)
        with self.assertRaises(ValueError):
            self.generate()
        self.assertEqual(outside.read_text(), "untouched")

    def test_rejects_bad_input_before_writing_or_network(self):
        invalid = [[], {}, {**fixture(), "engine": "unknown"}, {**fixture(), "rate": 1},
                   {**fixture(), "pitch": "+99Hz"}, {**fixture(), "voice": "unknown"},
                   {**fixture(), "clips": [fixture()["clips"][0]] * 17}]
        for field, value in (("filename", "../outside.mp3"), ("filename", "one.m4a"),
                             ("text", ""), ("text", "x" * 3001), ("text", "bad\x00text"),
                             ("title", None), ("walkthrough_id", "invalid"), ("chapter", [])):
            data = fixture()
            data["clips"][0][field] = value
            invalid.append(data)
        duplicate = fixture()
        duplicate["clips"].append(copy.deepcopy(duplicate["clips"][0]))
        invalid.append(duplicate)
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                audio.generate(data, self.output, "ffmpeg", "test", lambda *_: self.fail("must not synthesize"))
        self.assertEqual(self.snapshot(), {})

    def test_full_pcm_measurement_rejects_silence_and_excessive_duration(self):
        encoded = self.output / "clip.mp3"
        encoded.write_bytes(b"fake" * 1024)
        def write_pcm(arguments, **options):
            self.assertEqual(options["timeout"], 60)
            self.assertIn("-xerror", arguments)
            self.assertNotIn("-t", arguments)
            Path(arguments[-1]).write_bytes(array.array("h", [1000, -1000] * 12000).tobytes())
        with patch.object(audio.subprocess, "run", side_effect=write_pcm):
            measured = audio.verify_decoded(encoded, self.output, "ffmpeg", 180)
        self.assertEqual(measured["decoded_seconds"], 1)
        self.assertEqual(measured["decoded_frames"], 24000)
        self.assertEqual(measured["rms_pcm16"], 1000)
        def silence(arguments, **_):
            Path(arguments[-1]).write_bytes(b"\0" * 48000)
        with patch.object(audio.subprocess, "run", side_effect=silence), self.assertRaisesRegex(ValueError, "Silent"):
            audio.verify_decoded(encoded, self.output, "ffmpeg", 180)
        def too_long(arguments, **_):
            Path(arguments[-1]).write_bytes(b"\0" * (48000 * 181))
        with patch.object(audio.subprocess, "run", side_effect=too_long), self.assertRaisesRegex(ValueError, "duration"):
            audio.verify_decoded(encoded, self.output, "ffmpeg", 180)

    def test_network_budget_cancels_one_request_without_retrying(self):
        calls, cancelled = [], []
        class FakeRequest:
            async def save(self, destination):
                try:
                    await asyncio.sleep(10)
                finally:
                    cancelled.append(destination)
        class FakeEdge:
            @staticmethod
            def Communicate(text, voice, **settings):
                calls.append((text, voice, settings))
                return FakeRequest()
        data = fixture()
        self.assertEqual(audio.NETWORK_TIMEOUT, 60)
        with patch.object(audio, "NETWORK_TIMEOUT", .001), self.assertRaises(asyncio.TimeoutError):
            asyncio.run(audio.synthesize_clip(FakeEdge, data, data["clips"][0], self.output / "timeout.mp3"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(cancelled), 1)
        self.assertEqual(calls[0][2], {"rate": "-5%", "pitch": "+0Hz"})
        self.assertEqual(self.snapshot(), {})


if __name__ == "__main__":
    unittest.main()
