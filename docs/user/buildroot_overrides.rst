===================
Buildroot Overrides
===================

Koji's buildroot is the set of packages that are available to use during a build. Normally this set
of packages only includes packages that have been marked as stable in Bodhi. There are times when a
developer will want to add a package to Koji's buildroot that is not yet stable so that it can be
used to build another package. This is where Bodhi's buildroot override functionality comes into
play.

Developers can create a buildroot override in Bodhi's create menu in the upper right hand corner, or
they can use the :doc:`man_pages/bodhi` command line interface to do it.

Once a buildroot override is created, Bodhi will present a hint to the developer describing how to
use the ``koji`` CLI to wait for the override to appear in the buildroot. Once ``koji`` confirms the
package is present in the buildroot, subsequent builds that depend on it may be performed.

Buildroot overrides have expiration dates, and Bodhi will automatically remove them from the build
root when those dates are reached. Developers can also use the web interface or CLI to manually
expire them if desired.
