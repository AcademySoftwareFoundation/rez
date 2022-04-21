Whenever Rez releases a new versioned tag, this documentation is automatically built.

TODO : Replace this URL once there's a real URL, later
You can see the documentation here: https://rez-rtd-test.readthedocs.io/en/latest

However, if you'd like to build the documentation locally, you can do so using
these steps:

- Install virtualenv

```sh
python3 -m pip install virtualenv --user
```

- Create a virtual environment and source it

```sh
virtualenv rez_documentation_environment
source rez_documentation_environment/bin/activate
```

- Install the pip requirements

```sh
python -m pip install --requirement requirements.txt
```

- Now build the documentation

```sh
sphinx-build . _build
```

If all goes well, you should be able to view the documentation in any website
browser (Firefox, Chromium, etc).

```sh
firefox _build/index.html
```
