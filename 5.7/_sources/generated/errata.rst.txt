bodhi.errata.publish
--------------------
::

    {
        "id": "https://bodhi.fedoraproject.org/message-schemas/v1/bodhi.errata.publish#",
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Schema for message sent when an update is pushed to stable",
        "type": "object",
        "properties": {
            "body": {
                "type": "string",
                "description": "The body of an human readable message about the update"
            },
            "subject": {
                "type": "string",
                "description": "A short summary of the update"
            },
            "update": {
                "type": "object",
                "description": "An update",
                "properties": {
                    "alias": {
                        "type": "string",
                        "description": "The alias of the update"
                    },
                    "builds": {
                        "type": "array",
                        "description": "A list of builds included in this update",
                        "items": {
                            "$ref": "#/definitions/build"
                        }
                    },
                    "release": {
                        "type": "object",
                        "description": "A release",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The name of the release e.g. F32"
                            }
                        },
                        "required": [
                            "name"
                        ]
                    },
                    "request": {
                        "type": [
                            "null",
                            "string"
                        ],
                        "description": "The request of the update, if any",
                        "enum": [
                            null,
                            "testing",
                            "obsolete",
                            "unpush",
                            "revoke",
                            "stable"
                        ]
                    },
                    "status": {
                        "type": "string",
                        "description": "The current status of the update",
                        "enum": [
                            null,
                            "pending",
                            "testing",
                            "stable",
                            "unpushed",
                            "obsolete",
                            "side_tag_active",
                            "side_tag_expired"
                        ]
                    },
                    "user": {
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
                    "alias",
                    "builds",
                    "release",
                    "request",
                    "status",
                    "user"
                ]
            }
        },
        "required": [
            "body",
            "subject",
            "update"
        ],
        "definitions": {
            "build": {
                "type": "object",
                "description": "A build",
                "properties": {
                    "nvr": {
                        "type": "string",
                        "description": "The nvr the identifies the build in koji"
                    }
                },
                "required": [
                    "nvr"
                ]
            }
        }
    }

