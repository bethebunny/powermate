#!/usr/bin/env python3
import collections
import glob
import struct


EV_MSC = 0x04
MSC_PULSELED = 0x01

EVENT_SIZE = 24
EVENT_FORMAT = 'llHHi'

PUSH = 0x01
ROTATE = 0x02

class Event(object):
  def __init__(self, tv_sec, tv_usec, type, code, value):
    self.tv_sec = tv_sec
    self.tv_usec = tv_usec
    self.type = type
    self.code = code
    self.value = value

  def raw(self):
    return struct.pack(EVENT_FORMAT, self.tv_sec, self.tv_usec,
                       self.type, self.code, self.value)

  @classmethod
  def fromraw(cls, data):
    tv_sec, tv_usec, type, code, value = struct.unpack(EVENT_FORMAT, data)
    return cls(tv_sec, tv_usec, type, code, value)

  def __repr__(self):
    return '%s(%s)' % (
      self.__class__.__name__,
      ', '.join('%s=%s' % (k, getattr(self, k))
                for k in self.__dict__ if not k.startswith('_'))
    )


class LedEvent(Event):
  def __init__(self, brightness=255, speed=0, pulse_type=0, asleep=0, awake=0):
    self.brightness = brightness
    self.speed = speed
    self.pulse_type = pulse_type
    self.asleep = asleep
    self.awake = awake
    self.type = EV_MSC
    self.code = MSC_PULSELED
    self.tv_sec, self.tv_usec = 0, 0

  @property
  def value(self):
    return (
      self.brightness |
      (self.speed << 8) |
      (self.pulse_type << 17) |
      (self.asleep << 19) |
      (self.awake << 20)
    )

  @classmethod
  def pulse(cls):
    return cls(speed=255, pulse_type=2, asleep=1, awake=1)


class PowerMateBase(object):
  def __init__(self, path, long_threshold=1000):
    self.__event_in = open(path, 'rb')
    self.__event_out = open(path, 'wb')
    self.__rotated = False
    self.button = 0
    self.__button_time = 0
    self.__long_threshold = 1000

  def run(self):
    self.__run = True
    self.handle_events()

  def stop(self):
    self.__run = False

  def handle_events(self):
    while self.__run:
      event = Event.fromraw(self.__event_in.read(24))
      try:
        self.handle_event(event)
      except Exception:
        import traceback
        traceback.print_exc()

  def handle_event(self, event):
    if event.type == PUSH:
      time = event.tv_sec * 10 ** 3 + (event.tv_usec * 10 ** -3)
      self.button = event.value
      if event.value:  #button depressed
        self.__button_time = time
        self.__rotated = False
      else:
        if self.__rotated:
          return
        if time - self.__button_time > self.__long_threshold:
          self.long_press()
        else:
          self.short_press()
    elif event.type == ROTATE:
      if self.button:
        self.__rotated = True
        self.push_rotate(event.value)
      else:
        self.rotate(event.value)

  def pulse_led(self):
    self.__event_out.write(LedEvent.pulse().raw())
    self.__event_out.flush()

  def set_led(self, brightness=255):
    self.__event_out.write(LedEvent(brightness).raw())
    self.__event_out.flush()

  def short_press(self):
    raise NotImplemented

  def long_press(self):
    raise NotImplemented

  def rotate(self, rotation):
    raise NotImplemented

  def push_rotate(self, rotation):
    raise NotImplemented


class PowerMate(PowerMateBase):
  def __init__(self, path):
    super(PowerMate, self).__init__(path)
    self._pulsing = False
    self._brightness = 255
    self.short_press()
  def short_press(self):
    print('Short press!')
    self._pulsing = not self._pulsing
    print(self._pulsing)
    if self._pulsing:
      self.pulse_led()
    else:
      self.set_led(self._brightness)
  def long_press(self):
    print('Long press!')
  def rotate(self, rotation):
    self._brightness += rotation
    if self._brightness < 0:
      self._brightness = 0
    if self._brightness > 255:
      self._brightness = 255
    print('Rotate %d!' % (rotation,))
    print('Brightness: %d' % (self._brightness))
    self.set_led(self._brightness)
  def push_rotate(self, rotation):
    print('Push rotate %d!' % (rotation,))

if __name__ == "__main__":
  pm = PowerMate(glob.glob('/dev/input/by-id/*PowerMate*')[0])
  pm.run()
