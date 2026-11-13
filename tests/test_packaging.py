"""Tests for frozen-mode packaging, script dispatch, and setup toolchain downloaders."""

from __future__ import annotations

import io
import json
import os
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from c64u_bridge import c64_studio, env, gamedev


def _make_zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_env_frozen_paths_and_local_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_dir = tmp_path / "C64-Studio"
    (app_dir / "tools" / "java" / "bin").mkdir(parents=True)
    (app_dir / "tools" / "oscar64" / "bin").mkdir(parents=True)
    (app_dir / "tools" / "kickassembler").mkdir(parents=True)

    java_exe = app_dir / "tools" / "java" / "bin" / ("java.exe" if os.name == "nt" else "java")
    oscar_exe = app_dir / "tools" / "oscar64" / "bin" / ("oscar64.exe" if os.name == "nt" else "oscar64")
    jar_file = app_dir / "tools" / "kickassembler" / "KickAss.jar"
    java_exe.write_bytes(b"")
    oscar_exe.write_bytes(b"")
    jar_file.write_bytes(b"")

    fake_exe = app_dir / "C64-Studio.exe"
    fake_exe.write_bytes(b"")

    monkeypatch.delenv("KICKASS_JAR", raising=False)
    monkeypatch.delenv("JAVA_BIN", raising=False)
    monkeypatch.delenv("OSCAR64_BIN", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    assert env.is_frozen() is True
    assert env.get_app_root() == app_dir.resolve()
    assert env.find_default_kickass_jar() == jar_file.resolve()
    assert Path(env.find_default_java_bin() or "") == java_exe.resolve()
    assert Path(env.find_default_oscar64_bin() or "") == oscar_exe.resolve()

    target_env: dict[str, str] = {"PATH": "C:\\Windows\\System32"}
    env.prepend_local_tool_paths(target_env, app_dir)
    parts = target_env["PATH"].split(os.pathsep)
    assert str((app_dir / "tools" / "java" / "bin").resolve()) in parts
    assert str((app_dir / "tools" / "oscar64" / "bin").resolve()) in parts


def test_gamedev_frozen_tool_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_dir = tmp_path / "C64-Studio"
    (app_dir / "tools" / "sprites").mkdir(parents=True)
    fake_exe = app_dir / "C64-Studio.exe"
    fake_exe.write_bytes(b"")

    monkeypatch.delenv("KICKASS_JAR", raising=False)
    monkeypatch.delenv("JAVA_BIN", raising=False)
    monkeypatch.delenv("OSCAR64_BIN", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    assert gamedev.tools_root() == app_dir.resolve()
    cmd = gamedev.tool_command("sprites", tmp_path / "player.json")
    assert cmd[0] == str(fake_exe)
    assert cmd[1] == "--run-script"
    assert cmd[2].endswith(str(Path("tools") / "sprites" / "sprite_tool.py"))


def test_c64_studio_run_script_dispatch(tmp_path: Path) -> None:
    out_file = tmp_path / "ran.txt"
    script = tmp_path / "sample_script.py"
    script.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        f"Path({str(out_file)!r}).write_text(' '.join(sys.argv[1:]), encoding='utf-8')\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        c64_studio.main(["--run-script", str(script), "alpha", "beta"])
    assert exc.value.code == 0
    assert out_file.read_text(encoding="utf-8") == "alpha beta"


def test_setup_bridge_downloaders_and_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import setup_bridge

    monkeypatch.setattr(setup_bridge.platform, "system", lambda: "Windows")

    jre_zip = _make_zip_bytes({"jdk-17.0.13+11-jre/bin/java.exe": b"fake-java"})
    oscar_zip = _make_zip_bytes({"oscar64-1.32/bin/oscar64.exe": b"fake-oscar64"})
    release_json = json.dumps(
        {
            "assets": [
                {
                    "name": "oscar64.zip",
                    "browser_download_url": "https://example.invalid/oscar64.zip",
                }
            ]
        }
    ).encode("utf-8")

    class _FakeResp:
        def __init__(self, payload: bytes):
            self._payload = payload

        def read(self) -> bytes:
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _fake_urlopen(req, timeout=30):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "adoptium" in url:
            return _FakeResp(jre_zip)
        if "api.github.com" in url:
            return _FakeResp(release_json)
        if "oscar64.zip" in url:
            return _FakeResp(oscar_zip)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(setup_bridge.urllib.request, "urlopen", _fake_urlopen)

    java_bin = setup_bridge.download_and_extract_portable_java(tmp_path / "tools" / "java")
    assert java_bin is not None
    assert java_bin == (tmp_path / "tools" / "java" / "bin" / "java.exe").resolve()
    assert java_bin.is_file()

    oscar_bin = setup_bridge.download_and_extract_oscar64(tmp_path / "tools" / "oscar64")
    assert oscar_bin is not None
    assert oscar_bin == (tmp_path / "tools" / "oscar64" / "bin" / "oscar64.exe").resolve()
    assert oscar_bin.is_file()

    kick_jar = tmp_path / "tools" / "kickassembler" / "KickAss.jar"
    kick_jar.parent.mkdir(parents=True, exist_ok=True)
    kick_jar.write_bytes(b"fake-jar")

    monkeypatch.setattr(setup_bridge, "is_frozen", lambda: True)
    setup_bridge.save_configuration(
        project_root=tmp_path,
        host="192.168.1.99",
        port=80,
        password=None,
        kickass_jar=kick_jar,
        java_bin=java_bin,
        oscar64_bin=oscar_bin,
    )
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "C64U_HOST=192.168.1.99" in env_text
    assert f"KICKASS_JAR={kick_jar.resolve()}" in env_text
    assert f"JAVA_BIN={java_bin.resolve()}" in env_text
    assert f"OSCAR64_BIN={oscar_bin.resolve()}" in env_text


def test_setup_bridge_github_release_staging_and_updater_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import setup_bridge

    bundle_zip = _make_zip_bytes(
        {
            "C64-Studio/C64-Studio.exe": b"new-ide",
            "C64-Studio/C64-Studio-Setup.exe": b"new-setup",
            "C64-Studio/.env": b"SHOULD_BE_STRIPPED=1",
        }
    )

    monkeypatch.setattr(setup_bridge, "_download_bytes", lambda url, label: bundle_zip)

    release = {
        "tag_name": "v1.2.3",
        "assets": [
            {
                "name": "C64-Studio-windows.zip",
                "browser_download_url": "https://example.invalid/C64-Studio-windows.zip",
            }
        ],
    }

    staged = setup_bridge.stage_c64_studio_update(tmp_path, release)
    assert staged is not None
    assert staged["tag"] == "v1.2.3"
    assert (staged["studio_dir"] / "C64-Studio.exe").is_file()
    assert not (staged["studio_dir"] / ".env").exists()
    assert staged["setup_exe"] is not None and staged["setup_exe"].is_file()

    bat_path = setup_bridge.build_windows_updater_script(tmp_path, staged, wait_pid=4242, temp_dir=tmp_path)
    bat_text = bat_path.read_text(encoding="utf-8")
    assert "PID eq 4242" in bat_text
    assert "IMAGENAME eq C64-Studio.exe" in bat_text
    assert "xcopy /E /Y /I /Q" in bat_text
    assert "C64-Studio-Setup.exe" in bat_text
    assert ".c64_studio_version" in bat_text
    assert 'del "%~f0"' in bat_text


def test_setup_bridge_version_comparison(tmp_path: Path) -> None:
    import setup_bridge

    assert setup_bridge.is_newer_version("v0.2.0", "0.1.0") is True
    assert setup_bridge.is_newer_version("v1.10.0", "v1.2.0") is True
    assert setup_bridge.is_newer_version("v0.1.0", "0.1.0") is False
    assert setup_bridge.is_newer_version("v0.1.0", "v0.2.0") is False

    assert setup_bridge.get_installed_version(tmp_path) == setup_bridge.APP_VERSION
    (tmp_path / setup_bridge.VERSION_STAMP_FILE).write_text("v0.2.0\n", encoding="utf-8")
    assert setup_bridge.get_installed_version(tmp_path) == "v0.2.0"
