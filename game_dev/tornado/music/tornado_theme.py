"""
TORNADO title theme - song file for tools/sid/song_tool.py.

C minor 80s rescue-chopper synth action theme, 132 BPM, 16th-note rows.
  Voice 1  bass   driving octave pulse bass, filtered
  Voice 2  lead   soaring heroic pulse lead with PWM and vibrato
  Voice 3  drums  kick, snare, hi-hat
"""
from song_tool import bar, drum_bar

TITLE = "TORNADO title theme"
ASM = "music.asm"
SID = dict(name="TORNADO Title Theme", author="Antigravity", released="2026 TORNADO",
           file="tornado_title.sid")

INSTRUMENTS = {
    "lead":  dict(ad=0x16, sr=0xA8, pw=0x0600, pws=0x30, vib=1,
                  wave=[(0x41, 12), (0x41, 0)], loop=None),
    "bass":  dict(ad=0x05, sr=0x86, pw=0x0400, pws=0x20, vib=0,
                  wave=[(0x81, ("abs", 70)), (0x41, 0)], loop=None),
    "kick":  dict(ad=0x08, sr=0x00, pw=0x0800, pws=0, vib=0,
                  wave=[(0x81, ("abs", 62)), (0x41, ("abs", 42)), (0x41, ("abs", 34)),
                        (0x41, ("abs", 28)), (0x40, ("abs", 22))], loop=None),
    "snare": dict(ad=0x07, sr=0x00, pw=0x0800, pws=0, vib=0,
                  wave=[(0x81, ("abs", 92)), (0x41, ("abs", 52)), (0x81, ("abs", 88)),
                        (0x81, ("abs", 84))], loop=None),
    "hat":   dict(ad=0x03, sr=0x00, pw=0x0800, pws=0, vib=0,
                  wave=[(0x81, ("abs", 95)), (0x80, ("abs", 92))], loop=None),
}

FILTER_CUTOFF = 0x58
FILTER_ROUTING = 0x51   # resonance 5, filter voice 1 (bass)

KIT = {"K": "kick", "S": "snare", "h": "hat"}

PATTERNS = {
    "rest":      bar("lead", ("-", 16)),
    "bass_rest": bar("bass", ("-", 16)),
    "bass_drive": bar("bass", ("C3", 2), ("C4", 2), ("C3", 2), ("C4", 2),
                      ("C3", 2), ("C4", 2), ("C3", 2), ("G3", 2)),
    "bass_turn":  bar("bass", ("C3", 2), ("C4", 2), ("D3", 2), ("Eb3", 2),
                      ("F3", 2), ("G3", 2), ("Ab3", 2), ("Bb3", 2)),

    "drum_intro": drum_bar("K2 h2 S2 h2 K2 h2 S1 h1 S2", KIT),
    "drum_main":  drum_bar("K2 h2 S2 h2 K1 K1 h2 S2 h2", KIT),
    "drum_fill":  drum_bar("K2 h2 S2 h2 K2 S2 S1 S1 S2", KIT),

    "lead_a": (
        bar("lead", ("G4", 4), ("C5", 4), ("D5", 2), ("Eb5", 2), ("D5", 4))
        + bar("lead", ("C5", 4), ("G4", 4), ("Bb4", 4), ("G4", 4))
        + bar("lead", ("Ab4", 4), ("C5", 4), ("Eb5", 2), ("F5", 2), ("Eb5", 4))
        + bar("lead", ("D5", 8), ("G4", 4), ("B4", 4))
        + bar("lead", ("G4", 4), ("C5", 4), ("D5", 2), ("Eb5", 2), ("F5", 4))
        + bar("lead", ("G5", 6), ("F5", 2), ("Eb5", 4), ("D5", 4))
        + bar("lead", ("C5", 4), ("Eb5", 4), ("D5", 4), ("B4", 4))
        + bar("lead", ("C5", 12), ("-", 4))
    ),
    "lead_b": (
        bar("lead", ("Eb5", 4), ("Eb5", 2), ("F5", 2), ("G5", 4), ("Eb5", 4))
        + bar("lead", ("D5", 4), ("D5", 2), ("Eb5", 2), ("F5", 4), ("D5", 4))
        + bar("lead", ("C5", 4), ("C5", 2), ("D5", 2), ("Eb5", 4), ("C5", 4))
        + bar("lead", ("D5", 4), ("G4", 4), ("B4", 4), ("D5", 4))
        + bar("lead", ("C5", 4), ("G4", 4), ("Eb5", 4), ("D5", 4))
        + bar("lead", ("C5", 4), ("Bb4", 4), ("Ab4", 4), ("G4", 4))
        + bar("lead", ("F4", 4), ("Ab4", 4), ("G4", 4), ("B4", 4))
        + bar("lead", ("C5", 10), ("-", 6))
    ),
}

CHORDS = ["Cm", "Cm", "Ab", "G", "Cm", "Eb", "G", "Cm",
          "Eb", "Bb", "Cm", "G", "Cm", "Ab", "Fm", "G"]
SHIFT = {"Cm": 0, "Eb": 3, "Ab": -4, "Bb": -2, "Fm": -7, "G": -5}


def bass_order():
    seq = ["bass_rest"]
    loop = len(seq)
    for i, ch in enumerate(CHORDS):
        seq += [("T", SHIFT[ch]), "bass_turn" if i in (7, 15) else "bass_drive"]
    return seq, loop


def drum_order():
    seq = ["drum_intro"]
    loop = len(seq)
    half = ["drum_main", "drum_main", "drum_main", "drum_fill"] * 2
    return seq + half + half, loop


ORDERS = [bass_order(), (["rest", "lead_a", "lead_b"], 1), drum_order()]
SIM_FRAMES = (1 + len(CHORDS)) * 16 * 6
