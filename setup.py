# -*- coding: utf-8 -*-
from setuptools import setup

plugin_identifier = "autofarm"
plugin_package = "octoprint_autofarm"
plugin_name = "Smart Auto Clean"
plugin_version = "0.1.4"
plugin_description = "Autonomous print queue: eject, bed-clear check, power off when idle"
plugin_author = "Atharva"
plugin_author_email = "coppertocode@gmail.com"
plugin_url = "https://github.com/sudo-atharva/OctoPrint-SmartAutoClean"
plugin_license = "AGPLv3"

plugin_requires = ["PyYAML"]
plugin_additional_data = ["printer_profiles.yaml"]

try:
    import octoprint_setuptools
except ImportError:
    print(
        "Could not import OctoPrint's setuptools, are you sure you are running "
        "this under the same python installation OctoPrint is installed under?"
    )
    import sys

    sys.exit(-1)

setup_parameters = octoprint_setuptools.create_plugin_setup_parameters(
    identifier=plugin_identifier,
    package=plugin_package,
    name=plugin_name,
    version=plugin_version,
    description=plugin_description,
    author=plugin_author,
    mail=plugin_author_email,
    url=plugin_url,
    license=plugin_license,
    requires=plugin_requires,
    additional_data=plugin_additional_data,
)

setup(**setup_parameters)
