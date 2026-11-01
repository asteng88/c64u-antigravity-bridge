"""
HELISCAPE game over tune - song file for tools/sid/song_tool.py.

An arrangement of the Funeral March from Chopin's Piano Sonata No. 2 (1839, public
domain), in B-flat minor. One pattern row = one sixteenth note at the driver's fixed
125 BPM, so a slow quarter note takes 8 rows and a 4/4 bar takes 32.
  Voice 1  chords   the rocking left hand, fast arpeggios through the filter
  Voice 2  lead     the melody on a hollow pulse with vibrato
  Voice 3  drum     muffled drum on 1 and 3, a snare roll into each phrase

Build:  python tools/sid/song_tool.py game_dev/Heliscape/music/death/death_march.py --build
"""
from song_tool import bar

TITLE = "HELISCAPE game over"
ASM = "music.asm"
SID = dict(name="HELISCAPE Game Over", author="F. Chopin, arr. Andrew Thomas", released="2026 HELISCAPE",
           file="heliscape_gameover.sid")
BAR = 32

INSTRUMENTS = {
    "lead": dict(ad=0x46, sr=0x98, pw=0x0300, pws=0x14, vib=1, wave=[(0x41, 0)], loop=None),
    "minor": dict(ad=0x28, sr=0x88, pw=0x0600, pws=0x10, vib=0,
                  wave=[(0x41, 0), (0x41, 3), (0x41, 7)], loop=0),
    "major": dict(ad=0x28, sr=0x88, pw=0x0600, pws=0x10, vib=0,
                  wave=[(0x41, 0), (0x41, 4), (0x41, 7)], loop=0),
    "drum": dict(ad=0x09, sr=0x00, pw=0x0800, pws=0, vib=0,
                 wave=[(0x81, ("abs", 50)), (0x41, ("abs", 32)), (0x41, ("abs", 28)), (0x41, ("abs", 25)),
                       (0x41, ("abs", 22)), (0x40, ("abs", 20))], loop=None),
    "roll": dict(ad=0x03, sr=0x00, pw=0x0800, pws=0, vib=0,
                 wave=[(0x81, ("abs", 88)), (0x81, ("abs", 84)), (0x80, ("abs", 84))], loop=0),
}

FILTER_CUTOFF = 0x38
FILTER_ROUTING = 0x41   # resonance 4, filter voice 1 (chords)


def rock(a_inst, a, b_inst, b):
    """Four quarter notes rocking between two chords."""
    return (bar(a_inst, (a, 8), rows=8) + bar(b_inst, (b, 8), rows=8)) * 2


def phrase(a, b, c, d, e):
    """The march's rhythm: long, dotted pair, long, dotted pair / two dotted pairs, held."""
    return (bar("lead", (a, 8), (a, 6), (a, 2), (a, 8), (b, 6), (c, 2), rows=BAR)
            + bar("lead", (c, 6), (a, 2), (a, 6), (d, 2), (a, 12), ("-", 4), rows=BAR)) if e is None else (
            bar("lead", (a, 8), (a, 6), (a, 2), (a, 8), (b, 6), (c, 2), rows=BAR)
            + bar("lead", (c, 6), (a, 2), (a, 6), (d, 2), (e, 12), ("-", 4), rows=BAR))


PATTERNS = {
    "rest": bar("lead", ("-", 32), rows=BAR),
    "bbm": rock("minor", "Bb2", "major", "Gb2"),
    "dbm": rock("major", "Db3", "major", "Ab2"),
    "drums": (bar("drum", ("C4", 16), rows=16) + bar("drum", ("C4", 16), rows=16)),
    "drums_in": (bar("drum", ("C4", 16), rows=16) + bar("drum", ("C4", 8), rows=8) + bar("roll", ("C4", 8), rows=8)),
    "lead_a": phrase("Bb4", "Db5", "C5", "A4", None),
    "lead_b": phrase("Db5", "F5", "Eb5", "C5", None),
    "lead_end": (bar("lead", ("Bb4", 8), ("Bb4", 6), ("Bb4", 2), ("Bb4", 8), ("Db5", 6), ("C5", 2), rows=BAR)
                 + bar("lead", ("C5", 6), ("Bb4", 2), ("Bb4", 6), ("A4", 2), ("Bb4", 16), rows=BAR)),
}

# two bars of chords alone, then A A B A, then round again
ORDERS = [
    (["bbm", "bbm"] + ["bbm"] * 4 + ["bbm", "bbm"] + ["dbm", "dbm"] + ["bbm", "bbm"], 0),
    (["rest", "rest", "lead_a", "lead_a", "lead_b", "lead_end"], 0),
    (["drums", "drums_in"] + ["drums", "drums", "drums", "drums_in"] * 3, 0),
]
SIM_FRAMES = 12 * BAR * 6
