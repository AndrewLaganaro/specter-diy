from .applet import Applet, ISOException, AppletException
from .securechannel import SecureChannel
import hashlib

def encode(data):
    return bytes([len(data)])+data

class SecureException(Exception):
    """
    Raised when exception was on the card, 
    but not due to the secure channel
    """
    pass

class SecureApplet(Applet):
    SECURE_RANDOM = b"\x01\x00"
    PIN_STATUS    = b"\x03\x00"
    UNLOCK        = b"\x03\x01"
    LOCK          = b"\x03\x02"
    CHANGE_PIN    = b'\x03\x03'
    SET_PIN       = b"\x03\x04"
    # PIN status codes
    PIN_UNSET    = 0
    PIN_LOCKED   = 1
    PIN_UNLOCKED = 2
    PIN_BRICKED  = 3

    def __init__(self, connection, aid):
        super().__init__(connection, aid)
        # secure channel
        self.sc = SecureChannel(self)
        self._pin_attempts_left = None
        self._pin_attempts_max = None
        self._pin_status = None

    def open_secure_channel(self):
        self.sc.open()

    def close_secure_channel(self):
        self.sc.close()

    @property
    def is_secure_channel_open(self):
        return self.sc.is_open

    def _get_pin_status(self):
        status = self.sc.request(self.PIN_STATUS)
        (self._pin_attempts_left, 
         self._pin_attempts_max, 
         self.pin_status) = list(status)
        return tuple(status)

    def get_random(self):
        return self.sc.request(self.SECURE_RANDOM)

    @property
    def is_pin_set(self):
        if self._pin_status is None:
            self._get_pin_status()
        return self._pin_status > 0

    @property
    def pin_attempts_left(self):
        if self._pin_status is None:
            self._get_pin_status()
        return self._pin_attempts_left

    @property
    def pin_attempts_max(self):
        if self._pin_status is None:
            self._get_pin_status()
        return self._pin_attempts_max

    @property
    def is_locked(self):
        if self._pin_status is None:
            self._get_pin_status()
        return self._pin_status in [self.PIN_LOCKED, self.PIN_BRICKED]

    def set_pin(self, pin):
        if self.is_pin_set:
            raise AppletException("PIN is already set")
        # we always set sha256(pin) so it's constant length
        h = hashlib.sha256(pin.encode()).digest()
        self.sc.request(self.SET_PIN+h)
        # update status
        self._get_pin_status()

    def change_pin(self, old_pin, new_pin):
        if not self.is_pin_set:
            raise AppletException("PIN is not set")
        if self.is_locked:
            raise AppletException("Unlock the card first")
        h1 = hashlib.sha256(old_pin.encode()).digest()
        h2 = hashlib.sha256(new_pin.encode()).digest()
        self.sc.request(self.CHANGE_PIN+encode(h1)+encode(h2))
        # update status
        self._get_pin_status()

    def unlock(self, pin):
        if not self.is_locked:
            return
        try:
            h = hashlib.sha256(pin.encode()).digest()
            self.sc.request(self.UNLOCK+h)
        finally:
            # update status
            self._get_pin_status()

    def lock(self):
        self.sc.request(self.LOCK)
        # update status
        self._get_pin_status()
