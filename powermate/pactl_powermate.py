#!/usr/bin/env python3

from __future__ import division

import glob

import pactl
import powermate


class PowerMate(powermate.PowerMateBase):
  def rotate(self, rotation):
    sink = pactl.active_sink()
    if sink:
      volume = sink.inc_volume(rotation)
      return powermate.LedEvent.percent(volume / 100)


if __name__ == '__main__':
  pm = PowerMate(glob.glob('/dev/input/by-id/*PowerMate*')[0])
  pm.run()
