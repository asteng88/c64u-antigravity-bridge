"""
HELISCAPE title theme - song file for tools/sid/song_tool.py.

D Phrygian dominant, built on the D-Eb-F#-G-A-Bb motif of the original game.
One pattern row = one sixteenth note at the driver's fixed 125 BPM.
  Voice 1  bass    driving filtered pulse, rotor-like eighth-note pedal
  Voice 2  lead    the motif on a singing pulse with PWM and vibrato
  Voice 3  drums   kick and snare with a tom fill

Build:  python tools/sid/song_tool.py game_dev/Heliscape/music/heliscape_theme.py --build
"""
from song_tool import bar, drum_bar

TITLE = "HELISCAPE title theme"
ASM = "music.asm"
SID = dict(name="HELISCAPE", author="Andrew Thomas", released="2026 HELISCAPE", file="heliscape_title.sid")

INSTRUMENTS = {
    "lead": dict(ad=0x37, sr=0xA8, pw=0x0500, pws=0x30, vib=1, wave=[(0x41, 12), (0x41, 0)], loop=None),
    "pad": dict(ad=0x89, sr=0x87, pw=0x0800, pws=0x18, vib=1, wave=[(0x41, 0)], loop=None),
    "bass": dict(ad=0x05, sr=0x88, pw=0x0300, pws=0x20, vib=0, wave=[(0x81, ("abs", 70)), (0x41, 0)], loop=None),
    "kick": dict(ad=0x08, sr=0x00, pw=0x0800, pws=0, vib=0,
                 wave=[(0x81, ("abs", 60)), (0x41, ("abs", 40)), (0x41, ("abs", 34)),
                       (0x41, ("abs", 29)), (0x41, ("abs", 25)), (0x40, ("abs", 22))], loop=None),
    "snare": dict(ad=0x07, sr=0x00, pw=0x0800, pws=0, vib=0,
                  wave=[(0x81, ("abs", 92)), (0x41, ("abs", 52)), (0x41, ("abs", 49)),
                        (0x81, ("abs", 88)), (0x81, ("abs", 86))], loop=None),
    "hat": dict(ad=0x02, sr=0x00, pw=0x0800, pws=0, vib=0, wave=[(0x81, ("abs", 94)), (0x80, ("abs", 94))], loop=None),
    "tom": dict(ad=0x08, sr=0x00, pw=0x0800, pws=0, vib=0,
                wave=[(0x81, ("abs", 66)), (0x41, ("abs", 48)), (0x41, ("abs", 45)), (0x41, ("abs", 42)),
                      (0x41, ("abs", 40)), (0x40, ("abs", 38))], loop=None),
}

FILTER_CUTOFF = 0x48
FILTER_ROUTING = 0x51   # resonance 5, filter voice 1 (bass)

KIT = {"K": "kick", "S": "snare", "h": "hat", "T": "tom"}

PATTERNS = {
    "rest": bar("lead", ("-", 16)),
    "bass_rest": bar("bass", ("-", 16)),
    # rotor pedal: root on every eighth with an octave kick on the off-beat of 4
    "bass_d": bar("bass", ("D3", 2), ("D3", 2), ("D3", 2), ("D3", 1), ("D3", 1),
                  ("D3", 2), ("D3", 2), ("D4", 2), ("D3", 2)),
    "bass_up": bar("bass", ("D3", 2), ("D3", 2), ("Eb3", 2), ("Eb3", 2), ("F#3", 2), ("F#3", 2), ("G3", 2), ("A3", 2)),

    "drum_in": drum_bar("h2 h2 h2 h2 h2 h2 T1 T1 T2", KIT),
    "drum_a": drum_bar("K2 h2 S2 h2 K2 K2 S2 h2", KIT),
    "drum_b": drum_bar("K2 h2 S2 h1 K1 h2 K2 S1 S1 T2", KIT),
    "drum_fill": drum_bar("K2 S2 T2 T1 T1 S1 S1 T1 T1 S1 S1 T1 T1", KIT),

    "lead_a": (
        bar("lead", ("D5", 4), ("Eb5", 2), ("F#5", 4), ("G5", 2), ("F#5", 2), ("Eb5", 2))
        + bar("lead", ("D5", 6), ("A4", 2), ("Bb4", 2), ("A4", 2), ("F#4", 4))
        + bar("lead", ("G4", 4), ("A4", 2), ("Bb4", 4), ("D5", 2), ("Eb5", 2), ("D5", 2))
        + bar("lead", ("A4", 12), ("-", 4))
        + bar("lead", ("D5", 4), ("Eb5", 2), ("F#5", 4), ("G5", 2), ("A5", 2), ("Bb5", 2))
        + bar("lead", ("A5", 6), ("G5", 2), ("F#5", 2), ("Eb5", 2), ("F#5", 4))
        + bar("lead", ("G5", 3), ("F#5", 1), ("Eb5", 4), ("D5", 2), ("Eb5", 2), ("Bb4", 4))
        + bar("lead", ("D5", 12), ("-", 4))
    ),
    "lead_b": (
        bar("pad", ("A5", 16))
        + bar("pad", ("Bb5", 8), ("A5", 8))
        + bar("pad", ("G5", 16))
        + bar("pad", ("F#5", 8), ("Eb5", 8))
        + bar("lead", ("D5", 2), ("F#5", 2), ("A5", 2), ("D6", 2), ("Eb6", 4), ("D6", 2), ("Bb5", 2))
        + bar("lead", ("A5", 2), ("F#5", 2), ("Eb5", 2), ("D5", 2), ("Eb5", 4), ("F#5", 4))
        + bar("lead", ("G5", 4), ("F#5", 2), ("Eb5", 2), ("D5", 4), ("Bb4", 4))
        + bar("lead", ("A4", 4), ("Eb5", 4), ("D5", 8))
    ),
}

CHORD_SHIFT = [0, 0, -5, -5, 0, 0, -7, 0]   # D D A A D D G D (phrygian-flavoured roots)
CHORD_B = [0, 1, -7, -7, 0, 0, -7, 0]


def bass_order():
    seq = ["bass_rest"]
    loop = 1
    for shift in CHORD_SHIFT:
        seq += [("T", shift), "bass_d"]
    for i, shift in enumerate(CHORD_B):
        seq += [("T", shift), "bass_up" if i == 7 else "bass_d"]
    return seq, loop


def drum_order():
    half = ["drum_a", "drum_b"] * 3 + ["drum_a", "drum_fill"]
    return ["drum_in"] + half + half, 1


ORDERS = [bass_order(), (["rest", "lead_a", "lead_b"], 1), drum_order()]
SIM_FRAMES = 17 * 16 * 6
