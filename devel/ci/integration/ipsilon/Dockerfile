FROM fedora
RUN curl -o /etc/yum.repos.d/infra-tags.repo https://infrastructure.fedoraproject.org/cgit/ansible.git/plain/files/common/fedora-infra-tags.repo
RUN dnf install -y ipsilon ipsilon-openid ipsilon-openidc ipsilon-authfas patch
COPY devel/ci/integration/ipsilon/api.py /usr/lib/python2.7/site-packages/ipsilon/providers/openid/extensions/api.py
RUN ipsilon-server-install --root-instance --secure no --testauth yes --openid yes --fas yes --hostname id.dev.fedoraproject.org --openid-extensions "insecureAPI,Teams,CLAs,Simple Registration"
RUN sscg --cert-file /etc/pki/tls/certs/localhost.crt --cert-key-file /etc/pki/tls/private/localhost.key
COPY devel/ci/integration/ipsilon/start.sh /usr/local/bin/start.sh
RUN dnf install -y procps-ng elinks
EXPOSE 80 443
CMD /usr/local/bin/start.sh
