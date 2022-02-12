# rez-wiki

This directory holds the content used to produce the Rez Wiki documentation
found [here](https://github.com/nerdvegas/rez/wiki). The wiki is updated by the
`Wiki` Github workflow, on release.

You should include relevant wiki updates with your code PRs.

## Testing

To test wiki updates locally:

* Make your changes to any pages/* or media/* files;
* Run `python ./generate-wiki.py`
* View the resulting content in the `out` directory using your markdown viewer
  of choice (we suggest [grip](https://github.com/joeyespo/grip)).
