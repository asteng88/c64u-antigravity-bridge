import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from c64u_bridge import project
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


def test_iso_tool_builds_charset_lookup_tables_and_map(tmp_path):
    path = project.create_definition("isotiles", tmp_path / "isle.py")
    res = run_tool("isotiles", path)
    assert res.ok, res.output
    assert res.first(".html") == tmp_path / "isle_iso_review.html"
    assert len((tmp_path / "isle_charset.bin").read_bytes()) == 2048
    asm = (tmp_path / "isle_iso.asm").read_text(encoding="utf-8")
    for name in (".const TR_SEA = 0", "terrain_flags:", "iso_chr:", "char_col:", "iso_row_lo:", "iso_map:"):
        assert name in asm, name
    # iso_chr: 4 pages (q*256 + U half*16 + L half), char_col: one colour per screen code
    lines = asm.splitlines()
    chr_rows = lines[lines.index("iso_chr:") + 1:lines.index("char_col:")]
    col_rows = lines[lines.index("char_col:") + 1:lines.index("terrain_flags:")]
    assert sum(r.count("$") for r in chr_rows) == 1024
    assert sum(r.count("$") for r in col_rows if r.startswith("    .byte")) == 256


def test_iso_tool_projects_heights_into_walls(tmp_path):
    path = project.create_definition("isotiles", tmp_path / "hill.py")
    src = path.read_text(encoding="utf-8")
    src += '''

def wall(lx, ly):
    return "#"


TERRAINS += [dict(name="WALL_L", elev=4, flags=1, surface=wall, face=("#", "#"), wall=True),
             dict(name="WALL_R", elev=4, flags=1, surface=wall, face=("#", "#"), wall=True)]
WALLS = ("WALL_L", "WALL_R")


def HEIGHT_AT(i, j):
    return 1 if (i, j) == (8, 32) else 0
'''
    path.write_text(src, encoding="utf-8")
    res = run_tool("isotiles", path)
    assert res.ok, res.output
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "tools" / "isotiles"))
    import iso_tool
    d = iso_tool.load_def(path)
    names = [t["name"] for t in d.TERRAINS]
    vis = iso_tool.project(d, {n: k for k, n in enumerate(names)})
    wl, wr = names.index("WALL_L"), names.index("WALL_R")
    # the raised diamond's own cell shows both walls; its top is drawn two rows up
    assert vis[32][8] == [wl, wr]
    assert vis[30][8] == [names.index(d.TERRAIN_AT(8, 32))] * 2


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


@pytest.mark.skipif(shutil.which("java") is None, reason="KickAssembler needs Java")
def test_heliscape_builds_and_flies_in_the_simulator(tmp_path):
    src = ROOT / "game_dev" / "Heliscape"
    game = tmp_path / "game_dev" / "Heliscape"
    shutil.copytree(src, game, ignore=shutil.ignore_patterns("__pycache__", "*.prg", "*.tap", "*.sym", "*.vs", "*.sid"))
    # the game imports the shared SID driver by a path relative to the repository
    shutil.copytree(ROOT / "tools" / "sid", tmp_path / "tools" / "sid", ignore=shutil.ignore_patterns("__pycache__"))
    res = run_tool("build", game / "build.py")
    assert res.ok, res.output
    prg = game / "heliscape.prg"
    script = tmp_path / "input.json"
    # past the title and the briefing, then lift off and fly east
    script.write_text(
        '[{"frame":60,"joy":"fire","hold":3},{"frame":100,"joy":"fire","hold":3},'
        '{"frame":130,"joy":"up","hold":40},{"frame":170,"joy":"right","hold":200}]', encoding="utf-8")
    sim = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "c64sim" / "c64sim.py"), str(prg),
         "--frames", "400", "--input", str(script), "--shot", "399"],
        capture_output=True, text=True, timeout=300)
    assert sim.returncode == 0, sim.stdout + sim.stderr
    assert (game / "heliscape_f399.png").is_file()


def test_level_tool_writes_tables_records_and_enforces_check(tmp_path):
    level = tmp_path / "lv.py"
    level.write_text(
        'LEVELS = [{"hp": 1, "map": [5, 6]}, {"hp": 2, "map": [7]}]\n'
        'TABLES = [("lv_hp", "hp")]\nRECORDS = [("lv_map", "map")]\n', encoding="utf-8")
    res = run_tool("levels", level)
    assert res.ok, res.output
    asm = (tmp_path / "lv_levels.asm").read_text(encoding="utf-8")
    assert ".const LEVEL_COUNT = 2" in asm and "lv_hp:" in asm and "lv_map_lo:" in asm and "lv_map_1:" in asm
    assert res.first(".html") == tmp_path / "lv_levels_review.html"
    level.write_text('LEVELS = [{"hp": 1}]\nTABLES = [("lv_hp", "hp")]\n'
                     'def CHECK(levels):\n    assert False, "too easy"\n', encoding="utf-8")
    assert not run_tool("levels", level).ok


def test_heliscape_levels_get_harder_every_level():
    # CHECK is what guarantees it; run_tool would fail the build otherwise
    res = run_tool("levels", ROOT / "game_dev" / "Heliscape" / "map" / "heliscape_levels.py")
    assert res.ok, res.output


def test_c64sim_models_cpu_stalls_for_sprites_and_bad_lines():
    sys.path.insert(0, str(ROOT / "tools" / "sim6502"))
    sys.path.insert(0, str(ROOT / "tools" / "c64sim"))
    import c64sim

    m = c64sim.C64()
    m.vic[0x11] = 0x1B
    m.vic[0x15] = 0xFF
    for s in range(8):
        m.vic[1 + 2 * s] = 0
    m.raster = 200              # no sprite here, not a bad line
    assert m.line_stalls() == []
    m.raster = 203              # a bad line: 203 & 7 == 3
    assert m.line_stalls() == [(10, 55)]
    m.vic[1] = 180              # sprite 0 shows on line 201: it fetches at the end of 200
    m.raster = 200
    assert m.line_stalls() == [(55, 63)]
    m.vic[1] = 0
    m.vic[1 + 2 * 7] = 180      # sprite 7 fetches at the start of the line that shows it
    assert m.line_stalls() == [(5, 11)]


def test_c64sim_draws_a_register_change_where_the_beam_was():
    sys.path.insert(0, str(ROOT / "tools" / "sim6502"))
    sys.path.insert(0, str(ROOT / "tools" / "c64sim"))
    import c64sim

    m = c64sim.C64()
    m.render = True
    m.image = [[0] * c64sim.IMG_W for _ in range(c64sim.IMG_H)]
    m.raster = 100
    m.line_cycle = 100 * c64sim.CYCLES_PER_LINE
    m.beam_vic[0x11], m.beam_vic[0x16], m.beam_vic[0x21] = 0x1B, 0x08, 2
    m.vic[0x11], m.vic[0x16] = 0x1B, 0x08
    # a store landing on cycle 26 of the line: 10 cycles, 80 pixels into the window
    m.cycles = m.line_cycle + 27
    m.io_write(0xD021, 5)
    m.end_line()
    line = m.image[100 - c64sim.FIRST_LINE]
    assert line[32 + 79] == 2
    assert line[32 + 80] == 5
    assert m.writes == []


def _hyperload_tape(prg, name="TEST"):
    sys.path.insert(0, str(ROOT / "tools" / "sim6502"))
    sys.path.insert(0, str(ROOT / "tools" / "c64sim"))
    sys.path.insert(0, str(ROOT / "tools" / "hyperload"))
    import c64sim
    import hyperload_tool as tape_tool

    tap, boot, block, code, _ = tape_tool.build_tape(prg, name)
    m = c64sim.C64()
    m.mem[0x0351:0x0351 + len(code)] = code     # where LOAD leaves the header
    m.mem[0x02A7:0x02A7 + len(block)] = block   # and the file
    m.pc, m.sp, m.i = 0x0351, 0xF6, 0
    m.play_tape(tap, boot)
    return m, tap, boot, c64sim, tape_tool


def test_hyperload_tape_loads_a_program_in_the_simulator():
    # SYS 2064, then a program spanning three pages that stores a mark when it runs
    data = bytes.fromhex("0b080a009e3230363400000000") + bytes(2)
    data += bytes.fromhex("a92a8d0002") + b"\x4c\x15\x08" + bytes(range(256)) * 2 + b"end"
    prg = b"\x01\x08" + data
    m, _, _, _, _ = _hyperload_tape(prg)
    for _ in range(400):
        m.run_frame()
        if m.mem[0x200] == 0x2A:
            break
    assert m.mem[0x200] == 0x2A, f"never started, pc=${m.pc:04X}"
    assert bytes(m.mem[0x801:0x801 + len(data)]) == data
    assert m.port & 0x20, "the motor should be off"
    assert m.vic[0x11] & 0x10, "the screen should be back on"


def test_hyperload_tape_stops_on_a_bad_checksum():
    data = bytes.fromhex("0b080a009e3230363400000000") + bytes(2) + bytes.fromhex("4c1008") + bytes(500)
    m, _, boot, _, tape_tool = _hyperload_tape(b"\x01\x08" + data)
    # flip one bit in the second page
    flip = boot + tape_tool.PILOT_BITS + 9 + (256 + 1 + 10) * 8
    m.tape[flip] = (tape_tool.FAST_LONG if m.tape[flip] == tape_tool.FAST_SHORT * 8 else tape_tool.FAST_SHORT) * 8
    for _ in range(300):
        m.run_frame()
    assert m.vic[0x20] & 15 == 2, "the screen should turn red"
    assert m.port & 0x20, "the motor should be off"


def test_hyperload_tape_boot_file_autostarts_through_the_idle_vector(tmp_path):
    sys.path.insert(0, str(ROOT / "src"))
    from c64u_bridge.tap import extract_tap_stages, read_tap_info

    prg = tmp_path / "game.prg"
    prg.write_bytes(b"\x01\x08" + bytes.fromhex("0b080a009e3230363400000000") + bytes(2) + bytes(600))
    res = run_tool("hyperload", prg)
    assert res.ok, res.output
    tap = res.first(".tap").read_bytes()
    assert read_tap_info(tap)["has_correct_size"]
    boot = next(s for s in extract_tap_stages(tap) if s.load_address == 0x02A7)
    idle = 2 + 0x0302 - 0x02A7
    assert boot.prg_data[idle:idle + 2] == bytes([0x51, 0x03])     # $0302 -> the loader at $0351
    assert boot.payload_size == 0x0304 - 0x02A7


def test_hyperload_tape_refuses_programs_it_cannot_load(tmp_path):
    prg = tmp_path / "high.prg"
    prg.write_bytes(b"\x00\xc8" + bytes(0x1000))
    assert not run_tool("hyperload", prg).ok


def test_hyperload_writes_the_path_and_name_it_is_given(tmp_path):
    prg = tmp_path / "game.prg"
    prg.write_bytes(b"\x01\x08" + bytes.fromhex("0b080a009e3230363400000000") + bytes(2) + bytes(600))
    out = tmp_path / "other.tap"
    res = run_tool("hyperload", prg, args=("-o", str(out), "--name", "mygame"))
    assert res.ok, res.output
    assert out.is_file() and not prg.with_suffix(".tap").exists()
    assert b"MYGAME" in _kernal_header(out.read_bytes())


def _kernal_header(tap):
    sys.path.insert(0, str(ROOT / "src"))
    from c64u_bridge.tap import extract_tap_stages

    return extract_tap_stages(tap)[0].name.upper().encode()


# ---------------------------------------------------------------- projects


@pytest.mark.parametrize("kind", ["sprites", "tileset", "isotiles", "koala", "levels"])
def test_every_starter_file_is_recognised_and_builds(tmp_path, kind):
    path = project.create_definition(kind, tmp_path / "first_try.py")
    assert project.classify_file(path) == kind
    res = run_tool(kind, path)
    assert res.ok, res.output


@pytest.mark.skipif(shutil.which("java") is None, reason="KickAssembler needs Java")
def test_starter_song_builds_a_sid_that_plays(tmp_path):
    path = project.create_definition("song", tmp_path / "first_song.py")
    assert project.classify_file(path) == "song"
    res = run_tool("song", path)
    assert res.ok, res.output
    assert res.first(".sid").read_bytes()[:4] == b"PSID"


def test_classify_tells_definitions_from_game_code(tmp_path):
    def kind_of(text):
        return project.classify_source(text)

    assert kind_of('STEPS = [("asm", "a.asm")]') == "build"
    assert kind_of("import math\nborder_color(1)\n") == "python"
    assert kind_of("this is ( not python") == "python"
    for path, want in [("game_dev/Heliscape/build.py", "build"),
                       ("game_dev/Heliscape/sprites/heliscape_sprites.py", "sprites"),
                       ("game_dev/Heliscape/map/heliscape_map.py", "tileset"),
                       ("game_dev/Heliscape/map/heliscape_levels.py", "levels"),
                       ("game_dev/Heliscape/music/heliscape_theme.py", "song"),
                       ("game_dev/Heliscape/heliscape.asm", "asm"),
                       ("game_dev/tornado/map/tornado_iso.py", "isotiles")]:
        assert project.classify_file(ROOT / path) == want, path


def test_find_manifest_looks_up_from_a_game_file_and_stops_at_game_dev():
    src = ROOT / "game_dev" / "Heliscape" / "src" / "irq.asm"
    assert project.find_manifest(src) == ROOT / "game_dev" / "Heliscape" / "build.py"
    assert project.find_manifest(ROOT / "game_dev" / "loose.asm") is None


def test_scan_finds_what_heliscape_really_builds():
    steps = project.scan_steps(ROOT / "game_dev" / "Heliscape")
    assert steps[-1] == ("asm", "heliscape.asm")
    assert steps[0] == ("sprites", "sprites/heliscape_sprites.py")
    assert ("levels", "map/heliscape_levels.py") in steps
    assert sum(1 for tool, _ in steps if tool == "song") == 2


def test_create_game_refuses_to_overwrite(tmp_path):
    manifest = project.create_game("My Game!", tmp_path)
    assert manifest == tmp_path / "my_game" / "build.py"
    with pytest.raises(FileExistsError):
        project.create_game("my game", tmp_path)
    with pytest.raises(ValueError):
        project.create_game("!!!", tmp_path)


def test_create_definition_refuses_to_overwrite(tmp_path):
    path = project.create_definition("levels", tmp_path / "a.py")
    path.write_text("# mine", encoding="utf-8")
    with pytest.raises(FileExistsError):
        project.create_definition("levels", path)
    assert path.read_text(encoding="utf-8") == "# mine"


def test_create_manifest_keeps_an_existing_build_py(tmp_path):
    (tmp_path / "build.py").write_text("# mine\nSTEPS = []\n", encoding="utf-8")
    assert project.create_manifest(tmp_path).read_text(encoding="utf-8").startswith("# mine")


def test_add_step_goes_before_assembly_and_only_once(tmp_path):
    manifest = project.create_game("g", tmp_path)
    target = manifest.parent / "music" / "s.py"
    assert project.add_step(manifest, "song", target)
    assert not project.add_step(manifest, "song", target)
    text = manifest.read_text(encoding="utf-8")
    assert text.count("music/s.py") == 1
    assert text.index("music/s.py") < text.index('("asm", "g.asm")')


# ---------------------------------------------------------------- game check
_GAMECHECK_PROGRAMS = {
    # a sound effect left on: voice 1 gated with sustain, then nothing touches it
    "stuck": """
BasicUpstart2(start)
* = $0810
start:  sei
        lda #$0F
        sta $D418
        lda #$00
        sta $D405
        lda #$F0
        sta $D406
        lda #$20
        sta $D401
        lda #$11
        sta $D404
loop:   jmp loop
""",
    # main code shows a bitmap screen but the raster IRQ keeps writing text mode
    "fight": """
BasicUpstart2(start)
* = $0810
start:  sei
        lda #<irq
        sta $0314
        lda #>irq
        sta $0315
        lda #$7F
        sta $DC0D
        lda #$80
        sta $D012
        lda #$1B
        sta $D011
        lda #$01
        sta $D01A
        cli
        lda #$3B
        sta $D011
loop:   jmp loop
irq:    lda #$1B
        sta $D011
        lda #$01
        sta $D019
        jmp $EA81
""",
    # fine scroll steps 2 px a frame and wraps, but the screen never moves
    "jump": """
BasicUpstart2(start)
* = $0810
start:  sei
        ldx #$00
loop:   lda $D012
        cmp #250
        bne loop
w2:     lda $D012
        cmp #250
        beq w2
        txa
        clc
        adc #$02
        and #$07
        tax
        ora #$08
        sta $D016
        jmp loop
""",
    "clean": """
BasicUpstart2(start)
* = $0810
start:  inc $D020
        jmp start
""",
}


def _build_gamecheck_prg(tmp_path, name):
    src = tmp_path / f"{name}.asm"
    src.write_text(_GAMECHECK_PROGRAMS[name], encoding="utf-8")
    jar = ROOT / "tools" / "kickassembler" / "KickAss.jar"
    subprocess.run(["java", "-jar", str(jar), src.name], cwd=tmp_path, capture_output=True, check=True)
    prg = tmp_path / f"{name}.prg"
    assert prg.is_file()
    return prg


@pytest.mark.skipif(shutil.which("java") is None, reason="KickAssembler needs Java")
@pytest.mark.parametrize("name, finding", [
    ("stuck", "STUCK SOUND voice 1"),
    ("fight", "MODE FIGHT"),
    ("jump", "SCROLL JUMP"),
    ("clean", None),
])
def test_game_check_finds_engine_bugs(tmp_path, name, finding):
    prg = _build_gamecheck_prg(tmp_path, name)
    res = subprocess.run([sys.executable, str(ROOT / "tools" / "gamecheck" / "game_check.py"), str(prg),
                          "--frames", "160"], capture_output=True, text=True)
    report = (tmp_path / f"{name}_check.txt").read_text(encoding="utf-8")
    if finding is None:
        assert res.returncode == 0, res.stdout
        assert "no problems found" in report
    else:
        assert res.returncode == 1, res.stdout
        assert finding in report
        for other in ("STUCK SOUND", "MODE FIGHT", "SCROLL JUMP"):
            if other not in finding:
                assert other not in report, report
