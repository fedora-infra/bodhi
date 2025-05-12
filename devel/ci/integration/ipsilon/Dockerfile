FROM quay.io/fedora/fedora:38
# should be specified as hostname:port to listen on a non-standard port
ARG hostname=id.dev.fedoraproject.org
# can be a comma-separated list
ARG redirect=http://bodhi.ci:8080/oidc/authorize
ARG clienturi=http://bodhi.ci:8080/oidc/
# to listen on a non-standard port, specify this too, it's dumb but you can't do
# conditionals or string parsing in dockerfiles...only used for EXPOSE anyway
ARG listen=80
RUN curl -o /etc/yum.repos.d/infra-tags.repo https://pagure.io/fedora-infra/ansible/raw/main/f/files/common/fedora-infra-tags.repo

RUN dnf install -y ipsilon ipsilon-openid ipsilon-openidc patch git sed systemd procps-ng elinks
RUN git clone https://pagure.io/fedora-infra/ipsilon-fedora.git /opt/ipsilon-fedora \
    && cd /opt/ipsilon-fedora \
    && ./install.sh
RUN ipsilon-server-install --root-instance --secure no --testauth yes --testauth-groups "fedora-contributors,packager" --openid yes --openidc yes --hostname $hostname --openid-extensions "insecureAPI,Teams,CLAs,Simple Registration" --openidc-extensions "fedora-account,waiverdb" --openidc-default-attribute-mapping '[["*", "*"], ["_groups", "groups"], [["_extras", "cla"], "cla"], ["fullname", "name"], ["_username", "nickname"], ["_username", "preferred_username"], ["fasIRCNick", "ircnick"], ["fasLocale", "locale"], ["fasTimeZone", "zoneinfo"], ["fasTimeZone", "timezone"], ["fasWebsiteURL", "website"], ["fasGPGKeyId", "gpg_keyid"], ["ipaSshPubKey", "ssh_key"], ["fasIsPrivate", "privacy"], ["fullname", "human_name"]]'
# RUN sscg \
#     --ca-file /etc/pki/tls/certs/localhost-ca.crt \
#     --cert-file /etc/pki/tls/certs/localhost.crt \
#     --cert-key-file /etc/pki/tls/private/localhost.key \
#     --hostname $hostname \
#     --subject-alt-name ipsilon.ci \
#     --subject-alt-name ipsilon
RUN \
    dnf -y install openssl && \
    cd /root && \
    curl -L -o easyrsa.tgz https://github.com/OpenVPN/easy-rsa/releases/download/v3.2.2/EasyRSA-3.2.2.tgz && \
    tar -xf /root/easyrsa.tgz && \
    mv EasyRSA* easyrsa && \
    cd easyrsa && \
    ./easyrsa init-pki && \
    ./easyrsa --batch --bc-crit build-ca nopass && \
    ./easyrsa --batch --bc-crit --san=DNS:ipsilon.ci --san=DNS:ipsilon --san=DNS:id.dev.fedoraproject.org build-server-full id.dev.fedoraproject.org nopass && \
    cp ./pki/ca.crt /etc/pki/tls/certs/localhost-ca.crt && \
    cp ./pki/issued/id.dev.fedoraproject.org.crt /etc/pki/tls/certs/localhost.crt && \
    cp ./pki/private/id.dev.fedoraproject.org.key /etc/pki/tls/private/localhost.key && \
    chmod 644 /etc/pki/tls/certs/localhost-ca.crt /etc/pki/tls/certs/localhost.crt
COPY devel/ci/integration/ipsilon/setup-bodhi.py.tmpl /tmp/setup-bodhi.py.tmpl
RUN sed -e "s|##REDIRECT##|$redirect|g" -e "s,##CLIENTURI##,$clienturi,g" /tmp/setup-bodhi.py.tmpl > /usr/local/bin/setup-bodhi.py && chmod ugo+x /usr/local/bin/setup-bodhi.py
RUN python3 /usr/local/bin/setup-bodhi.py
RUN systemctl enable httpd.service
COPY devel/ci/integration/ipsilon/start.sh /usr/local/bin/start.sh
EXPOSE 80 443 $listen
RUN systemctl enable httpd.service
CMD /usr/local/bin/start.sh
