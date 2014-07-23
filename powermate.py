#!/usr/bin/env python3

from __future__ import print_function

import collections
import glob
try:
  import queue
except ImportError:
  import Queue as queue
import struct
import threading
import traceback


EV_MSC = 0x04
MSC_PULSELED = 0x01

EVENT_FORMAT = 'llHHi'
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

PUSH = 0x01
ROTATE = 0x02
MAX_BRIGHTNESS = 255
MAX_PULSE_SPEED = 255

# We don't want a huge backlog of events, otherwise we get bad situations where
# the listener is processing really old events and takes a while to catch up to
# current ones. If a listener is slow the expected behavior is to drop events
# for that listener.
MAX_QUEUE_SIZE = 5


class EventNotImplemented(NotImplementedError):
  """Special exception type for non-implemented events."""


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
  def __init__(self, brightness=MAX_BRIGHTNESS, speed=0,
               pulse_type=0, asleep=0, awake=0):
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
    return cls(speed=MAX_PULSE_SPEED, pulse_type=2, asleep=1, awake=1)

  @classmethod
  def max(cls):
    return cls(brightness=MAX_BRIGHTNESS)

  @classmethod
  def off(cls):
    return cls(brightness=0)

  @classmethod
  def percent(cls, percent):
    return cls(brightness=int(percent * MAX_BRIGHTNESS))


class FileEventSource(object):
  def __init__(self, path, event_size):
    self.__event_size = event_size
    self.__event_in = open(path, 'rb')
    self.__event_out = open(path, 'wb')

  def __iter__(self):
    data = b''
    while True:
      data += self.__event_in.read(EVENT_SIZE)
      if len(data) >= EVENT_SIZE:
        event = Event.fromraw(data[:EVENT_SIZE])
        data = data[EVENT_SIZE:]
        try:
          yield event
        except EventNotImplemented:
          pass
        except Exception:
          import traceback
          traceback.print_exc()

  def send(self, event):
    self.__event_out.write(event.raw())
    self.__event_out.flush()


class QueueEventSource(object):
  def __init__(self, source):
    self.source = source
    self.queues = []

  def __iter__(self):
    q = queue.Queue(MAX_QUEUE_SIZE)
    self.queues.append(q)
    def iter_queue():
      while True:
        yield q.get()
    return iter_queue()

  def watch(self):
    for event in self.source:
      for q in self.queues:
        try:
          q.put_nowait(event)
        except queue.Full:
          pass

  def send(self, event):
    self.source.send(event)


class EventHandler(object):
  def handle_events(self, source):
    for event in source:
      try:
        return_event = self.handle_event(event)
      except EventNotImplemented:
        pass
      except Exception as e:
        traceback.print_exc()
      else:
        if return_event is not None:
          source.send(return_event)

  def handle_event(self, event):
    raise EventNotImplemented


class PowerMateEventHandler(EventHandler):
  def __init__(self, long_threshold=1000):
    self.__rotated = False
    self.button = 0
    self.__button_time = 0
    self.__long_threshold = long_threshold

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
          return self.long_press()
        else:
          return self.short_press()
    elif event.type == ROTATE:
      if self.button:
        self.__rotated = True
        return self.push_rotate(event.value)
      else:
        return self.rotate(event.value)

  def short_press(self):
    raise EventNotImplemented

  def long_press(self):
    # default to short press if long press is not defined
    return short_press()

  def rotate(self, rotation):
    raise EventNotImplemented

  def push_rotate(self, rotation):
    raise EventNotImplemented


class AsyncFileEventDispatcher(object):
  def __init__(self, path, event_size=EVENT_SIZE):
    self.__filesource = FileEventSource(path, event_size)
    self.__source = QueueEventSource(self.__filesource)
    self.__threads = []

  def add_listener(self, event_handler):
    thread = threading.Thread(target=event_handler.handle_events,
                              args=(self.__source,))
    thread.daemon = True
    thread.start()
    self.__threads.append(thread)

  def run(self):
    self.__source.watch()


class PowerMateBase(AsyncFileEventDispatcher, PowerMateEventHandler):
  def __init__(self, path, long_threshold=1000):
    AsyncFileEventDispatcher.__init__(self, path)
    PowerMateEventHandler.__init__(self, long_threshold)
    self.add_listener(self)


class ExamplePowerMate(PowerMateBase):
  def __init__(self, path):
    super(ExamplePowerMate, self).__init__(path)
    self._pulsing = False
    self._brightness = MAX_BRIGHTNESS

  def short_press(self):
    print('Short press!')
    self._pulsing = not self._pulsing
    print(self._pulsing)
    if self._pulsing:
      return LedEvent.pulse()
    else:
      return LedEvent(brightness=self._brightness)

  def long_press(self):
    print('Long press!')

  def rotate(self, rotation):
    print('Rotate {}!'.format(rotation))
    self._brightness = max(0, min(MAX_BRIGHTNESS, self._brightness + rotation))
    self._pulsing = False
    return LedEvent(brightness=self._brightness)

  def push_rotate(self, rotation):
    print('Push rotate {}!'.format(rotation))


class ExampleBadHandler(PowerMateEventHandler):
  def rotate(self, rotation):
    import time
    time.sleep(1)


if __name__ == "__main__":
  pm = ExamplePowerMate(glob.glob('/dev/input/by-id/*PowerMate*')[0])
  pm.add_listener(ExampleBadHandler())
  pm.run()
