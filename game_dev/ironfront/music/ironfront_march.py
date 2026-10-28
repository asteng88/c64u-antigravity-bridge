"""
IRONFRONT title march - song file for tools/sid/song_tool.py.

D minor military march, 125 BPM, one pattern row = one sixteenth note.
  Voice 1  bass      oom-pah root/fifth, filtered, transposed per chord
  Voice 2  lead      brass-style pulse with a bright attack, PWM and vibrato
  Voice 3  drums     kick, snare, ghost snare and real retriggered snare rolls

Build:  python tools/sid/song_tool.py game_dev/ironfront/music/ironfront_march.py --build
"""
from song_tool import bar, drum_bar

TITLE = "IRONFRONT title march"
ASM = "music.asm"
SID = dict(name="IRONFRONT Title March", author="Andrew Thomas", released="2026 IRONFRONT",
           file="ironfront_title.sid")

# ---------------------------------------------------------------- instruments
INSTRUMENTS = {
    "lead":  dict(ad=0x26, sr=0xA9, pw=0x0600, pws=0x28, vib=1,
                  wave=[(0x41, 12), (0x41, 0)], loop=None),
    "bass":  dict(ad=0x06, sr=0x98, pw=0x0400, pws=0x18, vib=0,
                  wave=[(0x81, ("abs", 72)), (0x41, 0)], loop=None),
    "kick":  dict(ad=0x08, sr=0x00, pw=0x0800, pws=0, vib=0,
                  wave=[(0x81, ("abs", 60)), (0x41, ("abs", 40)), (0x41, ("abs", 34)),
                        (0x41, ("abs", 29)), (0x41, ("abs", 25)), (0x40, ("abs", 22))], loop=None),
    "snare": dict(ad=0x07, sr=0x00, pw=0x0800, pws=0, vib=0,
                  wave=[(0x81, ("abs", 92)), (0x41, ("abs", 52)), (0x41, ("abs", 49)),
                        (0x81, ("abs", 88)), (0x81, ("abs", 86))], loop=None),
    "ghost": dict(ad=0x04, sr=0x00, pw=0x0800, pws=0, vib=0,
                  wave=[(0x81, ("abs", 90)), (0x81, ("abs", 86))], loop=None),
    "roll":  dict(ad=0x04, sr=0x00, pw=0x0800, pws=0, vib=0,
                  wave=[(0x81, ("abs", 92)), (0x81, ("abs", 88)), (0x80, ("abs", 88))], loop=0),
}

FILTER_CUTOFF = 0x50
FILTER_ROUTING = 0x61   # resonance 6, filter voice 1 (bass)

# ---------------------------------------------------------------- patterns
KIT = {"K": "kick", "S": "snare", "s": "ghost", "R": "roll"}

PATTERNS = {
    "rest":     bar("lead", ("-", 16)),
    "bass_rest": bar("bass", ("-", 16)),
    # root on 1 and 3, fifth below on 2 and 4, short and punchy
    "bass_march": bar("bass", ("D3", 2), ("-", 2), ("A2", 2), ("-", 2), ("D3", 2), ("-", 2), ("A2", 2), ("-", 2)),
    "bass_walk":  bar("bass", ("D3", 2), ("-", 2), ("A2", 2), ("-", 2), ("D3", 2), ("E3", 2), ("F3", 2), ("A3", 2)),

    "drum_intro1": drum_bar("R16", KIT),
    "drum_intro2": drum_bar("R8 S2 S2 S2 S2", KIT),
    "drum_march":  drum_bar("K2 s1 s1 S2 s2 K2 s1 s1 S1 s1 R2", KIT),
    "drum_march2": drum_bar("K2 s1 s1 S2 s1 s1 K1 K1 s1 s1 S1 S1 S2", KIT),
    "drum_fill":   drum_bar("S1 s1 S1 s1 R4 S1 S1 S1 S1 R2 S2", KIT),

    "lead_a": (
        bar("lead", ("A4", 3), ("A4", 1), ("D5", 4), ("A4", 4), ("F4", 4))
        + bar("lead", ("D5", 3), ("E5", 1), ("F5", 4), ("E5", 2), ("D5", 2), ("C#5", 4))
        + bar("lead", ("D5", 6), ("C5", 2), ("Bb4", 4), ("A4", 4))
        + bar("lead", ("G4", 3), ("A4", 1), ("Bb4", 4), ("A4", 8))
        + bar("lead", ("A4", 3), ("A4", 1), ("D5", 4), ("F5", 4), ("A5", 4))
        + bar("lead", ("Bb5", 6), ("A5", 2), ("G5", 4), ("F5", 4))
        + bar("lead", ("E5", 3), ("F5", 1), ("G5", 4), ("F5", 2), ("E5", 2), ("C#5", 4))
        + bar("lead", ("D5", 12), ("-", 4))
    ),
    "lead_b": (
        bar("lead", ("F5", 3), ("F5", 1), ("F5", 4), ("D5", 4), ("Bb4", 4))
        + bar("lead", ("C5", 3), ("C5", 1), ("C5", 4), ("A4", 4), ("F4", 4))
        + bar("lead", ("E5", 3), ("E5", 1), ("G5", 4), ("E5", 4), ("C5", 4))
        + bar("lead", ("C#5", 4), ("E5", 4), ("A5", 8))
        + bar("lead", ("A5", 3), ("G5", 1), ("F5", 4), ("E5", 2), ("D5", 2), ("A4", 4))
        + bar("lead", ("Bb4", 3), ("C5", 1), ("D5", 4), ("G5", 4), ("Bb5", 4))
        + bar("lead", ("A5", 6), ("G5", 2), ("F5", 2), ("E5", 2), ("C#5", 4))
        + bar("lead", ("D5", 8), ("-", 8))
    ),
}

# ---------------------------------------------------------------- arrangement
# chord roots per bar after the 2-bar drum intro: A section, then B section
CHORDS = ["Dm", "Dm", "Bb", "A", "Dm", "Gm", "A", "Dm",
          "Bb", "F", "C", "A", "Dm", "Gm", "A", "Dm"]
SHIFT = {"Dm": 0, "Bb": -4, "A": -5, "Gm": -7, "F": -9, "C": -2}


def bass_order():
    seq = ["bass_rest", "bass_rest"]
    loop = len(seq)
    for i, ch in enumerate(CHORDS):
        seq += [("T", SHIFT[ch]), "bass_walk" if i in (7, 15) else "bass_march"]
    return seq, loop


def drum_order():
    seq = ["drum_intro1", "drum_intro2"]
    loop = len(seq)
    half = ["drum_march", "drum_march2"] * 3 + ["drum_march", "drum_fill"]
    return seq + half + half, loop


ORDERS = [bass_order(), (["rest", "rest", "lead_a", "lead_b"], 2), drum_order()]

# one pass of the song (intro + 16 bars) is all the review page needs
SIM_FRAMES = (2 + len(CHORDS)) * 16 * 6

# arrangement summary for the review page
SUMMARY = {
    "bpm": 125, "bars": 2 + len(CHORDS), "loopBar": 3, "key": "D minor",
    "chords": ["", ""] + CHORDS,
    "voices": [
        {"name": "Bass", "role": "Filtered pulse, oom-pah root and fifth",
         "bars": ["rest"] * 2 + ["march"] * 7 + ["walk"] + ["march"] * 7 + ["walk"]},
        {"name": "Lead", "role": "Brass-style pulse, PWM and vibrato", "bars": ["rest"] * 2 + ["A"] * 8 + ["B"] * 8},
        {"name": "Drums", "role": "Kick, snare, ghost notes, snare rolls",
         "bars": ["roll", "roll"] + (["march", "alt"] * 3 + ["march", "fill"]) * 2},
    ],
}
