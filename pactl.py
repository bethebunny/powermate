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


LIST_PATTERNS = {
    'state': 'State: (\w+)',
    'volume': 'Volume: 0: +(\d+)%',
    'name': 'Name: (.+)'
}


def list_sinks():
  """Return a list of sink objects; these are dicts of properties."""
  output = subprocess.check_output(['pactl', 'list', 'sinks']).decode()
  sinks = []

  for line in output.split('\n'):
    if line.startswith('Sink #'):
      sink = {}
      sinks.append(sink)
    else:
      # While it's close to YAML output, it isn't, and doesn't parse at all :P
      # So some mad hacks here to pull out some basic data
      for prop, pattern in LIST_PATTERNS.items():
        vals = re.findall(pattern, line)
        if vals:
          sink[prop] = vals[0]

  return sinks


def active_sink():
  """Retrieve the first running PulseAudio sink."""
  for sink in list_sinks():
    if sink['state'] == 'RUNNING':
      return sink


def set_volume(value, sink=None):
  """Set an absolute volume for a sink (0-100). Default to active sink."""
  sink = sink or active_sink()
  return subprocess.check_call(['pactl', 'set-sink-volume', sink['name'],
                                '{}%'.format(value)])


def inc_volume(delta=1, sink=None):
  """Set a relative volume for a sink (can be negative). Default to active sink."""
  sink = sink or active_sink()
  if sink:
    volume = int(sink['volume'])
    set_volume(max(0, min(100, volume + delta)), sink=sink)
    return sink
