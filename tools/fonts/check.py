#!/usr/bin/env python3
"""Validate bundled glyphs in an isolated real Godot process, without the game server."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def run(command: list[str], *, cwd: Path, env: dict[str, str], marker: str | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=120)
    if result.returncode or (marker and marker not in result.stdout):
        print(result.stdout, end="")
        raise RuntimeError(f"Font check failed (exit {result.returncode}): {command}")
    if "SCRIPT ERROR:" in result.stdout or "Parse Error:" in result.stdout:
        print(result.stdout, end="")
        raise RuntimeError("Godot reported a script error")
    if marker:
        print(result.stdout, end="")
    else:
        print("PASS: isolated Godot font import")
    return result.stdout


def verify_integration() -> None:
    project = (ROOT / "project.godot").read_text()
    theme = (ROOT / "themes/main_theme.tres").read_text()
    selection = (ROOT / "scenes/ui/CharacterSelect.tscn").read_text()
    if 'theme/custom="res://themes/main_theme.tres"' not in project:
        raise ValueError("Game does not select the bundled main theme")
    if 'ArcadeFontLocale="*res://scripts/arcade_font_locale.gd"' not in project:
        raise ValueError("Game does not register its locale font switcher")
    if "res://fonts/neptune-arcade/neptune_arcade.tres" not in theme or "default_font =" not in theme:
        raise ValueError("Main theme does not use Neptune Arcade")
    if "bomberman_font.ttf" in selection or "theme_override_fonts/font" in selection:
        raise ValueError("Character selection overrides the locale-aware global font")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", default=shutil.which("godot"), help="Godot 4 executable")
    parser.add_argument("--screenshot", type=Path,
                        help="Render showcase PNG; requires a graphical display or xvfb-run")
    parser.add_argument("--skip-integration", action="store_true",
                        help="Check resources only while integrating into a different Godot project")
    args = parser.parse_args()
    if not args.godot:
        parser.error("Godot is required; pass --godot /path/to/godot")
    godot = str(Path(args.godot).resolve())
    try:
        if not args.skip_integration:
            verify_integration()
        package = ROOT / "fonts/neptune-arcade"
        if not (package / "neptune_arcade.tres").is_file():
            raise ValueError("Bundled font resources are missing; run tools/fonts/generate_resources.py")
        with tempfile.TemporaryDirectory(prefix="neptune-font-check-") as directory:
            sandbox = Path(directory)
            shutil.copytree(package, sandbox / "fonts/neptune-arcade",
                            ignore=shutil.ignore_patterns("__pycache__", ".godot"))
            (sandbox / "tools/fonts").mkdir(parents=True)
            for name in ("check_godot.gd", "showcase.gd", "showcase.tscn"):
                shutil.copy2(ROOT / "tools/fonts" / name, sandbox / "tools/fonts" / name)
            (sandbox / "themes").mkdir()
            shutil.copy2(ROOT / "themes/main_theme.tres", sandbox / "themes/main_theme.tres")
            (sandbox / "scripts").mkdir()
            shutil.copy2(ROOT / "scripts/arcade_font_locale.gd", sandbox / "scripts/arcade_font_locale.gd")
            (sandbox / "project.godot").write_text(
                'config_version=5\n[application]\nconfig/name="Neptune Font Check"\n'
                'run/main_scene="res://tools/fonts/showcase.tscn"\n'
                '[display]\nwindow/size/viewport_width=960\nwindow/size/viewport_height=720\n'
                '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
                'textures/default_filters/use_nearest_mipmap_filter=false\n'
            )
            env = os.environ.copy()
            for key, name in (("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache"),
                              ("XDG_CONFIG_HOME", "config")):
                env[key] = str(sandbox / name)
            run([godot, "--headless", "--path", str(sandbox), "--editor", "--import"],
                cwd=sandbox, env=env)
            run([godot, "--headless", "--path", str(sandbox), "--script", "tools/fonts/check_godot.gd"],
                cwd=sandbox, env=env, marker="NEPTUNE_FONT_CHECK_PASS")
            if args.screenshot:
                destination = args.screenshot.resolve()
                destination.parent.mkdir(parents=True, exist_ok=True)
                command = [godot, "--path", str(sandbox), "--", "--screenshot=" + str(destination)]
                if not env.get("DISPLAY"):
                    xvfb = shutil.which("xvfb-run")
                    if not xvfb:
                        raise ValueError("Screenshot requires DISPLAY or xvfb-run; resource checks passed")
                    command = [xvfb, "-a", "-s", "-screen 0 960x720x24", *command]
                run(command, cwd=sandbox, env=env, marker="NEPTUNE_FONT_SCREENSHOT_PASS")
                if not destination.is_file() or destination.stat().st_size < 1000:
                    raise ValueError("Screenshot output is missing or empty")
        print("PASS: game integration and imported multilingual font stack")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print("FAIL:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
