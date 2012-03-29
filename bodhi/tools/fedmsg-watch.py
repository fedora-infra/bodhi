#!/usr/bin/env python

import pprint
import simplejson
import zmq

def main():
    # Prepare our context and publisher
    context = zmq.Context(1)
    subscriber = context.socket(zmq.SUB)
    subscriber.connect("tcp://127.0.0.1:6543")  # <-- set in fedmsg.ini
    subscriber.setsockopt(zmq.SUBSCRIBE, '')

    try:
        while True:
            topic, msg = subscriber.recv_multipart()
            pprint.pprint(simplejson.loads(msg))
    except Exception as e:
        print str(e)
    finally:
        subscriber.close()
        context.term()

if __name__ == "__main__":
    main()
