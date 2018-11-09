FROM centos:7
LABEL \
  name="resultsdb" \
  vendor="Fedora Infrastructure" \
  maintainer="Aurelien Bompard <abompard@fedoraproject.org>" \
  license="MIT"

RUN yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm

# The echo works around https://bugzilla.redhat.com/show_bug.cgi?id=1483553 and any other future yum
# upgrade bugs.
RUN yum upgrade -y || echo "We are not trying to test dnf upgrade, so ignoring dnf failure."

# Install deps
RUN yum install -y \
    httpd \
    mod_wsgi \
    resultsdb \
    python-psycopg2

# Configuration
COPY devel/ci/integration/resultsdb/settings.py /etc/resultsdb/settings.py
COPY devel/ci/integration/resultsdb/httpd.conf /etc/httpd/conf.d/resultsdb.conf

EXPOSE 80
CMD ["/usr/sbin/httpd", "-DFOREGROUND"]
