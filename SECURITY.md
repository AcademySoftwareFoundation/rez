# Security Policy

## Threat Model

List assumptions (rez will run inside an internal network, we assume good intentions, package definitions are written in python and executed)

Access to shared filesystem

The current assumptions are:
* Rez was designed to be used within a studio environment.
* Package definitions, both for building packages and resulting from a build are Python files (`package.py`). Rez will read and load them in memory at resolve time.
* Rez config files can be written in YAML or Python.
* Package definitions and config files written in Python can contain arbitrary code.
* Rez will create new shells via subprocesses.
* Packages can inject environment variables into the resulting shells via [commands](https://rez.readthedocs.io/en/stable/package_commands.html).
* Packages can inject arbitrary commands to be executed when the shells are started via [commands](https://rez.readthedocs.io/en/stable/package_commands.html).

With that in mind, the main entry points are config files (written in python) and pacakge definition files.
Config files will be loaded from default paths and it's also posssible to tell rez
to load them from any arbitraty path using the [REZ_CONFIG_FILE](https://rez.readthedocs.io/en/stable/environment.html#envvar-REZ_CONFIG_FILE) which can contain more than one path.

Document that it can talk to memcached and RabbitMQ (AMQP).

## Supported Versions

We only support the latest version. We try our best to keep rez backward
compatible as much as possible, which allows us to to only support the latest version.

## Reporting a Vulnerability

If you think you've found a potential vulnerability in rez, please report it by filing a GitHub [security
advisory](https://github.com/AcademySoftwareFoundation/rez/security/advisories/new).

Our policy is to acknowledge the receipt of vulnerability reports within 72 hours.
