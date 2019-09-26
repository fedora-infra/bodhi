#!/bin/bash
tail --retry -f /var/log/httpd/{,ssl_}{access,error}_log &
exec /usr/sbin/httpd -X
