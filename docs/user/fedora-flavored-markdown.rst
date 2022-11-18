========================
Fedora-Flavored Markdown
========================

Description
===========

Text fields in Bodhi2 support an enhanced version of `markdown`_. This is a cheat
sheet for your reference.

Be advised that, even if Bodhi supports a wide set of markups, the update notes
will be used for the description field in appstream tag, which instead supports
only a `reduced set
<https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html#tag-description>`_
of markups. Unsupported markup may be showed as plain text
or lead to unexpected beahvior in package managers GUI!

You can do **HEADERS** by underlining or by prefixing with the ``#`` character:

.. code-block:: html

  This is an H1
  =============

  This is an H2
  -------------

  # This is another H1

  ## This is another H2


You can do **BLOCKQUOTES** using email-style prefixes with the ``>`` character::

  > This is a quotation
  > over many lines
  > > and it can be nested(!)

**LISTS** work like you'd expect, by prefixing with any of the ``*``, ``+``,
or ``-`` characters:

.. code-block:: html

  Check out this list:

  * This
  * is
  * a list...

You need a blank line between a paragraph and the start of a list for the
renderer to pick up on it.

**EMPHASIS** can be addedd like this::

  *italics*
  _italics_
  **bold**
  __bold__

You can save your code references from being misinterpreted as emphasis by
surrounding them with backtick characters (`````)::

  Use `the_best_function()` and _not_ that crummy one

**LINKS** look like this::

  [text](http://getfedora.org)

...but we also support bare links if you just provide a URL.

You can create **CODE BLOCKS** by indenting every line of the block by at
least 4 spaces or 1 tab.

.. code-block:: html
  
  Here is a code block:
    for i in range(4):
      print i
    print("done")

You can reference **BUG REPORTS** by simply writing something of the form
``tracker#ticketid``.

.. code-block:: html

  This fixes PHP#1234 and Python#2345

...we will automatically generate links to the tickets in the appropriate
trackers in place. The supported bug tracker prefixes are:
(these are all case-insensitive)

.. code-block:: html

  Fedora, RHBZ and RH (all point to the Red Hat Bugzilla)
  GCC
  GNOME
  KDE
  Mozilla
  PEARL
  PEAR
  PHP
  Python
  SOURCEWARE

And you can refer to **OTHER USERS** by prefixing their username with the
``@`` symbol.

::

  Thanks @mattdm

This will generate a link to their profile, but it won't necessarily send
them a notification unless they have a special
`FMN <https://apps.fedoraproject.org/notifications>`_ rule set up to catch it.

Lastly, you can embed inline **IMAGES** with syntax like this::

  ![Alt text](/path/to/img.jpg)

.. _enhanced: https://github.com/fedora-infra/bodhi/blob/develop/bodhi/server/ffmarkdown.py
.. _markdown: http://daringfireball.net/projects/markdown/syntax
