mkdir /httpdir/run
ln -s /etc/httpd/modules /httpdir/modules
truncate --size=0 /httpdir/accesslog /httpdir/errorlog
tail -qf /httpdir/accesslog /httpdir/errorlog &
exec httpd -f /etc/bodhi/httpd.conf -DFOREGROUND -DNO_DETACH
