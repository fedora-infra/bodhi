import socket
hostname = socket.gethostname().split('.')[0]

from bodhi.release import VERSION as version

__all__ = ('version', 'hostname')
