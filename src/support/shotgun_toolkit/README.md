# App Launch Hook - Rez

This hook is executed to launch applications, potentially in a Rez context.

It is **NOT** official/supported by Shotgun Software, but by
[third-party contributors](/AUTHORS.md)


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

1. If you are using [tk-config-default2 v1.2.11][] and have the [patch][]
   program available, you can perform the remaining steps by running

   ```bash
   patch --strip=0 < tk-config-default2/example-configs.patch
   ```

   It might work with other versions/permutations of pipeline configurations
   but not guaranteed.

   ----

   Otherwise, manually...

1. Create new `settings.tk-tk-multi-launchapp.*` application configurations
   inside `<config>/env/includes/settings/tk-multi-launchapp.yml`.

   Here is an **example** for Maya. This assumes you have a `maya` rez package
   built, installed and available i.e. `rez env maya`.

   ```yaml
   # rez Maya 2019
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
     menu_name: "Maya 2019"
     location: "@apps.tk-multi-launchapp.location"
     # --- IMPORTANT ---
     # Point to rez_app_launch.py hook location
     hook_app_launch: "{config}/tk-multi-launchapp/rez_app_launch.py"
     # What to run after entering "rez env maya" to launch Maya, e.g.
     linux_path: "maya"
     mac_path: "Maya.app"
     windows_path: "maya.exe"
   ```

1. Expose those `settings.tk-tk-multi-launchapp.*` application configurations
   for Shotgun *apps* which launches applications

   i.e. inside `<config>/env/includes/settings/`:

   <details><summary>tk-desktop.yml</summary>

   ```yaml
   settings.tk-desktop.project:
     apps:
       tk-multi-pythonconsole:
         location: "@apps.tk-multi-pythonconsole.location"
       tk-multi-devutils:
         location: "@apps.tk-multi-devutils.location"
       tk-multi-launchapp: "@settings.tk-multi-launchapp"
       tk-multi-launchhiero: "@settings.tk-multi-launchapp.hiero"
       tk-multi-launchmari: "@settings.tk-multi-launchapp.mari"
       tk-multi-launchmaya: "@settings.tk-multi-launchapp.maya"  # Added this for rez Maya 2019!
   ```
   </details>

   <details><summary>tk-desktop2.yml</summary>

   ```yaml
   # project
   settings.tk-desktop2.all:
     apps:
       tk-multi-launchapp: "@settings.tk-multi-launchapp"
       tk-multi-launchhiero: "@settings.tk-multi-launchapp.hiero"
       tk-multi-launchmari: "@settings.tk-multi-launchapp.mari"
       tk-multi-launchmaya: "@settings.tk-multi-launchapp.maya"  # Added this for rez Maya 2019!
   ```
   </details>

   <details><summary>tk-shell.yml</summary>

   ```yaml
   # Same for other settings.tk-shell.*
   settings.tk-shell.asset:
     apps:
       tk-multi-launchapp: '@settings.tk-multi-launchapp'
       tk-multi-launchmaya: "@settings.tk-multi-launchapp.maya"  # Added this for rez Maya 2019!
       tk-multi-launchmari: '@settings.tk-multi-launchapp.mari'
   ```
   </details>

   <details><summary>tk-shotgun.yml</summary>

   ```yaml
   # Same for other settings.tk-shotgun.*
   settings.tk-shotgun.asset:
     apps:
       tk-multi-launchapp: "@settings.tk-multi-launchapp"
       tk-multi-launchmari: "@settings.tk-multi-launchapp.mari"
       tk-multi-launchmaya: "@settings.tk-multi-launchapp.maya"  # Added this for rez Maya 2019!
       tk-multi-launchmotionbuilder: "@settings.tk-multi-launchapp.motionbuilder"
   ```
   </details>

### tk-config-default (legacy)


Older, less supported by Shotgun and the original `rez_app_launch.py`.


[patch]: https://www.gnu.org/software/diffutils/manual/html_mono/diff.html#Invoking%20patch
[tk-config-default]: https://github.com/shotgunsoftware/tk-config-default
[tk-config-default2]: https://github.com/shotgunsoftware/tk-config-default2
[tk-config-default2 v1.2.11]: https://github.com/shotgunsoftware/tk-config-default2/releases/tag/v1.2.11