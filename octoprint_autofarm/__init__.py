# -*- coding: utf-8 -*-
import base64
import os
import shutil
import urllib.request

import flask
import octoprint.plugin
import yaml
from octoprint.events import Events
from octoprint.util import RepeatedTimer

from . import logic

try:
    import cv2
    import numpy as np

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import RPi.GPIO as GPIO

    HAS_GPIO = True
except (ImportError, RuntimeError):
    HAS_GPIO = False

def _to_data_uri(frame):
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("could not encode image")
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode("ascii")


EJECT_DONE_MARKER = "AUTOFARM_EJECT_DONE"
BED_POLL_INTERVAL = 5  # seconds
BED_COOL_TIMEOUT = 20 * 60  # give up waiting for cooldown after this long


class AutoFarmPlugin(
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.EventHandlerPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.StartupPlugin,
):
    def __init__(self):
        self._profiles = {}
        self._cooldown_timer = None
        self._cooldown_started = None
        self._awaiting_action = None  # "eject" or "next" or "shutdown", or None

    # ---------- lifecycle ----------

    def on_after_startup(self):
        self._load_profiles()

    def _profiles_path(self):
        user_copy = os.path.join(self.get_plugin_data_folder(), "printer_profiles.yaml")
        if not os.path.exists(user_copy):
            bundled = os.path.join(os.path.dirname(__file__), "printer_profiles.yaml")
            if os.path.exists(bundled):
                shutil.copy(bundled, user_copy)
        return user_copy

    def _load_profiles(self):
        try:
            path = self._profiles_path()
            with open(path) as f:
                self._profiles = yaml.safe_load(f) or {}
        except Exception:
            self._logger.exception("Could not load printer_profiles.yaml, using none")
            self._profiles = {}

    def _current_profile(self):
        name = self._settings.get(["printer_profile"])
        return self._profiles.get(name)

    # ---------- SettingsPlugin ----------

    def get_settings_defaults(self):
        return {
            "enabled": False,
            "auto_eject": False,
            "relay_mode": "manual",  # "gpio" or "manual"
            "relay_gpio_pin": 17,
            "relay_active_low": False,
            "bed_clear_check": True,
            "bed_clear_ratio_threshold": 0.02,
            "printer_profile": "kobra2neo",
            "queue": [],
        }

    def get_settings_restricted_paths(self):
        return {"admin": [["relay_gpio_pin"]]}

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._load_profiles()

    # ---------- TemplatePlugin / AssetPlugin ----------

    def get_template_configs(self):
        return [
            {"type": "settings", "custom_bindings": True, "template": "autofarm_settings.jinja2"},
            {"type": "tab", "custom_bindings": True, "template": "autofarm_tab.jinja2"},
        ]

    def get_assets(self):
        return {"js": ["js/autofarm.js"]}

    def get_template_vars(self):
        return {
            "has_cv2": HAS_CV2,
            "has_gpio": HAS_GPIO,
            "profiles": self._profiles,
        }

    # ---------- SimpleApiPlugin ----------

    def get_api_commands(self):
        return {
            "start_next": [],
            "shutdown_now": [],
            "add_to_queue": ["path"],
            "remove_from_queue": ["index"],
            "set_empty_reference": [],
            "test_eject": [],
            "check_bed_clear": [],
        }

    def on_api_command(self, command, data):
        if command == "start_next":
            self._resume_after_action()
        elif command == "shutdown_now":
            self._relay_off()
        elif command == "add_to_queue":
            queue = self._settings.get(["queue"])
            queue.append({"path": data["path"], "sd": data.get("sd", False)})
            self._settings.set(["queue"], queue)
            self._settings.save()
        elif command == "remove_from_queue":
            queue = self._settings.get(["queue"])
            index = int(data["index"])
            if 0 <= index < len(queue):
                queue.pop(index)
                self._settings.set(["queue"], queue)
                self._settings.save()
        elif command == "set_empty_reference":
            self._save_reference_snapshot()
        elif command == "test_eject":
            profile = self._current_profile()
            if profile:
                self._send_eject_gcode(profile)
        elif command == "check_bed_clear":
            return flask.jsonify(self._bed_clear_preview())

    def on_api_get(self, request):
        # Read-only status, polled by anything with an OctoPrint API key -
        # the mobile app / dashboard don't need a websocket connection open
        # to see whether AutoFarm is waiting on you.
        return flask.jsonify(
            {
                "enabled": self._settings.get_boolean(["enabled"]),
                "auto_eject": self._settings.get_boolean(["auto_eject"]),
                "awaiting_action": self._awaiting_action,
                "queue": self._settings.get(["queue"]),
                "printer_profile": self._settings.get(["printer_profile"]),
                "has_cv2": HAS_CV2,
                "has_gpio": HAS_GPIO,
            }
        )

    # ---------- event handling ----------

    def on_event(self, event, payload):
        if event == Events.PRINT_DONE and self._settings.get_boolean(["enabled"]):
            self._start_cooldown_wait()

    def _start_cooldown_wait(self):
        import time

        self._cooldown_started = time.time()
        if self._cooldown_timer is not None:
            self._cooldown_timer.cancel()
        self._cooldown_timer = RepeatedTimer(
            BED_POLL_INTERVAL, self._check_cooldown, run_first=True
        )
        self._cooldown_timer.start()

    def _check_cooldown(self):
        import time

        profile = self._current_profile()
        target = profile["bed_clear_temp"] if profile else 45
        temps = self._printer.get_current_temperatures()
        bed = temps.get("bed", {}).get("actual")
        timed_out = time.time() - self._cooldown_started > BED_COOL_TIMEOUT
        if bed is None or bed <= target or timed_out:
            self._cooldown_timer.cancel()
            self._cooldown_timer = None
            if timed_out:
                self._logger.warning("Bed cooldown timed out, proceeding anyway")
            self._handle_print_done()

    def _handle_print_done(self):
        profile = self._current_profile()
        if self._settings.get_boolean(["auto_eject"]) and profile:
            self._send_eject_gcode(profile)
            self._awaiting_action = "eject"
        else:
            self._awaiting_action = "next"
            self._notify("Print done and bed cooled. Remove part, then press Start Next.", True)

    # ---------- gcode-received hook target ----------

    def on_gcode_received(self, comm, line, *args, **kwargs):
        if EJECT_DONE_MARKER in line and self._awaiting_action == "eject":
            self._awaiting_action = None
            self._after_eject()
        return line

    def _send_eject_gcode(self, profile):
        z = profile["eject_z"]
        sx, sy = profile["sweep_start"]
        ex, ey = profile["sweep_end"]
        feed = profile["feedrate"]
        self._printer.commands(
            [
                "G90",
                f"G1 Z{z} F600",
                f"G1 X{sx} Y{sy} F{feed}",
                f"G1 X{ex} Y{ey} F{feed}",
                "G28 X Y",
                "M400",
                f"M118 {EJECT_DONE_MARKER}",
            ]
        )

    def _after_eject(self):
        if HAS_CV2 and self._settings.get_boolean(["bed_clear_check"]):
            clear = self._check_bed_clear()
            if clear is False:
                self._awaiting_action = "next"
                self._notify("Eject done but part still detected on bed. Check printer.", True)
                return
            # clear is None => check skipped (no camera/reference), proceed
        self._advance_queue()

    def _resume_after_action(self):
        stage, self._awaiting_action = self._awaiting_action, None
        if stage in ("next", None):
            self._advance_queue()
        elif stage == "eject":
            self._after_eject()

    def _advance_queue(self):
        queue = self._settings.get(["queue"])
        item, rest = logic.pop_next(queue)
        self._settings.set(["queue"], rest)
        self._settings.save()
        if item is None:
            self._notify("Queue empty.")
            self._handle_relay_shutdown()
            return
        self._printer.select_file(item["path"], item.get("sd", False), printAfterSelect=True)
        self._notify(f"Starting next print: {item['path']}")

    # ---------- relay ----------

    def _handle_relay_shutdown(self):
        mode = self._settings.get(["relay_mode"])
        if mode == "gpio" and HAS_GPIO:
            self._relay_off()
        else:
            self._awaiting_action = "shutdown"
            self._notify("Queue empty. Press Shutdown to power off the printer.", True)

    def _relay_off(self):
        if not HAS_GPIO:
            self._logger.warning("relay_off requested but RPi.GPIO is not available")
            return
        pin = self._settings.get_int(["relay_gpio_pin"])
        active_low = self._settings.get_boolean(["relay_active_low"])
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH if active_low else GPIO.LOW)
        self._notify("Printer powered off.")

    # ---------- bed-clear check ----------

    def _grab_snapshot(self):
        url = self._settings.global_get(["webcam", "snapshot"])
        if not url:
            return None
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = resp.read()
        arr = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def _reference_path(self):
        return os.path.join(self.get_plugin_data_folder(), "empty_bed_reference.jpg")

    def _save_reference_snapshot(self):
        try:
            frame = self._grab_snapshot()
            if frame is not None:
                cv2.imwrite(self._reference_path(), frame)
                self._notify("Empty-bed reference saved.")
        except Exception:
            self._logger.exception("Could not save reference snapshot")

    def _grab_and_compare(self):
        """Returns (ratio, current_frame, reference_frame). Raises if camera/reference missing."""
        reference = cv2.imread(self._reference_path())
        if reference is None:
            raise RuntimeError("no empty-bed reference saved yet")
        current = self._grab_snapshot()
        if current is None:
            raise RuntimeError("no webcam snapshot URL configured")
        if current.shape != reference.shape:
            current = cv2.resize(current, (reference.shape[1], reference.shape[0]))
        ratio = logic.diff_ratio(current, reference)
        return ratio, current, reference

    def _check_bed_clear(self):
        """True/False = checked, None = check skipped (not set up)."""
        if not os.path.exists(self._reference_path()):
            self._logger.info("No empty-bed reference set, skipping bed-clear check")
            return None
        try:
            ratio, _, _ = self._grab_and_compare()
            threshold = self._settings.get_float(["bed_clear_ratio_threshold"])
            return ratio < threshold
        except Exception:
            # Fail closed: a camera/check glitch must not wave a possibly-occupied bed through.
            self._logger.exception("Bed-clear check errored, treating as not clear")
            return False

    def _bed_clear_preview(self):
        """For the 'Test bed-clear check' button: run it now and return something to look at."""
        try:
            ratio, current, reference = self._grab_and_compare()
        except Exception as e:
            return {"ok": False, "error": str(e)}
        threshold = self._settings.get_float(["bed_clear_ratio_threshold"])
        return {
            "ok": True,
            "clear": ratio < threshold,
            "ratio": ratio,
            "threshold": threshold,
            "current_image": _to_data_uri(current),
            "reference_image": _to_data_uri(reference),
        }

    # ---------- notify ----------

    def _notify(self, text, needs_action=False):
        self._plugin_manager.send_plugin_message(
            self._identifier, {"text": text, "needs_action": needs_action}
        )

    # ---------- update check ----------

    def get_update_information(self):
        return {}


__plugin_name__ = "Smart Auto Clean"
__plugin_author__ = "Atharva"
__plugin_pythoncompat__ = ">=3.7,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = AutoFarmPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.comm.protocol.gcode.received": __plugin_implementation__.on_gcode_received
    }
