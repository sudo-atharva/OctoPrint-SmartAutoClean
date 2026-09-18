# OctoPrint-SmartAutoClean

Autonomous print queue for OctoPrint: on print done, waits for bed to cool,
optionally sweeps the finished part off the bed with a gcode move, checks the
bed is actually clear via webcam, starts the next queued file, and powers the
printer off (Pi GPIO relay) when the queue runs dry. Everything has a manual
fallback — flip a toggle instead of wiring anything.

Built for an Anycubic Kobra 2 Neo but printer-specific numbers live in
`octoprint_autofarm/printer_profiles.yaml`, copied to OctoPrint's plugin data
folder on first run. Add a block there for any other printer.

## Install

Via OctoPrint's [Plugin Manager](https://docs.octoprint.org/en/master/bundledplugins/pluginmanager.html) > Get More > ...from URL:

    https://github.com/sudo-atharva/OctoPrint-SmartAutoClean/archive/master.zip

Or manually:

```
pip install -e .
```
On a Raspberry Pi, if using the GPIO relay: `pip install RPi.GPIO` separately
(not in requirements.txt, it only installs on a Pi and would break `pip
install` everywhere else).

## Before you trust it unattended

- **Eject move**: default `eject_z` / sweep coordinates in
  `printer_profiles.yaml` are guesses. Use the "Test eject move" button in
  settings with an empty bed first, then with a real part, before turning on
  `auto_eject`. Nozzle drags across the bed at low Z — a wrong Z can scratch
  the plate or crash into a stuck part.
- **Bed-clear check** needs a webcam configured in OctoPrint *and* a
  reference shot of the empty bed ("Capture empty-bed reference" button). No
  camera or no reference = check is skipped, queue advances blind.
- **Relay GPIO pin**: wrong pin number cuts power to the wrong thing, or
  nothing. Verify with a multimeter before wiring mains through it.
- If the eject move can't get the part fully clear (stuck part, wrong
  coordinates), the plugin stops and asks for confirmation rather than
  starting the next print on top of it.

## Config knobs (plugin settings)

- `enabled` — master on/off for the whole autonomous flow.
- `auto_eject` — off means notify-and-wait-for-button instead of moving.
- `relay_mode` — `manual` (notify) or `gpio` (auto power off, needs
  RPi.GPIO + wiring).
- `bed_clear_check` — needs `opencv-python` installed, otherwise silently
  skipped.

## Author

Atharva ([@sudo-atharva](https://github.com/sudo-atharva))

## License

AGPLv3, see [LICENSE](LICENSE).
