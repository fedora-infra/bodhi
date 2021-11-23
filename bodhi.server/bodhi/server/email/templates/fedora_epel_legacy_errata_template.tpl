--------------------------------------------------------------------------------
Fedora EPEL%(testing)s Update Notification
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
This update can be installed with the "yum" update programs.  Use
su -c 'yum%(yum_repository)s update %(name)s' at the command line.
For more information, refer to "YUM", available at
https://access.redhat.com/documentation/en-US/Red_Hat_Enterprise_Linux/7\
/html/System_Administrators_Guide/ch-yum.html

All packages are signed with the Fedora EPEL GPG key.  More details on the
GPG keys used by the Fedora Project can be found at
https://fedoraproject.org/keys
--------------------------------------------------------------------------------
