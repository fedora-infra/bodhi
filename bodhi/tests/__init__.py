# -*- coding: utf-8 -*-
"""Unit and functional test suite for bodhi."""

from sqlalchemy import create_engine

from bodhi.models import initialize_sql

def setup_db():
    """Method used to build a database"""
    engine = create_engine('sqlite:///:memory:')
    initialize_sql(engine)

def teardown_db():
    """Method used to destroy a database"""
    #engine = config['pylons.app_globals'].sa_engine
    #model.metadata.drop_all(engine)
