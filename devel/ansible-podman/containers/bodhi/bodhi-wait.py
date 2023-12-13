#!/usr/bin/python3

import time

from bodhi.server.config import config
from sqlalchemy import engine_from_config
from sqlalchemy.exc import OperationalError

config.load_config()
engine = engine_from_config(config)


# stolen from waiverdb, GPLv2+, thanks Dan Callaghan
def wait_for_db():
    poll_interval = 10  # seconds
    while True:
        try:
            engine.connect()
        except OperationalError as e:
            print('Failed to connect to database: {}'.format(e))
            print(f'Sleeping for {poll_interval} seconds...')
            time.sleep(poll_interval)
            print('Retrying...')
        else:
            break


if __name__ == '__main__':
    wait_for_db()
