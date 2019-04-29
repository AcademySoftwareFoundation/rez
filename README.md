
![image](https://user-images.githubusercontent.com/2152766/56459362-3eb1ff00-638a-11e9-9db4-6ae83f6dc70f.png)

Rez, with all [feature branches](https://github.com/mottosso/bleeding-rez/branches/all?utf8=%E2%9C%93&query=feature%2F) merged.

[![](https://ci.appveyor.com/api/projects/status/github/mottosso/bleeding-rez?branch=dev&svg=true&passingText=dev%20-%20OK&failingText=master%20-%20failing&pendingText=master%20-%20pending)](https://ci.appveyor.com/project/mottosso/bleeding-rez)
[![](https://ci.appveyor.com/api/projects/status/github/mottosso/bleeding-rez?branch=master&svg=true&passingText=master%20-%20OK&failingText=dev%20-%20failing&pendingText=master%20-%20pending)](https://ci.appveyor.com/project/mottosso/bleeding-rez)

<br>

### Usage

There are a few ways you can use this repo.

1. Use it in place of Rez, it is entirely backwards compatible with your existing install and package repository
1. Each feature branch is self-contained and compatible with Rez, you can merge only the ones you like
2. Most commits are self-contained and well documented, you could cherry-pick only the ones that interest you

**Install**

```bash
$ pip install bleeding-rez
```

<details>
    <summary>Alternative 1 - Latest `master`</summary>

Each release on PyPI comes from tagged commits on master.

```bash
$ pip install git+https://github.com/mottosso/bleeding-rez.git
```
</details>


<details>
    <summary>Alternative 2 - Latest `dev`</summary>

Where development happens, with commits that are later cherry-picked into `master` and their corresponding feature branch.

```bash
$ pip install git+https://github.com/mottosso/bleeding-rez.git
```
</details>


<details>
    <summary>Alterantive 3 - Specific feature branch</summary>

Each feature works both standalone and together.

```bash
$ pip install git+https://github.com/mottosso/bleeding-rez.git@feature/windows-alias-additional-argument
```
</details>

<br>

### Changes

<table>
    <tr>
        <th width="25%">Feature</th>
        <th>Description</th>
        <th></th>
    </tr>
    <tr></tr>
    <tr>
        <td>Rez & PyPI</td>
        <td>

bleeding-rez is now a standard pip package and available on PyPI.

```bash
$ pip install bleeding-rez
```

`--target` is supported with one caveat on Windows; the destination must be available on your PYTHONPATH either globally or for the user. It cannot be added from within a console, as Rez is looking at your registry for where to find it.

```bash
$ pip install bleeding-rez --target ./some_dir
$ setx PYTHONPATH=some_dir
```
</td>
        <td><a href=https://github.com/mottosso/bleeding-rez/tree/feature/windows-appveyor><i>link</i></a></td>
    <tr></tr>
    </tr>
        <td>Preprocess function</td>
        <td>

`rezconfig.py` can take a `preprocess` function, rather than having to create and manage a separate module and `PYTHONPATH`</td>
        <td><a href=https://github.com/mottosso/bleeding-rez/tree/feature/windows-appveyor><i>link</i></a></td>
    </tr>
    <tr>
        <td>Windows Tests</td>
        <td>Tests now run on both Windows and Linux</td>
        <td><a href=https://github.com/mottosso/bleeding-rez/tree/feature/windows-appveyor><i>link</i></a></td>
    <tr></tr>
    </tr>
        <td>Preprocess function</td>
        <td>

`rezconfig.py` can take a `preprocess` function, rather than having to create and manage a separate module and `PYTHONPATH`</td>
        <td><a href=https://github.com/mottosso/bleeding-rez/tree/feature/windows-appveyor><i>link</i></a></td>
    </tr>
    <tr></tr>
    <tr>
        <td>Aliases & Windows</td>
        <td>

The `package.py:commands()` function `alias` didn't let Windows-users pass additional arguments to their aliases (doskeys)</td>
        <td><a href=https://github.com/mottosso/bleeding-rez/tree/feature/windows-alias-additional-arguments><i>link</i></a></td>
    </tr>
    <tr></tr>
    <tr>
        <td>Pip & Usability</td>
        <td>

As it happens, no one is actually using the `rez pip` command. It has some severe flaws which makes it unusable on anything other than a testing environment on a local machine you don't update.</td>
        <td><a href=https://github.com/mottosso/bleeding-rez/tree/feature/useful-pip><i>link</i></a></td>
    </tr>
    <tr></tr>
    <tr>
        <td>`Request.__iter__`</td>
        <td>

You can now iterate over `request` and `resolve` from within your `package.py:commands()` section, e.g. `for req in request: print(req)`
<td><a href=https://github.com/mottosso/bleeding-rez/tree/feature/iterate-over-request><i>link</i></a></td>
    </tr>
    <tr></tr>
    <tr>
        <td>Pip & Wheels</td>
        <td>

`rez pip` now uses wheels when available, avoiding needless a build step</td>
        <td><a href=https://github.com/mottosso/bleeding-rez/tree/feature/pip-wheels-windows><i>link</i></a></td>
    </tr>
    <tr></tr>
    <tr>
        <td>Pip & Multi-install</td>
        <td>

`rez pip` can now take multiple packages, e.g. `rez pip --install six requests`</td>
        <td><a href=https://github.com/mottosso/bleeding-rez/tree/feature/pip-multipleinstall><i>link</i></a></td>
    </tr>
    <tr></tr>
    <tr>
        <td>Pip & `--prefix`</td>
        <td>

`rez pip` can now take a `--prefix` argument, letting you install packages wherever</td>
        <td><a href=https://github.com/mottosso/bleeding-rez/tree/feature/pip-prefix><i>link</i></a></td>
    </tr>
    <tr>
        <td>PyYAML and Python 3</td>
        <td>

Prior to this, you couldn't use PyYAML and Python 3 as Rez packages.</td>
        <td><a href=https://github.com/mottosso/bleeding-rez/tree/feature/pip-multipleinstall><i>link</i></a></td>
    </tr>
    <tr>
        <td>Auto-create missing repository dir</td>
        <td>

New users no longer have to worry about creating their default package repository directory at `~/packages`, which may seem minor but was the resulting traceback was the first thing any new user would experience with Rez.</td>
        <td><a href=https://github.com/nerdvegas/rez/pull/623><i>PR</i></a></td>
    </tr>
    <tr>
        <td>Cross-platform rez-bind python</td>
        <td>

rez-bind previously used features unsupported on Windows to create the default Python package, now it uses the cross-compatible `alias()` command instead.</td>
        <td><a href=https://github.com/nerdvegas/rez/pull/624><i>PR</i></a></td>
    </tr>
</table>

<br>

### PRs

Along with merged pull-requests from the original repository, as they can take a while to get through (some take years!)

<table>
    <tr>
        <th>

Change</th>
        <th>Description</th>
        <th></th>
    </tr>
    <tr></tr>
    <tr>
        <td>Support for inverse version range</td>
        <td>E.g. `requires = ["urllib3>=1.21.1,<1.23"]`</td>
        <td>[#618](https://github.com/nerdvegas/rez/pull/618)</td>
    </tr>
</table>
