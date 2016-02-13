# Plover Development on OS X

## Getting Started
- Run `./bootstrap.sh`.
- Run `make app` to produce `../dist/Plover.app`.
  - If you want a disk image instead, use: `make dmg`
  - Standard development practice is to use `make clean app` to produce
    a clean rebuild of the app.


## Gotcha: Granting Assistive Device Permission
After each build, you need to approve Plover as an Assistive Device:

- Open System Preferences
- Open the Security & Privacy pane
- Select the Privacy tab
- Select "Accessibility" from the source list on the left
- Click the "+" button below the list off apps
- Use the file picker to select the Plover.app that you just built

Now you can run the app by double-clicking on it
or by using open(1):

    open ../dist/Plover.app

### Dev Workaround: Run as Root
Root doesn't need permission to use event taps,
so during development, you can avoid this rigmarole by running Plover via:

```
sudo python launch.py
```


## Dependencies
The bootstrap script takes care of these for you, but in case you're curious:

- Python2.7: `brew install python --framework`
- wxPython: `brew install wxpython`
- Various Python libraries, for which see
  [requirements.txt](./requirements.txt).


### Xcode Tools
You need the Xcode command-line tools.
The bootstrap script will walk you through this.

If you want to check for yourself, try running `clang` in Terminal.app.
You will receive a prompt if the tools are not installed
with instructions for how to install them.



## Using Virtualenv

Because wxPython is very virtualenv-unfriendly,
it is recommended _not_ to use a virtual environment for working on Plover.

If you insist on bulling through this, though, here goes nothing.

### Create a Virtual Environment
Create an environment using virtualenv (1.11.6) from virtualenv.org.
Once in the virtualenv (i.e. activate the environment),
you’ll want to update pip and setuptools.


### Hack wxPython into the Environment
You need to hack your virtualenv to have wxPython.

*If you want to understand what you’re about to do, you can
[read up on it at the wxPython Wiki.](http://wiki.wxpython.org/wxPythonVirtualenvOnMac)*

Run these commands while in the top directory of your plover virtualenv:

```bash
ln -s /Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/site-packages/wxredirect.pth lib/python2.7/site-packages
mv bin/python bin/bad_python
ln -s /Library/Frameworks/Python.framework/Versions/2.7/bin/python bin/python
echo 'PYTHONHOME=$VIRTUAL_ENV; export PYTHONHOME' >> bin/activate
```


### Fix a bug in py2app or modulegraph
There is a bug right now between py2app and modulegraph:

https://bitbucket.org/ronaldoussoren/modulegraph/issue/22/scan_code-in-modulegraphpy-contains-a

Until it’s fixed, we need to fix it ourselves by rewriting all calls
to `scan_code` to instead call `_scan_code`
and all calls to `load_module` to instead call `_load_module`,
that is, we need to underscore-prefix `scan_code` and `load_module`.

A quick fix that you can run from the root of the virtualenv:

`sed -i .bak -e 's/\.scan_code/._scan_code/' -e 's/\.load_module/._load_module/' lib/python2.7/site-packages/py2app/recipes/virtualenv.py`
