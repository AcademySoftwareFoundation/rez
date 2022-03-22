## Overview

Rez has a good number of configurable settings. The default settings, and
documentation for every setting, can be found
[here](https://github.com/__GITHUB_REPO__/blob/__GITHUB_BRANCH__/src/rez/rezconfig.py).

Settings are determined in the following way:

- The setting is first read from the file *rezconfig.py* in the rez installation;
- The setting is then overridden if it is present in another settings file pointed at by the
  *REZ_CONFIG_FILE* environment variable. This can also be a path-like variable, to read from
  multiple configuration files;
- The setting is further overriden if it is present in *$HOME/.rezconfig*;
- The setting is overridden again if the environment variable *REZ_XXX* is present, where *XXX* is
  the uppercase version of the setting key. For example, "image_viewer" will be overriden by
  *REZ_IMAGE_VIEWER*.
- This is a special case applied only during a package build or release. In this case, if the
  package definition file contains a "config" section, settings in this section will override all
  others. See [here](#package-overrides).

It is fairly typical to provide your site-specific rez settings in a file that the environment
variable *REZ_CONFIG_FILE* is then set to for all your users. Note that you do not need to provide
a copy of all settings in this file - just provide those that are changed from the defaults.

## Settings Merge Rules

When multiple configuration sources are present, the settings are merged together -
one config file does not replace the previous one, it overrides it. By default, the
following rules apply:

* Dicts are recursively merged together;
* Non-dicts override the previous value.

However, it is also possible to append and/or prepend list-based settings. For example, the
following config entry will append to the `release_hooks` setting value defined by the
previous configuration sources (you can also supply a *prepend* argument):

    release_hooks = ModifyList(append=["custom_release_notify"])

## Package Overrides

Packages themselves can override configuration settings. To show how this is useful,
consider the following example:

    # in package.py
    with scope("config") as c:
        c.release_packages_path = "/svr/packages/internal"

Here a package is overriding the default release path - perhaps you're releasing
internally- and externally-developed packages to different locations, for example.

These config overrides are only applicable during building and releasing of the package.
As such, even though any setting can be overridden, it's only useful to do so for
those that have any effect during the build/install process. These include:

* Settings that determine where packages are found, such as *packages_path*,
  *local_packages_path* and *release_packages_path*;
* Settings in the *build_system*, *release_hook* and *release_vcs* plugin types;
* *package_definition_python_path*;
* *package_filter*.

## String Expansions

The following string expansions occur on all configuration settings:

* Any environment variable reference, in the form *${HOME}*;
* Any property of the *system* object, eg *{system.platform}*.

The *system* object has the following attributes:

* platform: The platform, eg 'linux';
* arch: The architecture, eg 'x86_64';
* os: The operating system, eg 'Ubuntu-12.04';
* user: The current user's username;
* home: Current user's home directory;
* fqdn: Fully qualified domain name, eg 'somesvr.somestudio.com';
* hostname: Host name, eg 'somesvr';
* domain: Domain name, eg 'somestudio.com';
* rez_version: Version of rez, eg '2.0.1'.

## Delay Load

It is possible to store a config setting in a separate file, which will be loaded
only when that setting is referenced. This can be useful if you have a large value
(such as a dict) that you don't want to pollute the main config with. YAML and
JSON formats are supported:

    # in rezconfig
    default_relocatable_per_package = DelayLoad('/svr/configs/rez_relocs.yaml')

## Commandline Tool

You can use the *rez-config* command line tool to see what the current configured settings are.
Called with no arguments, it prints all settings; if you specify an argument, it prints out just
that setting:

    ]$ rez-config packages_path
    - /home/sclaus/packages
    - /home/sclaus/.rez/packages/int
    - /home/sclaus/.rez/packages/ext

Here is an example showing how to override settings using your own configuration file:

    ]$ echo 'packages_path = ["~/packages", "/packages"]' > myrezconfig.py
    ]$ export REZ_CONFIG_FILE=${PWD}/myrezconfig.py
    ]$ rez-config packages_path
    - /home/sclaus/packages
    - /packages

## Configuration Settings

Following is an alphabetical list of rez settings.

> [[media/icons/info.png]] Note that this list has been generated automatically
> from the [rez-config.py](https://github.com/__GITHUB_REPO__/blob/master/src/rez/rezconfig.py)
> file in the rez source, so you can also refer to that file for the same information.

__REZCONFIG_MD__
