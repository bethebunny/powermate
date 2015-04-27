"""A small library for interacting with the pactl command line tool.

This library allows for a few simple interactions with linux pulseaudio, like
viewing active sinks (sound outputs, usually loosely correlating with speakers)
and their relative volumes, and setting volume absolutely or relatively.

Most functions take a sink argument which defaults to retrieving and using
the first 'RUNNING' sink found. This uses a full subprocess, so users doing
repeated calls are recommended to get a sink object (eg. through active_sink())
and pass that to successive calls.

The pactl tool will need to be installed for this library to work. It is commonly
installed by default when PulseAudio is installed, and on many major distros.
"""

import re
import subprocess


class Sink(object):
  """A class wrapping attributes of PulseAudio sink properties."""

  LIST_PATTERNS = {
      'state': (str, 'State: (\w+)'),
      'volume': (int, 'Volume: 0: +(\d+)%'),
      'name': (str, 'Name: (.+)'),
  }

  __slots__ = tuple(LIST_PATTERNS)

  def __init__(self, **kwargs):
    for key, arg in kwargs.items():
      setattr(self, key, arg)

  def set_volume(self, value):
    """Set an absolute volume (0-100)."""
    if not 0 <= value <= 100:
      raise ValueError("Volume must be between 0 and 100")
    return subprocess.check_call(
        ['pactl', 'set-sink-volume', self.name, '{}%'.format(value)])

  def inc_volume(self, delta=1):
    """Set a relative volume (can be negative)."""
    new_volume = max(0, min(100, self.volume + delta))
    self.set_volume(new_volume)
    return new_volume


def list_sinks():
  """Iterate system's sink objects as Sinks."""
  output = subprocess.check_output(['pactl', 'list', 'sinks']).decode()
  if not output.strip():
    return

  sink = {}

  for line in output.split('\n')[1:]:  # first line starts a sink
    if line.startswith('Sink #'):
      yield Sink(**sink)
      sink = {}
    else:
      # While it's close to YAML output, it isn't, and doesn't parse at all :P
      # So some mad hacks here to pull out some basic data
      for prop, (conversion, pattern) in Sink.LIST_PATTERNS.items():
        vals = re.findall(pattern, line)
        if vals:
          sink[prop] = conversion(vals[0])

  yield Sink(**sink)


def active_sink():
  """Retrieve the first running PulseAudio sink."""
  for sink in list_sinks():
    if sink.state == 'RUNNING':
      return sink
