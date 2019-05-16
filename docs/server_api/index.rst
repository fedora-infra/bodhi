=================
Bodhi Server APIs
=================

Message API
===========

Bodhi sends a number of AMQP messages. Each message has a formally defined schema. Bodhi provides a
convenient ``bodhi.messages`` Python package that allows you to interact with messages
via handy Python classes. If you are unable to use Python 3.6+, Bodhi also publishes its message
schemas via `JSON Schema`_.

.. warning:: Bodhi's messages do contain fields that are not documented in its JSON schemas. Bodhi
   does not make any guarantees about data that is not documented in its schema, and thus it is
   subject to change. Please work with the Bodhi project if you need data that is not part of
   Bodhi's schemas.


.. toctree::
   :maxdepth: 2

   messages/base
   messages/buildroot_override
   messages/compose
   messages/errata
   messages/update


REST API
========

This section of the documentation describes Bodhi's REST API. You can read about the various
sections of the API by following the links below:


.. toctree::
   :maxdepth: 2

   rest/builds
   rest/comments
   rest/composes
   rest/csrf
   rest/markdown
   rest/overrides
   rest/packages
   rest/releases
   rest/schemas
   rest/updates
   rest/users


.. _JSON Schema: https://json-schema.org/
