"""
Commodore 64 Rainbow Raster Bars
Written in Python for the C64U Python-to-6502 Bridge!
"""

# Wait for raster beam and cycle border colors
while True:
    wait_raster(50)
    border_color(COLOR_RED)

    wait_raster(70)
    border_color(COLOR_ORANGE)

    wait_raster(90)
    border_color(COLOR_YELLOW)

    wait_raster(110)
    border_color(COLOR_GREEN)

    wait_raster(130)
    border_color(COLOR_CYAN)

    wait_raster(150)
    border_color(COLOR_BLUE)

    wait_raster(170)
    border_color(COLOR_PURPLE)

    wait_raster(250)
    border_color(COLOR_BLACK)
