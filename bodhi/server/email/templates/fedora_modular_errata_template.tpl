--------------------------------------------------------------------------------
Fedora Modular%(testing)s Update Notification
%(updateid)s
%(date)s
--------------------------------------------------------------------------------

Name        : %(name)s
Product     : %(product)s
Version     : %(version)s
Release     : %(release)s
URL         : %(url)s
Summary     : %(summary)s
Description :
%(description)s

--------------------------------------------------------------------------------
%(notes)s%(changelog)s%(references)s
This update can be installed with the "dnf" update program. Use
su -c 'dnf%(yum_repository)s upgrade --advisory %(updateid)s' at the command
line. For more information, refer to the dnf documentation available at
http://dnf.readthedocs.io/en/latest/command_ref.html#upgrade-command-label

All packages are signed with the Fedora Project GPG key. More details on the
GPG keys used by the Fedora Project can be found at
https://fedoraproject.org/keys
--------------------------------------------------------------------------------
