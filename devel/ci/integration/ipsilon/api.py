# Copyright (C) 2015 Patrick Uiterwijk, for license see Ipsilon's COPYING:
# https://forge.fedoraproject.org/apps/ipsilon/src/branch/master/COPYING


import inspect
import json

import ipsilon.root
from ipsilon.providers.openid.extensions.common import OpenidExtensionBase
from ipsilon.util.page import Page
from ipsilon.util.user import User


class OpenidExtension(OpenidExtensionBase):
    def __init__(self, *pargs):
        super().__init__("insecureAPI")

    def enable(self):
        """
        Enable the OpenID extension.

        This method retrieves the root application object to register the API page.
        """
        root_obj = self._retrieve_root_object()
        root_obj.api = APIPage(root_obj)

    def _retrieve_root_object(self):
        """
        Retrieve the Ipsilon root application object.

        This method inspects the call stack to find the root object, as it is not
        directly passed to the extension's enable method by the framework.
        """
        # Note: This approach uses stack inspection to locate the 'self' variable
        # from the caller's frame, which corresponds to the root application object.
        # This is necessary because the OpenID extension system does not currently
        # expose the root object to extensions.
        #
        # Stack index [6] is used because:
        # - Frame 0: inspect.stack() call itself
        # - Frame 1: This helper method (_retrieve_root_object)
        # - Frames 2-5: OpenID extension framework call chain
        # - Frame 6: Root application object (target)
        #
        # Note: Before refactoring into a helper method, this was [5] when the code
        # was inline in enable(). The helper method itself adds one extra frame.
        return inspect.stack()[6][0].f_locals["self"]


class APIPage(Page):
    def __init__(self, root_obj):
        ipsilon.root.sites["api"] = dict()
        ipsilon.root.sites["api"]["template_env"] = ipsilon.root.sites["default"][
            "template_env"
        ]
        super().__init__(ipsilon.root.sites["api"])
        self.v1 = APIV1Page(root_obj)


class APIV1Page(Page):
    def __init__(self, root_obj):
        ipsilon.root.sites["api_v1"] = dict()
        ipsilon.root.sites["api_v1"]["template_env"] = ipsilon.root.sites["default"][
            "template_env"
        ]
        super().__init__(ipsilon.root.sites["api_v1"])
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
                "email": f"{username}@example.com",
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
        fake_session.get_user = lambda *args: us_obj
        fake_session.get_user_attrs = lambda *args: userdata

        openid_response = openid._response(openid_request, fake_session)
        openid_response = openid.cfg.server.signatory.sign(
            openid_response
        ).fields.toPostArgs()
        return {"success": True, "response": openid_response}
