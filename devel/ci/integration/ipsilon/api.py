# Copyright (C) 2015 Patrick Uiterwijk, for license see Ipsilon's COPYING:
# https://pagure.io/ipsilon/blob/master/f/COPYING

from __future__ import absolute_import

import json
import inspect

from ipsilon.providers.openid.extensions.common import OpenidExtensionBase
import ipsilon.root
from ipsilon.util.page import Page
from ipsilon.util.user import User


class OpenidExtension(OpenidExtensionBase):
    def __init__(self, *pargs):
        super(OpenidExtension, self).__init__("insecureAPI")

    def enable(self):
        # This is the most ugly hack in my history of python...
        # But I need to find the root object, and that is not passed into
        #  the OpenID extension system anywhere...
        root_obj = inspect.stack()[5][0].f_locals["self"]
        root_obj.api = APIPage(root_obj)


class APIPage(Page):
    def __init__(self, root_obj):
        ipsilon.root.sites["api"] = dict()
        ipsilon.root.sites["api"]["template_env"] = ipsilon.root.sites["default"][
            "template_env"
        ]
        super(APIPage, self).__init__(ipsilon.root.sites["api"])
        self.v1 = APIV1Page(root_obj)


class APIV1Page(Page):
    def __init__(self, root_obj):
        ipsilon.root.sites["api_v1"] = dict()
        ipsilon.root.sites["api_v1"]["template_env"] = ipsilon.root.sites["default"][
            "template_env"
        ]
        super(APIV1Page, self).__init__(ipsilon.root.sites["api_v1"])
        self.root_obj = root_obj

    def root(self, *args, **kwargs):
        return json.dumps(self._perform_call(kwargs))

    def _perform_call(self, arguments):
        required_arguments = ["auth_module", "username", "password"]
        for arg in required_arguments:
            if arg not in arguments:
                return {
                    "success": False,
                    "status": 400,
                    "message": "Missing argument: %s" % arg,
                }

        openid = self.root_obj.openid

        openid_request = None
        try:
            openid_request = openid.cfg.server.decodeRequest(arguments)
        except Exception as ex:
            print("Error during openid decoding: %s" % ex)
            return {"success": False, "status": 400, "message": "Invalid request"}
        if not openid_request:
            print("No OpenID request parsed")
            return {"success": False, "status": 400, "message": "Invalid request"}
        if not arguments["auth_module"] == "fedoauth.auth.fas.Auth_FAS":
            print("Unknown auth module selected")
            return {
                "success": False,
                "status": 400,
                "message": "Unknown authentication module",
            }
        username = arguments["username"]
        password = arguments["password"]
        userdata = None
        if password == "ipsilon":
            userdata = {
                "username": username,
                "nickname": username,
                "email": "{}@example.com".format(username),
                "_groups": ["packager", "provenpackager"],
                "_extras": {
                    "cla": ["http://admin.fedoraproject.org/accounts/cla/done"]
                },
            }

        if userdata is None:
            print("No user or data: %s, %s" % (username, userdata))
            return {"success": False, "status": 400, "message": "Authentication failed"}

        us_obj = User(username)

        def fake_session():
            return None
        setattr(fake_session, "get_user", lambda *args: us_obj)
        setattr(fake_session, "get_user_attrs", lambda *args: userdata)

        openid_response = openid._response(openid_request, fake_session)
        openid_response = openid.cfg.server.signatory.sign(
            openid_response
        ).fields.toPostArgs()
        return {"success": True, "response": openid_response}
