#!/usr/bin/env python3

from configparser import ConfigParser
import sys

from oidc_register import discovery, registration


REDIRECT_URI = "https://bodhi-dev.example.com/oidc/authorize"
PROVIDER_URL = "https://ipsilon.tinystage.test/idp/openidc/"
CONFIG_FILE = "/home/vagrant/development.ini"
PLACEHOLDERS = {
    "client_id": "oidc-client_id",
    "client_secret": "oidc-client_secret",
}


def main():
    config = ConfigParser()
    config.read(CONFIG_FILE)
    for confkey in ("client_id", "client_secret"):
        if config["app:main"][f"oidc.fedora.{confkey}"] != PLACEHOLDERS[confkey]:
            print("Bodhi is already registered, aborting")
            print(config["app:main"][f"oidc.fedora.{confkey}"], PLACEHOLDERS[confkey])
            sys.exit(0)

    registration.check_redirect_uris([REDIRECT_URI])
    try:
        OP = discovery.discover_OP_information(PROVIDER_URL)
    except Exception as ex:
        print('Error discovering OP information')
        print(ex)
        sys.exit(1)

    if 'registration_endpoint' not in OP:
        print('Provider does not support dynamic client registration')
        print(OP)
        sys.exit(1)

    try:
        reg_info = registration.register_client(OP, [REDIRECT_URI])
    except Exception as ex:
        print('Error registering client')
        print(ex)
        sys.exit(1)

    config["app:main"]["oidc.fedora.client_id"] = reg_info["web"]["client_id"]
    config["app:main"]["oidc.fedora.client_secret"] = reg_info["web"]["client_secret"]
    config["app:main"]["oidc.fedora.server_metadata_url"] = \
        f'{reg_info["web"]["issuer"]}.well-known/openid-configuration'

    with open(CONFIG_FILE, "w") as config_file:
        config.write(config_file)
    print("Bodhi is now registered with Ipsilon.")


if __name__ == "__main__":
    main()
