#!/usr/bin/env python3
"""Explicit authoring CLI: synthesize online once, publish verified offline MP3s.

Requires an intentionally installed optional edge-tts package and FFmpeg. It
never installs dependencies, changes service authentication, runs in the App,
or edits lessons and learner records. Each clip has a 60-second network budget.
All requested audio is staged and fully decoded before replacing public files.

Input: {"engine":"edge-tts", "voice":"zh-CN-XiaoxiaoNeural", "rate":"-5%",
"pitch":"+0Hz", "clips":[{"chapter":"logic", "walkthrough_id":null,
"title":"中文讲解", "filename":"logic.mp3", "text":"旁白全文"}]}.
"""
from __future__ import annotations

import argparse
import array
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
CHAPTERS = {"logic", "case", "code", "experiment", "application", "summary"}
NETWORK_TIMEOUT = 60
DECODE_TIMEOUT = 60
SAMPLE_RATE = 24000
MAX_ENCODED_BYTES = 6 * 1024 * 1024


def validate_narration(data):
    if not isinstance(data, dict) or set(data) != {"engine", "voice", "rate", "pitch", "clips"}:
        raise ValueError("Narration requires exactly engine, voice, rate, pitch, clips")
    if data["engine"] != "edge-tts":
        raise ValueError("Only the optional edge-tts authoring engine is supported")
    if not isinstance(data["voice"], str) or not re.fullmatch(r"[a-z]{2,3}-[A-Z]{2}-[A-Za-z0-9]+Neural", data["voice"]):
        raise ValueError("Specify a named neural voice, for example zh-CN-XiaoxiaoNeural")
    for field, unit in (("rate", "%"), ("pitch", "Hz")):
        value = data[field]
        if not isinstance(value, str) or not re.fullmatch(r"[+-]\d{1,2}" + unit, value):
            raise ValueError(f"{field} requires a signed integer and {unit}")
        if not -50 <= int(value[:-len(unit)]) <= 50:
            raise ValueError(f"{field} must be between -50 and +50 {unit}")
    if not isinstance(data["clips"], list) or not 1 <= len(data["clips"]) <= 16:
        raise ValueError("Narration needs between 1 and 16 clips")
    filenames, slots = set(), set()
    for clip in data["clips"]:
        if not isinstance(clip, dict) or set(clip) != {"chapter", "walkthrough_id", "title", "filename", "text"}:
            raise ValueError("Clip fields do not match the narration contract")
        if not isinstance(clip["chapter"], str) or clip["chapter"] not in CHAPTERS:
            raise ValueError("Unknown chapter")
        walkthrough = clip["walkthrough_id"]
        if walkthrough is not None and (clip["chapter"] != "code" or not isinstance(walkthrough, str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,119}", walkthrough)):
            raise ValueError("Only code clips may specify a nonempty walkthrough ID")
        filename = clip["filename"]
        if not isinstance(filename, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,95}\.mp3", filename) or filename in filenames:
            raise ValueError("Narration filenames must be unique local .mp3 names")
        slot = (clip["chapter"], walkthrough)
        if slot in slots:
            raise ValueError("A chapter or walkthrough may have only one narration clip")
        filenames.add(filename)
        slots.add(slot)
        for field, limit in (("title", 200), ("text", 3000)):
            value = clip[field]
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(f"Clip {field} must contain 1 to {limit} characters")
            if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
                raise ValueError(f"Clip {field} contains an invalid control character")
    return data


def load_narration(path):
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("Narration input exceeds 1 MiB")
    return validate_narration(json.loads(path.read_text(encoding="utf-8")))


def output_location(path):
    root = ROOT.resolve()
    media = (root / "web/media").resolve()
    output = path.resolve()
    if root not in media.parents or (output != media and media not in output.parents):
        raise ValueError("Audio output must resolve inside this project's web/media directory")
    return output, "/" + output.relative_to(root / "web").as_posix() + "/"


def target_file(output, filename):
    target = output / filename
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError(f"Output target must be a regular file: {filename}")
    return target


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(data, clip, engine_version):
    settings = {name: data[name] for name in ("engine", "voice", "rate", "pitch")}
    settings.update(text=clip["text"], engine_version=engine_version)
    return digest(json.dumps(settings, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def read_cache(path):
    if not path.exists() or path.stat().st_size > 1024 * 1024:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value["clips"] if isinstance(value, dict) and isinstance(value.get("clips"), dict) else {}
    except (ValueError, OSError):
        return {}


async def synthesize_clip(edge_tts, settings, clip, destination):
    # One normal library call, no custom headers, token handling, retry loop or proxy.
    request = edge_tts.Communicate(clip["text"], settings["voice"],
                                   rate=settings["rate"], pitch=settings["pitch"])
    await asyncio.wait_for(request.save(str(destination)), timeout=NETWORK_TIMEOUT)


def verify_decoded(encoded, staging, ffmpeg, maximum_seconds):
    if not encoded.is_file() or not 1024 <= encoded.stat().st_size <= MAX_ENCODED_BYTES:
        raise ValueError(f"Empty or oversized encoded audio: {encoded.name}")
    decoded = staging / (encoded.stem + ".pcm")
    # Decode to EOF, not merely a probe or a duration-limited excerpt. -xerror
    # prevents a damaged packet being silently skipped on an otherwise valid file.
    subprocess.run([str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error", "-xerror",
                    "-i", str(encoded), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
                    "-c:a", "pcm_s16le", "-f", "s16le", "-y", str(decoded)],
                   check=True, capture_output=True, timeout=DECODE_TIMEOUT)
    byte_count = decoded.stat().st_size
    seconds = byte_count / (2 * SAMPLE_RATE)
    if byte_count % 2 or not 1 <= seconds <= maximum_seconds:
        raise ValueError(f"{encoded.name}: decoded duration must be 1 to {maximum_seconds} seconds")
    pcm = array.array("h", decoded.read_bytes())
    if sys.byteorder != "little":
        pcm.byteswap()
    rms = math.sqrt(sum(value * value for value in pcm) / len(pcm))
    peak = max(abs(value) for value in pcm)
    audible = sum(abs(value) > 16 for value in pcm) / len(pcm)
    if rms < 20 or peak < 100 or audible < .05:
        raise ValueError(f"Silent or unexpectedly empty narration: {encoded.name}")
    return {"sample_rate": SAMPLE_RATE, "channels": 1, "decoded_frames": len(pcm),
            "decoded_seconds": seconds, "rms_pcm16": round(rms, 2),
            "peak_pcm16": peak, "nonzero_fraction": round(audible, 4)}


def publish_verified(replacements, staging):
    """Replace individual files only after verification; roll back an I/O failure.

    These renames are not a cross-file crash transaction. The CLI must finish
    successfully before an author builds or publishes a course package.
    """
    backups = {}
    for index, (_, target) in enumerate(replacements):
        if target.exists():
            backup = staging / f"previous-{index}"
            shutil.copyfile(target, backup)
            backups[target] = backup
    replaced = []
    try:
        for source, target in replacements:
            os.replace(source, target)
            replaced.append(target)
    except Exception:
        for target in reversed(replaced):
            if target in backups:
                os.replace(backups[target], target)
            else:
                target.unlink()
        raise


def generate(data, output_dir, ffmpeg, engine_version, synthesize, force=False):
    """The supplied synthesizer performs one clip call; tests use offline fakes."""
    validate_narration(data)
    output, prefix = output_location(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for name in [clip["filename"] for clip in data["clips"]] + ["metadata.json", "generation-record.json"]:
        target_file(output, name)
    old = read_cache(output / "generation-record.json")
    records, clips = {}, []
    with tempfile.TemporaryDirectory(prefix=".neural-stage-", dir=output) as folder:
        staging = Path(folder)
        replacements = []
        for clip in data["clips"]:
            filename = clip["filename"]
            target, staged = output / filename, staging / filename
            key = fingerprint(data, clip, engine_version)
            previous = old.get(filename, {})
            reused = False
            if not force and isinstance(previous, dict) and previous.get("fingerprint") == key and target.is_file():
                if target.stat().st_size <= MAX_ENCODED_BYTES:
                    cached = target.read_bytes()
                    if digest(cached) == previous.get("sha256"):
                        staged.write_bytes(cached)
                        reused = True
            if not reused:
                synthesize(clip, staged)
            decoded = verify_decoded(staged, staging, ffmpeg, 300 if clip["walkthrough_id"] else 180)
            duration = decoded["decoded_seconds"]
            records[filename] = {"fingerprint": key, "sha256": digest(staged.read_bytes()),
                                 "bytes": staged.stat().st_size, "duration_seconds": duration,
                                 "engine": data["engine"], "engine_version": engine_version,
                                 "decode_check": decoded}
            clips.append({"chapter": clip["chapter"], "walkthrough_id": clip["walkthrough_id"],
                          "title": clip["title"], "src": prefix + filename,
                          "duration_seconds": round(duration, 3), "transcript": clip["text"]})
            replacements.append((staged, target))
            print(f"{filename}: {duration:.3f}s, decoded RMS {decoded['rms_pcm16']} ({'verified cache' if reused else 'synthesized'})", flush=True)
        voice_label = ("合成中文女声（晓晓 · Microsoft Edge Neural）" if data["voice"] == "zh-CN-XiaoxiaoNeural"
                       else f"合成语音（{data['voice']} · Microsoft Edge Neural）")
        metadata = {"voice": voice_label, "clips": clips}
        record = {name: data[name] for name in ("engine", "voice", "rate", "pitch")}
        record.update(engine_version=engine_version, clips=records)
        for filename, value in (("metadata.json", metadata), ("generation-record.json", record)):
            staged = staging / filename
            staged.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            replacements.append((staged, output / filename))
        publish_verified(replacements, staging)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="Destination inside this project's web/media")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="Existing FFmpeg command or executable path")
    parser.add_argument("--force", action="store_true", help="Regenerate even when fingerprint and file SHA-256 match")
    args = parser.parse_args()
    data = load_narration(args.input)
    output_location(args.output_dir)
    ffmpeg = shutil.which(args.ffmpeg)
    if ffmpeg is None:
        parser.error("FFmpeg is unavailable; supply --ffmpeg with an existing executable")
    try:
        import edge_tts  # Optional authoring dependency, never imported by the App.
    except ImportError:
        parser.error("Optional edge-tts is unavailable; use an authoring environment that already has it installed")
    def synthesize(clip, destination):
        asyncio.run(synthesize_clip(edge_tts, data, clip, destination))
    try:
        result = generate(data, args.output_dir, ffmpeg, edge_tts.__version__, synthesize, args.force)
    except Exception as error:
        # A nonzero exit preserves the original batch on synthesis/decode failure.
        parser.exit(1, f"Narration generation stopped: {type(error).__name__}: {error}\n")
    print(f"Published {len(result['clips'])} verified offline clips. Lesson and learner records were not changed.")


if __name__ == "__main__":
    main()
