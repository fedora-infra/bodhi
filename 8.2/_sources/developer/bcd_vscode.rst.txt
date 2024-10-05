=================================
Debugging with Visual Studio Code
=================================

Visual Studio Code's `Dev Containers <https://code.visualstudio.com/docs/devcontainers/containers>` extension may be able to use the environment provided by Vagrant,
with support for discovering, running and debugging unit-tests. The person who implemented BCD
doesn't use VS Code, so we don't really know. Please try it and tell us, then we can make this
doc better.

This provides an IDE alternative to running `btest` from `./bcd shell`.

This assumes you have working environment as described in :doc:`BCD - the Bodhi Container Development environment <bcd>`

Configure VS Code for BCD
=========================

Since BCD uses podman, `this handy guide from Stack Overflow <https://stackoverflow.com/questions/77167514>` should help.
You want to start the BCD containers as described in the BCD page, then set up podman so VS Code will be able to see it
(as explained on the SO question), then finally have VS Code attach to the running bodhi-dev-bodhi container. The upstream
VS Code docs explain that to attach to a running container, you should either select Dev Containers: Attach to Running Container
from the Command Palette (F1) or use the Remote Explorer in the Activity Bar and from the Containers view, select the
Attach to Container inline action on the container you want to connect to.

Again, we haven't tried this. Sorry. Let us know how it goes. The following instructions are preserved mostly unmodified
from when this page documented using VS Code with Vagrant. They're probably still more or less relevant to BCD.

Debugging application running in BCD
====================================

When inside the container set the debug configuration in `launch.json` for Pyramid (you should get the pyramid conf as a suggestion)::

  {
    "version": "0.2.0",
    "configurations": [
      {
          "name": "Python: Pyramid Application",
          "type": "python",
          "request": "launch",
          "module": "pyramid.scripts.pserve",
          "args": [
              "/home/vagrant/development.ini"
          ],
          "pyramid": true,
          "jinja": false,
      },

When you want to start application for debugging, you first need to run `systemctl stop bodhi` in the container shell,
otherwise the debugger will complain about ports already in use, as it will launch another instance of bodhi inside of the application.

After you stopped the bodhi service, you can run the "Python: Pyramid Application" from the Debug pane (Ctrl+Shift+D) and
the application will stop on breakpoints.

Debugging unit-tests
====================

For running unit-tests install `Python Test Explorer for Visual Studio Code <https://marketplace.visualstudio.com/items?itemName=littlefoxteam.vscode-python-test-adapter>` extension
Open settings (CTRL+Comma), and in the settings for the container, swith to JSON view and make the following configuration changes::

  {
    "python.testing.pytestEnabled": true,
    "python.testing.pytestPath": "py.test-3",
    "pythonTestExplorer.testFramework": "pytest",
    "python.pythonPath": "python3",
	  "python.testing.pytestArgs": ["--no-cov"]
  }

Currently coverage reporting and debugging don't work at the same time, due to a reported issue.
Currently suggested workaround is to disable the coverage-reporting with `--no-cov` parameter.
The issue is currently tracked in https://github.com/microsoft/vscode-python/issues/693

After configuring you should be able to populate the test-explorer with unit tests and start debugging!

Debugging celery
================
If you want to debug code running in the celery worker, you first need to stop the celery service and then start celery from inside vs-code,
in similar fashion as you'd run `pserve` in previous example.
