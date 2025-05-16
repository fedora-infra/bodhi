bodhi.buildroot_override.tag
----------------------------
::

    {
        "id": "https://bodhi.fedoraproject.org/message-schemas/v1/bodhi.buildroot_override.tag#",
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Schema for message sent when buildroot overrides are tagged",
        "type": "object",
        "properties": {
            "override": {
                "type": "object",
                "properties": {
                    "nvr": {
                        "type": "string",
                        "description": "The NVR of the build that was overridden"
                    },
                    "submitter": {
                        "type": "object",
                        "description": "The user that submitted the override",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The user's account name"
                            }
                        },
                        "required": [
                            "name"
                        ]
                    }
                },
                "required": [
                    "nvr",
                    "submitter"
                ]
            }
        },
        "required": [
            "override"
        ]
    }

bodhi.buildroot_override.untag
------------------------------
::

    {
        "id": "https://bodhi.fedoraproject.org/message-schemas/v1/bodhi.buildroot_override.untag#",
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Schema for message sent when buildroot overrides are untagged",
        "type": "object",
        "properties": {
            "override": {
                "type": "object",
                "properties": {
                    "nvr": {
                        "type": "string",
                        "description": "The NVR of the build that had been overridden"
                    },
                    "submitter": {
                        "type": "object",
                        "description": "The user that submitted the override",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The user's account name"
                            }
                        },
                        "required": [
                            "name"
                        ]
                    }
                },
                "required": [
                    "nvr",
                    "submitter"
                ]
            }
        },
        "required": [
            "override"
        ]
    }

