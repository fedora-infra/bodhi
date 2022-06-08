============================================
Debugging with Visual Studio Code
============================================

Visual Studio Code with its Remote - SSH extension can utilize the environment provided by Vagrant,
with support for discovering, running and debugging unit-tests.

This provides an IDE alternative to running `btest` from `vagrant ssh` shell.

This assumes you have working environment as described in :doc:`Bodhi Vagrant Guide <vagrant>`

Configure VS Code for Remote SSH
================================

To configure VS Code to access Vagrant Environment you first need to install the `Remote - SSH <https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-ssh>` extension

Get the ssh configuration for connecting to the vagrant-box::

  $ vagrant ssh-config
  Host bodhi
    HostName 192.168.122.225
    User vagrant
    Port 22
    UserKnownHostsFile /dev/null
    StrictHostKeyChecking no
    PasswordAuthentication no
    IdentityFile ~/work/bodhi/.vagrant/machines/bodhi/libvirt/private_key
    IdentitiesOnly yes
    LogLevel FATAL

If you have only one vagrant-box running, you should be able to just copy the configuration to your `~/.ssh/config` and test it::

  $ ssh bodhi
  Welcome to the Bodhi development environment! Here are some helpful commands:

In Visual Studio Code, press F1 and run the `Remote-SSH: Open SSH Host...`, you should be prompted for a ssh command,
if you have `~/.ssh/config` setup, using `ssh bodhi` should be sufficient. Now you can connect to the vagrant box with VS Code.

Debugging application running in Vagrant
========================================

When inside the SSH remote set the debug configuration in `launch.json` for Pyramid (you should get the pyramid conf as a suggestion)::

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

When you want to start application for debugging, you first need to run `sudo systemctl stop bodhi` in the vagrant's shell,
otherwise the debugger will complain about ports already in use, as it will launch another instance of bodhi inside of the application.

After you stopped the bodhi service, you can run the "Python: Pyramid Application" from the Debug pane (Ctrl+Shift+D) and
the application will stop on breakpoints.

Debugging unit-tests
===========================

For running unit-tests install `Python Test Explorer for Visual Studio Code <https://marketplace.visualstudio.com/items?itemName=littlefoxteam.vscode-python-test-adapter>` extension
Open settings (CTRL+Comma), and in the settings for the SSH Remote, swith to JSON view and make the following configuration changes::

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

After configuring you sould be able to populate the test-explorer with unit-tests and start debugging :-)

Debugging celery
===========================
If you want to debug code running in hte celery worker, you first need to stop the celery service and then start celery from inside vs-code,
in simmilar fashion as you'd run `pserve` in previous example.
