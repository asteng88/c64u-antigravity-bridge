// Music block: driver + song. music_init = $1000, music_play = $1003.
#import "music_config.asm"

* = $1000 "Music"
#import "../tools/sid/sid_player.asm"
#import "music_data.asm"
