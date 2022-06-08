bodhi.compose.complete
----------------------
::

    {
        "id": "https://bodhi.fedoraproject.org/message-schemas/v1/bodhi.compose.complete#",
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Schema for message sent when composes finish",
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "The name of the user who started this compose."
            },
            "repo": {
                "type": "string",
                "description": "The name of the repository being composed."
            },
            "success": {
                "type": "boolean",
                "description": "true if the compose was successful, false otherwise."
            },
            "ctype": {
                "type": "string",
                "description": "Type of the compose."
            }
        },
        "required": [
            "agent",
            "repo",
            "success"
        ]
    }

bodhi.compose.composing
-----------------------
::

    {
        "id": "https://bodhi.fedoraproject.org/message-schemas/v1/bodhi.compose.composing#",
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Schema for message sent when composes start",
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "The name of the user who started this compose."
            },
            "repo": {
                "type": "string",
                "description": "The name of the repository being composed."
            }
        },
        "required": [
            "agent",
            "repo"
        ]
    }

bodhi.compose.start
-------------------
::

    {
        "id": "https://bodhi.fedoraproject.org/message-schemas/v1/bodhi.compose.start#",
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Schema for message sent when composes start",
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "The name of the user who started this compose."
            }
        },
        "required": [
            "agent"
        ]
    }

bodhi.compose.sync.done
-----------------------
::

    {
        "id": "https://bodhi.fedoraproject.org/message-schemas/v1/bodhi.compose.sync.done#",
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Schema for message sent when the composer is done waiting to sync to mirrors",
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "The name of the user who started this compose."
            },
            "repo": {
                "type": "string",
                "description": "The name of the repository being composed."
            }
        },
        "required": [
            "agent",
            "repo"
        ]
    }

bodhi.compose.sync.wait
-----------------------
::

    {
        "id": "https://bodhi.fedoraproject.org/message-schemas/v1/bodhi.compose.sync.wait#",
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Schema for message sent when the composer is waiting to sync to mirrors",
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "The name of the user who started this compose."
            },
            "repo": {
                "type": "string",
                "description": "The name of the repository being composed."
            }
        },
        "required": [
            "agent",
            "repo"
        ]
    }

bodhi.repo.done
---------------
::

    {
        "id": "https://bodhi.fedoraproject.org/message-schemas/v1/bodhi.repo.done#",
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Schema for message sent when a repo is created and ready to be signed",
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "The name of the user who started this compose."
            },
            "path": {
                "type": "string",
                "description": "The path of the repository that was composed."
            },
            "repo": {
                "type": "string",
                "description": "The name of the repository that was composed."
            }
        },
        "required": [
            "agent",
            "path",
            "repo"
        ]
    }

