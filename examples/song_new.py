"""
SONG NEW song - build with F7: writes the music data and a .sid. F5 plays it on the C64U.

One pattern row = one sixteenth note at the driver's fixed 125 BPM.
"""
TITLE = "SONG NEW"
ASM = "music.asm"
SID = dict(name="SONG NEW", author="", released="", file="song_new.sid")

INSTRUMENTS = {
    "lead": dict(ad=0x37, sr=0xA8, pw=0x0500, pws=0x30, vib=1, wave=[(0x41, 0)], loop=None),
    "bass": dict(ad=0x05, sr=0x88, pw=0x0300, pws=0x20, vib=0, wave=[(0x41, 0)], loop=None),
}

# (instrument, note or None for a rest, rows)
PATTERNS = {
    "melody": [("lead", "C5", 4), ("lead", "E5", 4), ("lead", "G5", 4), ("lead", "E5", 4)],
    "bassline": [("bass", "C3", 8), ("bass", "G2", 8)],
    "rest": [("lead", None, 16)],
}

# one (sequence of patterns, position to loop back to) per voice
ORDERS = [
    (["melody"], 0),
    (["bassline"], 0),
    (["rest"], 0),
]
FILTER_CUTOFF = 0x60
FILTER_ROUTING = 0x00
SIM_FRAMES = 300
