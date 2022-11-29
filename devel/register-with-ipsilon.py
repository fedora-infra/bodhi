#!/usr/bin/env python3

from argparse import ArgumentParser
from configparser import ConfigParser
import os
import sys

from oidc_register import discovery, registration


REDIRECT_URI = "https://bodhi-dev.example.com/oidc/authorize"
PROVIDER_URL = "https://ipsilon.tinystage.test/idp/openidc/"
PLACEHOLDERS = {
    "client_id": "oidc-client_id",
    "client_secret": "oidc-client_secret",
}


def main():
    parser = ArgumentParser(description='Register Bodhi Server with an OIDC provider.')
    parser.add_argument(
        "config_file",
        nargs="?",
        default="/home/vagrant/development.ini",
        help="Bodhi server's configuration file",
    )
    args = parser.parse_args()
    if not os.path.exists(args.config_file):
        print(f"No such file: {args.config_file}", file=sys.stderr)
        sys.exit(1)
    config = ConfigParser()
    config.read(args.config_file)
    for confkey in ("client_id", "client_secret"):
        if config["app:main"][f"oidc.fedora.{confkey}"] != PLACEHOLDERS[confkey]:
            print("Bodhi is already registered, aborting.")
            return

    registration.check_redirect_uris([REDIRECT_URI])
    try:
        OP = discovery.discover_OP_information(PROVIDER_URL)
    except Exception as ex:
        print('Error discovering OP information', file=sys.stderr)
        print(ex, file=sys.stderr)
        sys.exit(1)

    if 'registration_endpoint' not in OP:
        print('Provider does not support dynamic client registration', file=sys.stderr)
        print(OP, file=sys.stderr)
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

    with open(args.config_file, "w") as config_file:
        config.write(config_file)
    print("Bodhi is now registered with Ipsilon.")


if __name__ == "__main__":
    main()
