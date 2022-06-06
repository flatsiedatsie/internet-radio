# Internet Radio

An add-on for the Candle Controller / WebThings Gateway that allows you to play internet radio stations.

https://www.candlesmarthome.com

It has a nice interface to find and manage radio stations.

It also creates a thing with a few properties:
- Select the desired station from a drop-down.
- You can set the audio volume
- You can turn the radio on and off
- Artist and song name of currently playing music (if that data is encoded in the stream)
- Audio output (hdmi, headphone jack, or bluetooth speaker).

It uses persistence to remember the previous state (e.g. selected radio station, volume, playing).

You will need to have `omx-player` installed on your system, if it isn't already.
Additionally, on Linux, you will need `alsa-utils` installed.

The Bluetooth functonality only works if Bluealsa is installed (The Candle Controller comes with it pre-installed)
