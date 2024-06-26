
def get_radiohead_ID(
    board_num: int
) -> int:
    """Return the radiohead ID of a given board"""
    
    # hard-coded board addresses
    board_ids = [0xA0, 0xB3, 0xC6, 0xD9, 0xEC]
    return board_ids[board_num-1]


def update_led(
    satellite, 
    r: int = 0, 
    g: int = 255, 
    b: int = 0, 
    brightness: float = 0.5
) -> None:
    """Set the PyCubed RGB LED's colour and brightness."""
    assert 0 <= r <= 255
    assert 0 <= g <= 255
    assert 0 <= b <= 255
    assert 0.0 <= brightness <= 1.0
    
    satellite.RGB = (r, g, b)
    satellite.neopixel.brightness = brightness