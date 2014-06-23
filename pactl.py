import re
import subprocess


LIST_PATTERNS = {
    'state': 'State: (\w+)',
    'volume': 'Volume: 0: +(\d+)%',
    'name': 'Name: (.+)'
}


def list_sinks():
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
  for sink in list_sinks():
    if sink['state'] == 'RUNNING':
      return sink


def set_volume(value, sink=None):
  sink = sink or active_sink()
  return subprocess.check_call(['pactl', 'set-sink-volume', sink['name'],
                                '{}%'.format(value)])


def inc_volume(delta=1, sink=None):
  sink = sink or active_sink()
  if sink:
    volume = int(sink['volume'])
    set_volume(max(0, min(100, volume + delta)), sink=sink)
    return sink
