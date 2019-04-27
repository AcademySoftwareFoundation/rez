![image](https://user-images.githubusercontent.com/2152766/56459362-3eb1ff00-638a-11e9-9db4-6ae83f6dc70f.png)

Rez, with all [feature branches](https://github.com/mottosso/bleeding-rez/branches/all?utf8=%E2%9C%93&query=feature%2F) merged.

<br>

<table>
    <tr>
        <th width="20%">Feature</th>
        <th>Description</th>
        <th></th>
    </tr>
    <tr></tr>
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

<br>

### A note on backwards compatibility

1. This repo is fully backwards compatible with Rez
1. The master branch is fully functional
1. Every added feature or change have a corresponding PR in the original Rez repo

However.

1. Not all new features are guaranteed or expected to last
1. Not all new features are guaranteed or expected to merge with Rez

It is an experimental, development fork of Rez with the intent on exploring new usecases and features beyond the hypothetical stage.