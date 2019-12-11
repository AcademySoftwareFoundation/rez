# App Launch Hook - Rez

This hook is executed to launch applications, potentially in a Rez context.
It is **NOT** official/supported by Shotgun Software, but by third-party
contributors:



## Installation

1. Setup custom pipeline configuration for your Shotgun project

   See ["Advanced project setup" steps](https://youtu.be/7qZfy7KXXX0?t=1170)
   video or checkout [this official tutorial page](https://developer.shotgunsoftware.com/5d83a936/#accessing-the-default-configuration)

1. Identify whether your pipeline configurations are based off
   [tk-config-default2][] or [tk-config-default][] (legacy)

The Python hook and example `.yml` configuration files are setup in a way
that mimics the folder structure where you need to copy them into.

`<config>` will now refer to the full path to the folder which contain
`core`, `env`, `hooks`.

See [this point in this video](https://youtu.be/7qZfy7KXXX0?t=2434)


### tk-config-default2

Latest supported by Shotgun, this will be the main focus.

1. Create `<config>/hooks/tk-multi-launchapp` folder if it does not exist.
1. Copy `tk-config-default2/hooks/tk-multi-launchapp/rez_app_launch.py`
   into that folder.
1. Create new `settings.tk-tk-multi-launchapp.*` application configurations
   inside `<config>/env/includes/settings/tk-multi-launchapp.yml`.

   Here is an example for Maya. This assumes you have a `maya` rez package
   built, installed and available i.e. `rez env maya`.

   ```yaml
   settings.tk-multi-launchapp.maya:
     engine: tk-maya
     extra:
       rez:
         packages:
         - maya-2019
         # # Optional, additional rez packages
         # - studio_maya_tools-1.2
         # - show_maya_tools-dev
         parent_variables:
         - PYTHONPATH
         - MAYA_MODULE_PATH
         - MAYA_SCRIPT_PATH
     hook_app_launch: "{config}/tk-multi-launchapp/rez_app_launch.py"  # IMPORTANT!
     menu_name: "Maya 2019"
     location: "@apps.tk-multi-launchapp.location"
   ```

1. Expose those `settings.tk-tk-multi-launchapp.*` application configurations
   for _apps_ which launches applications e.g.


### tk-config-default (legacy)


Older, less supported by Shotgun and the original `rez_app_launch.py`.



[tk-config-default]: https://github.com/shotgunsoftware/tk-config-default
[tk-config-default2]: https://github.com/shotgunsoftware/tk-config-default2