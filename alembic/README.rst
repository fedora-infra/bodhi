This folder contains the stuff to migrate the Bodhi database. We use
`alembic`_ for that.

.. _alembic: https://pypi.python.org/pypi/alembic

Create a new migration script
=============================

Say you've modified a model in ``bodhi/server/models.py``. You now need to
create a migration script, so that the current database can be "upgraded" to
your new model.

This is what you'd do::

    $ alembic revision --autogenerate -m "Add the foo table"

And that's it, alembic will compare your model with the current database, and
generate a new script in ``alembic/versions/``.

Open it up, and make sure it's correct.

When you're happy with it, upgrade your database::

    $ alembic upgrade head
