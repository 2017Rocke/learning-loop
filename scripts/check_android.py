#!/usr/bin/env python3
"""Run portable native rules checks with JDK 17; no phone or personal data needed."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def java_tool(name):
    suffix = ".exe" if os.name == "nt" else ""
    java_home = os.environ.get("JAVA_HOME")
    candidate = Path(java_home) / "bin" / (name + suffix) if java_home else None
    executable = str(candidate) if candidate and candidate.is_file() else shutil.which(name)
    if not executable:
        raise SystemExit("JDK 17 is required: set JAVA_HOME or add javac/java to PATH.")
    return executable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, default=ROOT / "dist/android-content")
    parser.add_argument("--assets", type=Path, default=ROOT / "android/app/src/main/assets/site")
    args = parser.parse_args()
    manifest_path = args.content / "manifest.json"
    courses = args.assets / "courses.json"
    if not manifest_path.is_file() or not courses.is_file():
        raise SystemExit("First run: python3 scripts/build_android_content.py --assets android/app/src/main/assets/site")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archive_name = manifest["archive"]["name"]
    if Path(archive_name).name != archive_name:
        raise SystemExit("Invalid archive name in local manifest")
    native = ROOT / "android/app/src/main/java/cn/learningloop/app"
    files = [native / (name + ".java") for name in
             ("ContentJson", "CourseContentRules", "ByteRanges", "CalendarTimes")]
    files.extend(ROOT / "android/tests" / name for name in
                 ("CourseContentRulesTest.java", "NativeUtilityCheck.java"))
    with tempfile.TemporaryDirectory(prefix="learning-loop-native-check-") as folder:
        subprocess.run([java_tool("javac"), "-encoding", "UTF-8", "-d", folder,
                        *map(str, files)], check=True)
        subprocess.run([java_tool("java"), "-cp", folder,
                        "cn.learningloop.app.CourseContentRulesTest", str(courses),
                        str(manifest_path), str(args.content / archive_name)], check=True)
        subprocess.run([java_tool("java"), "-cp", folder,
                        "cn.learningloop.app.NativeUtilityCheck"], check=True)


if __name__ == "__main__":
    main()
