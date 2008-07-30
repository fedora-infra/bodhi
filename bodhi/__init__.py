import socket
hostname = socket.gethostname()

from bodhi.release import VERSION as version

__all__ = ('version', 'hostname')
