"""
Receives events from /dev/input/by-id/somedevice

Events are 24 bytes long and are emitted from a character device in 24 byte chunks.
As the keyboards have "2" keyboard interfaces we need to listen on both of them incase some n00b
switches to game mode.

Each event is in the format of
* signed int of seconds
* signed int of microseconds
* unsigned short of event type
* unsigned short code
* signed int value
"""
import datetime
import fcntl
import json
import logging
import os
import time
import threading
import random
import select
import struct
import subprocess

# pylint: disable=import-error
from razer.keyboard import KEY_MAPPING, EVENT_MAPPING
from .macro import MacroKey, MacroRunner, macro_dict_to_obj

EVENT_FORMAT = '@llHHI'
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

EPOLL_TIMEOUT = 0.01

EVIOCGRAB = 0x40044590

COLOUR_CHOICES = (
    (255, 0, 0), # Red
    (0, 255, 0), # Green
    (0, 0, 255), # Blue
    (255, 255, 0), # Yellow
    (0, 255, 255), # Cyan
    (255, 0, 255), # Magenta
)

MEDIA_KEY_MAP = {
    'vol_mute': 'XF86AudioMute',
    'vol_up': 'XF86AudioRaiseVolume',
    'vol_down': 'XF86AudioLowerVolume',
    'media_play': 'XF86AudioPlay',
    'media_prev': 'XF86AudioPrev',
    'media_next': 'XF86AudioNext'
}


def random_colour_picker(last_choice, iterable):
    """
    Chose a random choice but not the last one

    :param last_choice: Last choice
    :type last_choice: object

    :param iterable: Iterable object
    :type iterable: iterable

    :return: Choice
    :rtype: object
    """
    result = random.choice(iterable)
    while result == last_choice:
        result = random.choice(iterable)
    return result


class KeyWatcher(threading.Thread):
    """
    Thread to watch keyboard event files and return keypresses
    """
    @staticmethod
    def parse_event_record(data):
        """
        Parse Input event record

        :param data: Binary data
        :type data: bytes

        :return: Tuple of event time, key_action, key_code
        :rtype: tuple
        """
        # Event Seconds, Event Microseconds, Event Type, Event Code, Event Value
        ev_sec, ev_usec, ev_type, ev_code, ev_value = struct.unpack(EVENT_FORMAT, data)

        if ev_type != 0x01: # input-event-codes.h EV_KEY 0x01
            return None, None, None

        if ev_value == 0:
            key_action = 'release'
        elif ev_value == 1:
            key_action = 'press'
        elif ev_value == 2:
            key_action = 'autorepeat'
        else:
            key_action = 'unknown'

        seconds = ev_sec + (ev_usec * 0.000001)
        date = datetime.datetime.fromtimestamp(seconds)

        result = (date, key_action, ev_code)

        if ev_type == ev_code == ev_value == 0:
            return None, None, None

        return result

    def __init__(self, device_id, event_files, parent):
        super(KeyWatcher, self).__init__()

        self._logger = logging.getLogger('razer.device{0}.keywatcher'.format(device_id))
        self._event_files = event_files
        self._shutdown = False
        self._parent = parent

        self.open_event_files = [open(event_file, 'rb') for event_file in self._event_files]
        # Set open files to non blocking mode
        for event_file in self.open_event_files:
            flags = fcntl.fcntl(event_file.fileno(), fcntl.F_GETFL)
            fcntl.fcntl(event_file.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def run(self):
        """
        Main event loop
        """
        # Create dict of Event File Descriptor: Event File Object
        event_file_map = {event_file.fileno(): event_file for event_file in self.open_event_files}

        # Create epoll object
        poll_object = select.epoll()

        # Register files with select
        for event_fd in event_file_map.keys():
            poll_object.register(event_fd, select.EPOLLIN | select.EPOLLPRI)

        # Loop
        while not self._shutdown:
            # epoll is nice but it wasn't getting events properly :(
            # events = poll_object.poll(EPOLL_TIMEOUT)
            #
            # if len(events) != 0:
            #     # pylint: disable=unused-variable
            #     for event_fd, mask in events:
            #         key_data = event_file_map[event_fd].read(EVENT_SIZE)
            #
            #         date, key_action, key_code = self.parse_event_record(key_data)
            #
            #         # Skip if date, key_action and key_code is none as thats a spacer record
            #         if date is None:
            #             continue
            #
            #         # Now if key is pressed then we record
            #         if key_action == 'press':
            #             self._parent.key_action(date, key_code, True)
            #         elif key_action == 'release':
            #             self._parent.key_action(date, key_code, False)

            for event_file in self.open_event_files:
                key_data = event_file.read(EVENT_SIZE)

                if key_data is None:
                    continue

                date, key_action, key_code = self.parse_event_record(key_data)

                # Skip if date, key_action and key_code is none as thats a spacer record
                if date is None:
                    continue

                # Now if key is pressed then we record
                if key_action == 'press':
                    self._parent.key_action(date, key_code, True)
                elif key_action == 'release':
                    self._parent.key_action(date, key_code, False)

            time.sleep(EPOLL_TIMEOUT)


        # Unbind files and close them
        for event_fd, event_file in event_file_map.items():
            poll_object.unregister(event_fd)
            event_file.close()

        poll_object.close()

    @property
    def shutdown(self):
        """
        Thread shutdown condition

        :return: Shutdown condition
        :rtype: bool
        """
        return self._shutdown
    @shutdown.setter
    def shutdown(self, value):
        """
        Set thread shutdown condition

        :param value: Boolean, normally only True would be used
        :type value: str
        """
        self._shutdown = value

class KeyManager(object):
    """
    Key management class.

    This class deals with anything to do with keypresses. Currently it does:
    * Receiving keypresses from the KeyWatcher
    * Logic to deal with GameMode shortcut not working when macro's not enabled
    * Logic to deal with recording on the fly macros and replaying them
    * Stores number of keypresses / key / hour, stats are used for heatmaps / time-series

    It will be used to store keypresses in a list (for at most 2 seconds) if enabled for the ripple effect, when I
    get round to making the effect.
    """
    # pylint: disable=too-many-instance-attributes
    def __init__(self, device_id, event_files, parent):

        self._device_id = device_id
        self._logger = logging.getLogger('razer.device{0}.keymanager'.format(device_id))
        self._parent = parent
        self._parent.register_observer(self)

        self._event_files = event_files
        self._access_lock = threading.Lock()
        self._keywatcher = KeyWatcher(device_id, event_files, self)
        self._open_event_files = self._keywatcher.open_event_files

        if len(event_files) > 0:
            self._logger.debug("Starting KeyWatcher")
            self._keywatcher.start()
        else:
            self._logger.warning("No event files for KeyWatcher")

        self._record_stats = parent.config.get('Statistics', 'key_statistics')
        self._stats = {}

        self._fn_down = False
        self._recording_macro = False
        self._macros = {}

        self._current_macro_bind_key = None
        self._current_macro_combo = []

        self._threads = set()
        self._clean_counter = 0

        self._temp_key_store_active = False
        self._temp_key_store = []
        self._temp_expire_time = datetime.timedelta(seconds=2)

        self._last_colour_choice = None

        self._event_files_locked = False

    #TODO add property for enabling key stats?

    @property
    def temp_key_store(self):
        """
        Get the temporary key store

        :return: List of keys
        :rtype: list
        """
        # Locking so it doesnt mutate whilst copying
        self._access_lock.acquire()
        now = datetime.datetime.now()

        # Remove expired keys from store
        try:
            # Get date and if its less than now its expired
            while self._temp_key_store[0][0] < now:
                self._temp_key_store.pop(0)
        except IndexError:
            pass

        # Creating a copy as then it doesnt mutate whilst iterating
        result = self._temp_key_store[:]
        self._access_lock.release()
        return result

    @property
    def temp_key_store_state(self):
        """
        Get the state of the temporary key store

        :return: Active state
        :rtype: bool
        """
        return self._temp_key_store_active

    @temp_key_store_state.setter
    def temp_key_store_state(self, value):
        """
        Set the state of the temporary key store

        :param value: Active state
        :type value: bool
        """
        self._temp_key_store_active = value

    def grab_event_files(self, grab):
        """
        Grab the event files exclusively

        :param grab: True to grab, False to release
        :type grab: bool
        """
        for event_file in self._open_event_files:
            fcntl.ioctl(event_file.fileno(), EVIOCGRAB, int(grab))
        self._event_files_locked = grab

    def key_action(self, event_time, key_id, key_press=True):
        """
        Process a key press event

        Ok an attempt to explain the logic
        * The function sets a value _fn_down depending on the state of FN.
        * Adds keypress and release events to a macro list if recording a macro.
        * Pressing FN+F9 starts recording a macro, then selecting any key marks that as a macro key,
          then it will record keys, then pressing FN+F9 will save macro.
        * Pressing any macro key will run macro.
        * Pressing FN+F10 will toggle game mode.
        * Pressing any key will increment a statistical number in a dictionary used for generating
          heatmaps.
        :param event_time: Time event occured
        :type event_time: datetime.datetime

        :param key_id: Key Event ID
        :type key_id: int

        :param key_press: If true then its a press, else its a release
        :type key_press: bool
        """
        # Disable pylints complaining for this part, #PerformanceOverNeatness
        # pylint: disable=too-many-branches,too-many-statements
        self._access_lock.acquire()

        now = datetime.datetime.now()

        # Remove expired keys from store
        try:
            # Get date and if its less than now its expired
            while self._temp_key_store[0][0] < now:
                self._temp_key_store.pop(0)
        except IndexError:
            pass

        # Clean up any threads
        if self._clean_counter > 20 and len(self._threads) > 0:
            self._clean_counter = 0
            self.clean_macro_threads()

        try:
            # Convert event ID to key name
            key_name = EVENT_MAPPING[key_id]

            # Key release
            if not key_press:
                # Logic for treating FN as a modifier
                if key_name == 'FN':
                    self._fn_down = False

                    if self._event_files_locked:
                        self.grab_event_files(False)

                # Add key release events to the macro chain if recording
                elif self._recording_macro and not self._fn_down:
                    # Skip as dont care about releasing macro bind key
                    if self._current_macro_bind_key == key_name:
                        pass

                    # Record key release events
                    else:
                        self._current_macro_combo.append((event_time, key_name, 'UP'))

            else:
                # Key press

                # This is the key for storing stats, by generating hour timestamps it will bucket data nicely.
                storage_bucket = event_time.strftime('%Y%m%d%H')

                try:
                    # Try and increment key in bucket
                    self._stats[storage_bucket][key_name] += 1
                    # self._logger.debug("Increased key %s", key_name)
                except KeyError:
                    # Create bucket
                    self._stats[storage_bucket] = dict.fromkeys(KEY_MAPPING, 0)
                    try:
                        # Increment key
                        self._stats[storage_bucket][key_name] += 1
                        # self._logger.debug("Increased key %s", key_name)
                    except KeyError as err:
                        self._logger.exception("Got key error. Couldn't store in bucket", exc_info=err)

                if self._temp_key_store_active:
                    colour = random_colour_picker(self._last_colour_choice, COLOUR_CHOICES)
                    self._last_colour_choice = colour
                    self._temp_key_store.append((now + self._temp_expire_time, KEY_MAPPING[key_name], colour))

                # Logic for treating FN as a modifier
                if key_name == 'FN':
                    self._fn_down = True

                    # Grab the file so no FN+Keys are leaked
                    if not self._event_files_locked:
                        self.grab_event_files(True)
                # Mute logic (as macro_keys disables all FN+Keys)
                elif self._fn_down and key_name == 'F1':
                    self.play_media_key('vol_mute')
                # Volume down logic
                elif self._fn_down and key_name == 'F2':
                    self.play_media_key('vol_down')
                # Volume up logic
                elif self._fn_down and key_name == 'F3':
                    self.play_media_key('vol_up')
                # Media previous logic
                elif self._fn_down and key_name == 'F5':
                    self.play_media_key('media_prev')
                # Media play/pause logic
                elif self._fn_down and key_name == 'F6':
                    self.play_media_key('media_play')
                # Media next logic
                elif self._fn_down and key_name == 'F7':
                    self.play_media_key('media_next')
                # Macro FN+F9 logic
                elif self._fn_down and key_name == 'F9':
                    self._logger.info("Got macro combo")

                    if not self._recording_macro:
                        # Starting to record macro
                        self._recording_macro = True
                        self._current_macro_bind_key = None
                        self._current_macro_combo = []

                        self._parent.setMacroEffect(0x01)
                        self._parent.setMacroMode(True)

                    else:
                        # Finish recording macro
                        self.add_kb_macro()
                        self._recording_macro = False
                        self._parent.setMacroMode(False)
                # Sets up game mode as when enabling macro keys it stops the key working
                elif self._fn_down and key_name == 'F10':
                    self._logger.info("Got game mode combo")

                    game_mode = self._parent.getGameMode()
                    self._parent.setGameMode(not game_mode)
                # Sleep logic
                elif self._fn_down and key_name == 'PAUSE':
                    self.play_media_key('sleep')
                # Recording all keypress events
                elif self._recording_macro:
                    if self._current_macro_bind_key is None:
                        self._current_macro_bind_key = key_name
                        self._parent.setMacroEffect(0x00)
                    # Don't want no recursion
                    elif self._current_macro_bind_key == key_name:
                        self._logger.warning("Skipping macro assignment as would cause recursion")
                    # Anything else just record it
                    else:
                        self._current_macro_combo.append((event_time, key_name, 'DOWN'))
                # Not recording anything so if a macro key is pressed then run
                else:
                    # If key has a macro, play it
                    if key_name in self._macros:
                        self._logger.info("Running Macro %s:%s", key_name, str(self._macros[key_name]))
                        self.play_macro(key_name)

        except KeyError as err:
            self._logger.exception("Got key error. Couldn't convert event to key name", exc_info=err)

        self._access_lock.release()

    def add_kb_macro(self):
        """
        Tidy up the recorded macro and add it to the store

        Goes through the macro and generated relative delays between key events
        """
        new_macro = []

        start_time = self._current_macro_combo[0][0]
        for event_time, key, state in self._current_macro_combo:
            delay = (event_time - start_time).microseconds
            start_time = event_time
            new_macro.append(MacroKey(key, delay, state))

        self._macros[self._current_macro_bind_key] = new_macro

    def clean_macro_threads(self):
        """
        Threadless-threadpool

        Goes though the threads (macro play jobs) and removed the threads if they have finished.
        #SetMagic
        """
        self._logger.debug("Cleaning up macro threads")
        to_remove = set()

        for macro_thread in self._threads:
            macro_thread.join(timeout=0.05)
            if not macro_thread.is_alive():
                to_remove.add(macro_thread)

        self._threads -= to_remove

    def play_macro(self, macro_key):
        """
        Play macro for a given key

        Launches a thread and adds it to the pool
        :param macro_key: Macro Key
        :type macro_key: str
        """
        macro_thread = MacroRunner(self._device_id, macro_key, self._macros[macro_key])
        macro_thread.start()
        self._threads.add(macro_thread)

    def play_media_key(self, media_key):
        """
        Execute a media keys function

        :param media_key: Media key name
        :type media_key: str
        """
        media_key_thread = MediaKeyPress(media_key)
        media_key_thread.start()
        self._threads.add(media_key_thread)

    # Methods to be used with DBus
    def dbus_delete_macro(self, key_name):
        """
        Delete a macro from a key

        :param key_name: Key Name
        :type key_name: str
        """
        try:
            del self._macros[key_name]
        except KeyError:
            pass

    def dbus_get_macros(self):
        """
        Get macros in JSON format

        :return: JSON of macros
        :rtype: str
        """
        result_dict = {}
        for macro_key, macro_combo in self._macros.items():
            str_combo = [value.to_dict() for value in macro_combo]
            result_dict[macro_key] = str_combo

        return json.dumps(result_dict)

    def dbus_add_macro(self, macro_key, macro_json):
        """
        Add macro from JSON

        :param macro_key: Macro bind key
        :type macro_key: str

        :param macro_json: Macro JSON
        :type macro_json: str
        """
        macro_list = [macro_dict_to_obj(json_dict) for json_dict in json.loads(macro_json)]
        self._macros[macro_key] = macro_list

    def close(self):
        """
        Cleanup function
        """
        if self._keywatcher.is_alive():
            self._parent.remove_observer(self)

            self._logger.debug("Stopping key manager")
            self._keywatcher.shutdown = True
            self._keywatcher.join(timeout=2)
            if self._keywatcher.is_alive():
                self._logger.error("Could not stop KeyWatcher thread")

    def __del__(self):
        self.close()

    def notify(self, msg):
        """
        Receive notificatons from the device (we only care about effects)

        :param msg: Notification
        :type msg: tuple
        """
        if not isinstance(msg, tuple):
            self._logger.warning("Got msg that was not a tuple")
        elif msg[0] == 'effect':
            # We have a message directed at us
            # MSG format
            #  0         1       2             3
            # ('effect', Device, 'effectName', 'effectparams'...)
            # Device is the device the msg originated from (could be parent device)
            if msg[2] != 'setRipple':
                # If we are not doing ripple effect then disable the storing of keys
                #self.temp_key_store_state = False
                pass

class MediaKeyPress(threading.Thread):
    """
    Class to run xdotool to execute media/volume keypresses
    """
    def __init__(self, media_key):
        super(MediaKeyPress, self).__init__()
        if media_key == 'sleep':
            self._media_key = media_key
        else:
            self._media_key = MEDIA_KEY_MAP[media_key]

    def run(self):
        if self._media_key == 'sleep':
            subprocess.call(['dbus-send', '--system', '--print-reply', '--dest=org.freedesktop.login1',
                             '/org/freedesktop/login1', 'org.freedesktop.login1.Manager.Suspend', 'boolean:true'])
        else:
            proc = subprocess.Popen(['xdotool', 'key', self._media_key], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.communicate()

















