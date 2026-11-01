// HELISCAPE game over tune: driver + song, for testing on its own and the .sid export.
// heliscape.asm imports the driver and the song data inside a `death` scope.

#import "music_config.asm"

* = $1000 "Music"
#import "../../../../tools/sid/sid_player.asm"
#import "music_data.asm"
