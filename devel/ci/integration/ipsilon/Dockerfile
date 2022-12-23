FROM fedora:latest
RUN curl -o /etc/yum.repos.d/infra-tags.repo https://pagure.io/fedora-infra/ansible/raw/main/f/files/common/fedora-infra-tags.repo
RUN dnf install -y ipsilon ipsilon-openid ipsilon-openidc patch git
RUN git clone https://pagure.io/fedora-infra/ipsilon-fedora.git /opt/ipsilon-fedora
RUN cd /opt/ipsilon-fedora && ./install.sh
RUN ipsilon-server-install --root-instance --secure no --testauth yes --openid yes --openidc yes --hostname id.dev.fedoraproject.org --openid-extensions "insecureAPI,Teams,CLAs,Simple Registration"
RUN sscg \
    --ca-file /etc/pki/tls/certs/localhost-ca.crt \
    --cert-file /etc/pki/tls/certs/localhost.crt \
    --cert-key-file /etc/pki/tls/private/localhost.key \
    --hostname id.dev.fedoraproject.org \
    --subject-alt-name ipsilon.ci \
    --subject-alt-name ipsilon
COPY devel/ci/integration/ipsilon/setup-bodhi.py /usr/local/bin/setup-bodhi.py
RUN python3 /usr/local/bin/setup-bodhi.py
COPY devel/ci/integration/ipsilon/start.sh /usr/local/bin/start.sh
RUN dnf install -y procps-ng elinks
EXPOSE 80 443
CMD /usr/local/bin/start.sh
