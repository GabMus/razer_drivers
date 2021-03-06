"""
BlackWidow Chroma Effects
"""
from razer_daemon.dbus_services import endpoint

@endpoint('razer.device.lighting.brightness', 'getBrightness', out_sig='d')
def get_brightness(self):
    """
    Get the device's brightness

    :return: Brightness
    :rtype: float
    """
    self.logger.debug("DBus call get_brightness")

    driver_path = self.get_driver_path('set_brightness')

    with open(driver_path, 'r') as driver_file:
        brightness = float(driver_file.read()) * (100.0/255.0)
        return round(brightness, 2)

@endpoint('razer.device.lighting.brightness', 'setBrightness', in_sig='d')
def set_brightness(self, brightness):
    """
    Set the device's brightness

    :param brightness: Brightness
    :type brightness: int
    """
    self.logger.debug("DBus call set_brightness")

    driver_path = self.get_driver_path('set_brightness')

    brightness = int(round(brightness * (255.0/100.0)))
    if brightness > 255:
        brightness = 255
    elif brightness < 0:
        brightness = 0

    with open(driver_path, 'w') as driver_file:
        driver_file.write(str(brightness))

    # Notify others
    self.send_effect_event('setBrightness', brightness)

@endpoint('razer.device.led.gamemode', 'getGameMode', out_sig='b')
def get_game_mode(self):
    """
    Get game mode LED state

    :return: Game mode LED state
    :rtype: bool
    """
    self.logger.debug("DBus call get_game_mode")

    driver_path = self.get_driver_path('mode_game')

    with open(driver_path, 'r') as driver_file:
        return driver_file.read().strip() == '1'

@endpoint('razer.device.led.gamemode', 'setGameMode', in_sig='b')
def set_game_mode(self, enable):
    """
    Set game mode LED state

    :param enable: Status of game mode
    :type enable: bool
    """
    self.logger.debug("DBus call set_game_mode")

    driver_path = self.get_driver_path('mode_game')

    with open(driver_path, 'w') as driver_file:
        if enable:
            driver_file.write('1')
        else:
            driver_file.write('0')

@endpoint('razer.device.led.macromode', 'getMacroMode', out_sig='b')
def get_macro_mode(self):
    """
    Get macro mode LED state

    :return: Status of macro mode
    :rtype: bool
    """
    self.logger.debug("DBus call get_macro_mode")

    driver_path = self.get_driver_path('mode_macro')

    with open(driver_path, 'r') as driver_file:
        return driver_file.read().strip() == '1'

@endpoint('razer.device.led.macromode', 'setMacroMode', in_sig='b')
def set_macro_mode(self, enable):
    """
    Set macro mode LED state

    :param enable: Status of macro mode
    :type enable: bool
    """
    self.logger.debug("DBus call set_macro_mode")

    driver_path = self.get_driver_path('mode_macro')

    with open(driver_path, 'w') as driver_file:
        if enable:
            driver_file.write('1')
        else:
            driver_file.write('0')

@endpoint('razer.device.led.macromode', 'getMacroEffect', out_sig='i')
def get_macro_effect(self):
    """
    Get the effect on the macro LED

    :return: Macro LED effect ID
    :rtype: int
    """
    self.logger.debug("DBus call get_macro_effect")

    driver_path = self.get_driver_path('mode_macro_effect')

    with open(driver_path, 'r') as driver_file:
        return int(driver_file.read().strip())

@endpoint('razer.device.led.macromode', 'setMacroEffect', in_sig='y')
def set_macro_effect(self, effect):
    """
    Set the effect on the macro LED

    :param effect: Macro LED effect ID
    :type effect: int
    """
    self.logger.debug("DBus call set_macro_effect")

    driver_path = self.get_driver_path('mode_macro_effect')

    with open(driver_path, 'w') as driver_file:
        driver_file.write(str(int(effect)))


@endpoint('razer.device.lighting.chroma', 'setWave', in_sig='i')
def set_wave_effect(self, direction):
    """
    Set the wave effect on the device

    :param direction: 1 - left to right, 2 right to left
    :type direction: int
    """
    self.logger.debug("DBus call set_wave_effect")

    # Notify others
    self.send_effect_event('setWave', direction)

    driver_path = self.get_driver_path('mode_wave')

    if direction not in (1, 2):
        direction = 1

    with open(driver_path, 'w') as driver_file:
        driver_file.write(str(direction))

@endpoint('razer.device.lighting.chroma', 'setStatic', in_sig='yyy')
def set_static_effect(self, red, green, blue):
    """
    Set the device to static colour

    :param red: Red component
    :type red: int

    :param green: Green component
    :type green: int

    :param blue: Blue component
    :type blue: int
    """
    self.logger.debug("DBus call set_static_effect")

    # Notify others
    self.send_effect_event('setStatic', red, green, blue)

    driver_path = self.get_driver_path('mode_static')

    payload = bytes([red, green, blue])

    with open(driver_path, 'wb') as driver_file:
        driver_file.write(payload)

@endpoint('razer.device.lighting.chroma', 'setSpectrum')
def set_spectrum_effect(self):
    """
    Set the device to spectrum mode
    """
    self.logger.debug("DBus call set_spectrum_effect")

    # Notify others
    self.send_effect_event('setSpectrum')

    driver_path = self.get_driver_path('mode_spectrum')

    with open(driver_path, 'w') as driver_file:
        driver_file.write('1')

@endpoint('razer.device.lighting.chroma', 'setNone')
def set_none_effect(self):
    """
    Set the device to spectrum mode
    """
    self.logger.debug("DBus call set_none_effect")

    # Notify others
    self.send_effect_event('setNone')

    driver_path = self.get_driver_path('mode_none')

    with open(driver_path, 'w') as driver_file:
        driver_file.write('1')

@endpoint('razer.device.lighting.chroma', 'setReactive', in_sig='yyyy')
def set_reactive_effect(self, red, green, blue, speed):
    """
    Set the device to reactive effect

    :param red: Red component
    :type red: int

    :param green: Green component
    :type green: int

    :param blue: Blue component
    :type blue: int

    :param speed: Speed
    :type speed: int
    """
    self.logger.debug("DBus call set_reactive_effect")

    driver_path = self.get_driver_path('mode_reactive')

    # Notify others
    self.send_effect_event('setReactive', red, green, blue, speed)

    if speed not in (1, 2, 3, 4):
        speed = 4

    payload = bytes([red, green, blue, speed])

    with open(driver_path, 'wb') as driver_file:
        driver_file.write(payload)

@endpoint('razer.device.lighting.chroma', 'setBreathRandom')
def set_breath_random_effect(self):
    """
    Set the device to random colour breathing effect
    """
    self.logger.debug("DBus call set_breath_random_effect")

    # Notify others
    self.send_effect_event('setBreathRandom')

    driver_path = self.get_driver_path('mode_breath')

    payload = b'1'

    with open(driver_path, 'wb') as driver_file:
        driver_file.write(payload)

@endpoint('razer.device.lighting.chroma', 'setBreathSingle', in_sig='yyy')
def set_breath_single_effect(self, red, green, blue):
    """
    Set the device to single colour breathing effect

    :param red: Red component
    :type red: int

    :param green: Green component
    :type green: int

    :param blue: Blue component
    :type blue: int
    """
    self.logger.debug("DBus call set_breath_single_effect")

    # Notify others
    self.send_effect_event('setBreathSingle', red, green, blue)

    driver_path = self.get_driver_path('mode_breath')

    payload = bytes([red, green, blue])

    with open(driver_path, 'wb') as driver_file:
        driver_file.write(payload)

@endpoint('razer.device.lighting.chroma', 'setBreathDual', in_sig='yyyyyy')
def set_breath_dual_effect(self, red1, green1, blue1, red2, green2, blue2):
    """
    Set the device to dual colour breathing effect

    :param red1: Red component
    :type red1: int

    :param green1: Green component
    :type green1: int

    :param blue1: Blue component
    :type blue1: int

    :param red2: Red component
    :type red2: int

    :param green2: Green component
    :type green2: int

    :param blue2: Blue component
    :type blue2: int
    """
    self.logger.debug("DBus call set_breath_dual_effect")

    # Notify others
    self.send_effect_event('setBreathDual', red1, green1, blue1, red2, green2, blue2)

    driver_path = self.get_driver_path('mode_breath')

    payload = bytes([red1, green1, blue1, red2, green2, blue2])

    with open(driver_path, 'wb') as driver_file:
        driver_file.write(payload)

@endpoint('razer.device.lighting.chroma', 'setCustom')
def set_custom_effect(self):
    """
    Set the device to use custom LED matrix
    """
    # TODO uncomment
    # self.logger.debug("DBus call set_custom_effect")

    driver_path = self.get_driver_path('mode_custom')

    payload = b'1'

    with open(driver_path, 'wb') as driver_file:
        driver_file.write(payload)

@endpoint('razer.device.lighting.chroma', 'setKeyRow', in_sig='ay', byte_arrays=True)
def set_key_row(self, payload):
    """
    Set the RGB matrix on the device

    Byte array like
    [1, 255, 255, 00, 255, 255, 00, 255, 255, 00, 255, 255, 00, 255, 255, 00, 255, 255, 00, 255, 255, 00, 255, 255, 00,
        255, 255, 00, 255, 255, 00, 255, 255, 00, 255, 255, 00, 255, 255, 00, 255, 255, 00, 255, 00, 00]

    First byte is row, on firefly its always 1, on keyboard its 0-5
    Then its 3byte groups of RGB
    :param payload: Binary payload
    :type payload: bytes
    """

    # TODO uncomment
    # self.logger.debug("DBus call set_key_row")

    driver_path = self.get_driver_path('set_key_row')

    with open(driver_path, 'wb') as driver_file:
        driver_file.write(payload)

# Not sure if works on firefly
@endpoint('razer.device.lighting.chroma', 'clearKeyRow', in_sig='y')
def clear_key_row(self, row_id):
    """
    Clear the RGB matrix on the device

    :param row_id: Row ID
    :type row_id: int
    """
    self.logger.debug("DBus call clear_key_row")

    driver_path = self.get_driver_path('temp_clear_row')

    with open(driver_path, 'w') as driver_file:
        driver_file.write(str(int(row_id)))



@endpoint('razer.device.lighting.custom', 'setRipple', in_sig='yyyd')
def set_ripple_effect(self, red, green, blue, refresh_rate):
    """
    Set the daemon to serve a ripple effect of the specified colour

    :param red: Red component
    :type red: int

    :param green: Green component
    :type green: int

    :param blue: Blue component
    :type blue: int

    :param refresh_rate: Refresh rate
    :type refresh_rate: int
    """
    self.logger.debug("DBus call set_ripple_effect")

    # Notify others
    self.send_effect_event('setRipple', red, green, blue, refresh_rate)

@endpoint('razer.device.lighting.custom', 'setRippleRandomColour', in_sig='d')
def set_ripple_effect_random_colour(self, refresh_rate):
    """
    Set the daemon to serve a ripple effect of random colours

    :param refresh_rate: Refresh rate
    :type refresh_rate: int
    """
    self.logger.debug("DBus call set_ripple_effect")

    # Notify others
    self.send_effect_event('setRipple', None, None, None, refresh_rate)

