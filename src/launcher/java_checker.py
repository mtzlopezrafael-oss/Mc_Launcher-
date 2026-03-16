from __future__ import annotations

"""Utilities to detect Java installation across platforms."""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple


def _candidate_from_java_home() -> Optional[Path]:
    java_home = os.environ.get("JAVA_HOME")
    if not java_home:
        return None
    candidate = Path(java_home) / "bin" / ("java.exe" if platform.system() == "Windows" else "java")
    return candidate if candidate.exists() else None


def locate_java() -> Optional[Path]:
    """
    Return the path to a usable java binary if present, otherwise None.
    Preference order: JAVA_HOME, PATH.
    """
    java_from_env = _candidate_from_java_home()
    if java_from_env:
        return java_from_env
    which = shutil.which("java")
    return Path(which) if which else None


def java_version(java_path: Path) -> Optional[str]:
    """
    Return the Java version string (e.g., '17.0.10') or None on failure.
    Uses `java -version`, which writes to stderr.
    """
    try:
        result = subprocess.run(
            [str(java_path), "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return None

    output = result.stderr.splitlines() + result.stdout.splitlines()
    for line in output:
        if "version" in line:
            # Example: 'java version "17.0.10" 2024-01-16 LTS'
            parts = line.split('"')
            if len(parts) >= 2:
                return parts[1]
    return None


def ensure_java() -> Tuple[bool, Optional[Path], Optional[str], str]:
    """
    Check for Java availability.

    Returns:
        (found, path, version, message)
    """
    path = locate_java()
    if not path:
        return False, None, None, "Java no encontrado. Instala Java 17+ y reinicia el launcher."

    version = java_version(path)
    if version is None:
        return True, path, None, f"Java detectado en {path}, no se pudo leer la versión."

    return True, path, version, f"Java detectado ({version}) en {path}"
