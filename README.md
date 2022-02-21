# Internet Radio

An add-on for the WebThings Gateway that allows you to play internet radio stations.

It comes with a few default radio stations, but you can add your own in the settings page.

It creates a thing with a few properties:
- Select the desired station from a drop-down.
- You can set the audio volume
- You can turn the radio on and off

It uses persistence to remember the previous state (e.g. selected radio station, volume, playing).

You will need to have `ffmpeg` installed on your system, if it isn't already.
Additionally, on Linux, you will need `alsa-utils` installed.

The Bluetooth functonality only works is Bluealsa is installed.
