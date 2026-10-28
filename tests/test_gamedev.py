import shutil
from pathlib import Path

import pytest

from c64u_bridge.gamedev import GAME_TOOLS, run_tool, tool_command, tools_root

ROOT = tools_root()
IRONFRONT = ROOT / "game_dev" / "ironfront"


def test_every_registered_tool_script_exists():
    for tool in GAME_TOOLS.values():
        assert (ROOT / tool.script).is_file(), tool.script


def test_tool_command_runs_script_with_target_and_extra_args(tmp_path):
    cmd = tool_command("song", tmp_path / "tune.py")
    assert cmd[1].endswith("song_tool.py")
    assert cmd[2] == str(tmp_path / "tune.py")
    assert cmd[3:] == ["--build"]


def _copy(folder, tmp_path, *names):
    for name in names:
        shutil.copy(IRONFRONT / folder / name, tmp_path / name)


def test_sprite_tool_builds_bank_and_review(tmp_path):
    _copy("sprites", tmp_path, "ironfront_sprites.py", "review_template.html")
    res = run_tool("sprites", tmp_path / "ironfront_sprites.py")
    assert res.ok, res.output
    assert res.first(".html") == tmp_path / "sprite_review.html"
    asm = (tmp_path / "sprites.asm").read_text(encoding="utf-8")
    assert ".const SPR_TANK = 0" in asm and ".align 64" in asm


def test_koala_tool_writes_a_valid_koala_file(tmp_path):
    scene = tmp_path / "scene.py"
    scene.write_text(
        "from koala_tool import YELLOW, small_text\n"
        "OUTPUT = 'title'\n"
        "def compose(cv):\n"
        "    small_text(cv, 'TEST', 10, 10, YELLOW)\n",
        encoding="utf-8",
    )
    res = run_tool("koala", scene)
    assert res.ok, res.output
    kla = (tmp_path / "title.kla").read_bytes()
    assert len(kla) == 10003 and kla[:2] == b"\x00\x60"


@pytest.mark.skipif(shutil.which("java") is None, reason="KickAssembler needs Java")
def test_song_tool_builds_sid_and_profiler_reads_it(tmp_path):
    _copy("music", tmp_path, "ironfront_march.py", "music.asm")
    # music.asm imports the driver relative to the game folder; point it at tools/
    asm = tmp_path / "music.asm"
    driver = (ROOT / "tools" / "sid" / "sid_player.asm").as_posix()
    asm.write_text(asm.read_text(encoding="utf-8").replace("../../../tools/sid/sid_player.asm", driver),
                   encoding="utf-8")
    res = run_tool("song", tmp_path / "ironfront_march.py")
    assert res.ok, res.output
    sid = res.first(".sid")
    assert sid is not None and sid.read_bytes()[:4] == b"PSID"

    prof = run_tool("sim", sid)
    assert prof.ok, prof.output
    assert "raster lines" in prof.output


def test_tileset_tool_builds_charset_tiles_and_map(tmp_path):
    _copy("map", tmp_path, "ironfront_map.py")
    res = run_tool("tileset", tmp_path / "ironfront_map.py")
    assert res.ok, res.output
    assert res.first(".html") == tmp_path / "ironfront_review.html"
    assert len((tmp_path / "ironfront_charset.bin").read_bytes()) == 2048
    asm = (tmp_path / "ironfront_tiles.asm").read_text(encoding="utf-8")
    assert ".const T_ORE3" in asm and "map_tiles:" in asm and "map_objects:" in asm


def test_c64sim_renders_border_and_raster_irq(tmp_path):
    # sei; lda #$35; sta $01; lda #2; sta $d020; jmp *
    code = bytes([0x78, 0xA9, 0x35, 0x85, 0x01, 0xA9, 0x02, 0x8D, 0x20, 0xD0, 0x4C, 0x0A, 0xC0])
    prg = tmp_path / "border.prg"
    prg.write_bytes(b"\x00\xc0" + code)
    res = run_tool("c64sim", prg)
    assert res.ok, res.output
    png = res.first(".png")
    assert png is not None and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.skipif(shutil.which("java") is None, reason="KickAssembler needs Java")
def test_build_tool_runs_steps_and_assembles(tmp_path):
    _copy("map", tmp_path, "ironfront_map.py")
    (tmp_path / "main.asm").write_text(
        'BasicUpstart2(start)\n* = $0810\nstart: inc $d020\n        jmp start\n'
        '* = $2000\n        .import binary "ironfront_charset.bin"\n', encoding="utf-8")
    (tmp_path / "build.py").write_text(
        'STEPS = [("tileset", "ironfront_map.py"), ("asm", "main.asm")]\n', encoding="utf-8")
    res = run_tool("build", tmp_path / "build.py")
    assert res.ok, res.output
    prg = res.first(".prg")
    assert prg == tmp_path / "main.prg" and prg.read_bytes()[:2] == b"\x01\x08"
