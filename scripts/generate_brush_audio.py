#!/usr/bin/env python3
"""Create local Chinese narration with macOS's installed voice and audio codecs.

No network, voice downloads, package installation, or speaker playback. The input
is an explicit narration JSON; this script never edits lesson or learning data.
Every clip is staged, checked, decoded to PCM, then atomically replaces its output.
The metadata is only published after every requested clip has been verified.

On restricted macOS environments, system speech/audio services may need an
approved unsandboxed execution. A successful `say` exit alone is insufficient:
this script rejects zero-duration and silent output.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web/media/brush/audio"
ALLOWED_CHAPTERS = {"logic", "case", "code", "experiment", "application", "summary"}


def run(arguments):
    return subprocess.run(arguments, check=True, capture_output=True, text=True).stdout


def audio_info(path):
    output = run(["/usr/bin/afinfo", str(path)])
    match = re.search(r"estimated duration:\s*([0-9.]+) sec", output)
    if not match:
        raise RuntimeError(f"Cannot confirm audio duration: {path.name}")
    duration = float(match.group(1))
    if duration <= 1 or path.stat().st_size < 1024:
        raise RuntimeError(f"Speech service produced empty/invalid audio: {path.name}")
    return duration, output


def verify_decoded(path, temp):
    decoded = temp / (path.stem + ".decoded.wav")
    run(["/usr/bin/afconvert", str(path), str(decoded), "-f", "WAVE", "-d", "LEI16"])
    # macOS writes WAVE_FORMAT_EXTENSIBLE. Read its PCM payload explicitly so
    # the system Python 3.9 works as well as Python 3.12's extended wave reader.
    raw = decoded.read_bytes()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise RuntimeError("Decoder did not produce a WAVE file")
    chunks, offset = {}, 12
    while offset + 8 <= len(raw):
        name, size = struct.unpack_from("<4sI", raw, offset)
        chunks[name] = raw[offset + 8:offset + 8 + size]
        offset += 8 + size + size % 2
    fmt = chunks.get(b"fmt ", b"")
    if len(fmt) < 16 or b"data" not in chunks:
        raise RuntimeError("Decoded WAVE is missing format or samples")
    kind, channels, rate, _, block, bits = struct.unpack_from("<HHIIHH", fmt)
    pcm_kind = kind == 1 or (kind == 65534 and len(fmt) >= 40 and struct.unpack_from("<I", fmt, 24)[0] == 1)
    if not pcm_kind or channels != 1 or bits != 16 or block != 2:
        raise RuntimeError("Expected mono 16-bit PCM decoded audio")
    pcm = array.array("h", chunks[b"data"])
    if sys.byteorder != "little":
        pcm.byteswap()
    if not pcm:
        raise RuntimeError("Decoded audio has no samples")
    rms = math.sqrt(sum(value * value for value in pcm) / len(pcm))
    peak = max(abs(value) for value in pcm)
    nonzero_fraction = sum(abs(value) > 16 for value in pcm) / len(pcm)
    if rms < 20 or peak < 100 or nonzero_fraction < .05:
        raise RuntimeError("Decoded narration is silent or unexpectedly empty")
    return {
        "sample_rate": rate, "channels": channels,
        "decoded_frames": len(pcm), "decoded_seconds": len(pcm) / rate,
        "rms_pcm16": round(rms, 2), "peak_pcm16": peak,
        "nonzero_fraction": round(nonzero_fraction, 4),
    }


def load_narration(path):
    data = json.loads(path.read_text())
    if set(data) != {"voice", "rate", "clips"}:
        raise ValueError("Narration requires exactly voice, rate, clips")
    voice = data["voice"]
    rate = data["rate"]
    if voice not in {"Tingting", "Meijia", "Sinji"}:
        raise ValueError("Choose an already installed Chinese voice")
    if type(rate) is not int or not 120 <= rate <= 240:
        raise ValueError("Narration rate must be between 120 and 240")
    if not isinstance(data["clips"], list) or not data["clips"]:
        raise ValueError("Narration needs clips")
    files = set()
    for clip in data["clips"]:
        if set(clip) != {"chapter", "walkthrough_id", "title", "filename", "text"}:
            raise ValueError("Clip fields do not match the narration contract")
        if clip["chapter"] not in ALLOWED_CHAPTERS:
            raise ValueError("Unknown chapter")
        if clip["walkthrough_id"] is not None and (clip["chapter"] != "code" or not isinstance(clip["walkthrough_id"], str)):
            raise ValueError("Only code chapters may specify a walkthrough")
        filename = clip["filename"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*\.m4a", filename) or filename in files:
            raise ValueError("Narration filenames must be unique local .m4a names")
        files.add(filename)
        if not isinstance(clip["text"], str) or not clip["text"].strip() or len(clip["text"]) > 3000:
            raise ValueError("Narration text is empty or too long")
        if not isinstance(clip["title"], str) or not clip["title"].strip():
            raise ValueError("Narration title is required")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "content/brush-narration.json")
    parser.add_argument("--output-dir", type=Path, default=OUT,
                        help="Destination below this project's web/media; default: web/media/brush/audio")
    parser.add_argument("--force", action="store_true", help="Regenerate even when text, voice, and rate match")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    media_dir = (ROOT / "web/media").resolve()
    if output_dir != media_dir and media_dir not in output_dir.parents:
        raise ValueError("Audio output must resolve inside this project's web/media directory")
    public_prefix = "/" + output_dir.relative_to((ROOT / "web").resolve()).as_posix() + "/"
    data = load_narration(args.input)
    installed = run(["/usr/bin/say", "-v", "?"])
    if not re.search(r"^" + re.escape(data["voice"]) + r"\s+zh_", installed, flags=re.MULTILINE):
        raise RuntimeError("Requested Chinese voice is not already available")
    output_dir.mkdir(parents=True, exist_ok=True)
    record_path = output_dir / "generation-record.json"
    old_records = json.loads(record_path.read_text()).get("clips", {}) if record_path.exists() else {}
    records, clips = {}, []
    # Place staging in the destination filesystem for an atomic final rename.
    with tempfile.TemporaryDirectory(prefix=".generate-", dir=output_dir) as directory:
        temp = Path(directory)
        replacements = []
        for clip in data["clips"]:
            filename = clip["filename"]
            target = output_dir / filename
            fingerprint = hashlib.sha256(json.dumps({"text":clip["text"],"voice":data["voice"],"rate":data["rate"]},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            reuse = not args.force and old_records.get(filename, {}).get("fingerprint") == fingerprint and target.exists()
            if reuse:
                encoded = target
            else:
                text_path = temp / (target.stem + ".txt")
                raw = temp / (target.stem + ".aiff")
                encoded = temp / filename
                text_path.write_text(clip["text"])
                run(["/usr/bin/say", "-v", data["voice"], "-r", str(data["rate"]), "-f", str(text_path), "-o", str(raw)])
                audio_info(raw)
                run(["/usr/bin/afconvert", str(raw), str(encoded), "-f", "m4af", "-d", "aac", "-b", "64000"])
                replacements.append((encoded, target))
            duration, info = audio_info(encoded)
            limit = 300 if clip["walkthrough_id"] else 180
            if duration > limit:
                raise RuntimeError(f"{filename} is {duration:.1f}s: shorten narration to at most {limit} seconds")
            decoded = verify_decoded(encoded, temp)
            if abs(decoded["decoded_seconds"] - duration) > .15:
                raise RuntimeError("Decoded duration disagrees with the container")
            records[filename] = {"fingerprint":fingerprint,"sha256":hashlib.sha256(encoded.read_bytes()).hexdigest(),"bytes":encoded.stat().st_size,"duration_seconds":duration,"format":"AAC, mono, 22050 Hz, 64 kbps target","decode_check":decoded}
            clips.append({"chapter":clip["chapter"],"walkthrough_id":clip["walkthrough_id"],"title":clip["title"],"src":public_prefix+filename,"duration_seconds":round(duration,3),"transcript":clip["text"]})
            print(f"{filename}: {duration:.3f}s, {encoded.stat().st_size:,} bytes; decoded RMS {decoded['rms_pcm16']}", flush=True)
        for source, target in replacements:
            os.replace(source, target)
        metadata = {"voice":f"本机合成中文语音（{data['voice']}）", "clips":clips}
        for name, content in [("metadata.json",metadata),("generation-record.json",{"voice":data["voice"],"rate":data["rate"],"source":str(args.input.resolve()),"clips":records})]:
            pending = temp / name
            pending.write_text(json.dumps(content,ensure_ascii=False,indent=2)+"\n")
            os.replace(pending, output_dir / name)
    print(f"Generated and decoded {len(clips)} local narration clips. No speaker playback was requested.")


if __name__ == "__main__":
    main()
