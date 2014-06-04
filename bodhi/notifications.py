import fedmsg
import bodhi
import bodhi.config


def publish(topic, msg):
    if not bodhi.config.config.get('fedmsg_enabled'):
        bodhi.log.warn("fedmsg disabled.  not sending %r" % topic)
        return

    bodhi.log.debug("fedmsg sending %r" % topic)
    fedmsg.publish(topic=topic, msg=msg)
