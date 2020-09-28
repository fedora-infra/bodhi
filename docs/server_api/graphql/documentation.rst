=====================
Using the GraphQL API
=====================

This provides the documentation on how to use the GraphiQL client to query Bodhi's resources.

The Basics
==========

The GraphQL API assists in getting data in and out of* Bodhi. It's an HTTP-based API that can be 
used to query & post data. It's composed of:

- **Node**  : An individual object. (Eg: Release, Update, etc.)
- **Edge**  : A connection between a collection of objects and a single object. (Eg: Releases in an Update)
- **Field** : Data/attributes of an object. (Eg: id_prefix of a Release)

You can implement GraphQL queries by either sending POST requests using CURL to the /graphql 
endpoint, or using the GraphiQL client.


Using the GraphiQL Client
-------------------------

GraphiQL is a GUI for editing and testing GraphQL queries and mutations cleanly.

On the left side of the interface, you can enter traditional GraphQL queries. On the right 
tab, you will see the consequent data rendered.


GraphQL Query/Response Structure
--------------------------------

A typical GraphQL query looks like this

::

    { nameOfQuery(optionalArgument: argumentValue){
        fieldDesired
      }
    }


A typical GraphQL data response looks like this

::

    { "data":{
        "nameOfQuery": [
          {
            "fieldDesired": value
          }
        ] 
      }
    }


Available Queries
=================

``nameOfQuery`` can be replaced with ``allReleases``, ``getRelease``, and ``getUpdate``.

allReleases
-----------
.. list-table::
   :widths: 28 72
   :header-rows: 0

   * - **Description**
     - Query all releases in Bodhi.
   * - **Object**
     - bodhi.server.models.release
   * - **Fields Available**
     - name, longName, version, id_prefix, branch, distTag, stableTag, testingTag, candidateTag, 
       pendingSigningTag, pendingTestingTag, PendingStableTag, OverrideTag, mailTemplate, state, id, 
       composedByBodhi, createAutomaticUpdates, packageManager, testingRepository
   * - **Curl Request**
     - ``curl -H 'Content-Type: application/json' -X POST -d '{"query": "query {allReleases {name state}}"}' https://bodhi.fedoraproject.org/graphql``
   * - **GraphiQL Client Query**
     - ::

         { allReleases {
              name
              state
            }
         }
   * - **Output**
     - ::

         {
            "data": {
                "allReleases": [
                  {
                    "name": "F32C",
                    "state": "current"
                  },
                  {
                  "name": "F33",
                  "state": "pending"
                  },
                ..
                ..
            }
         }


getRelease
----------
.. list-table::
   :widths: 28 72
   :header-rows: 0

   * - **Description**
     - Query specific releases in Bodhi using arguments as a filter.
   * - **Object**
     - bodhi.server.models.release
   * - **Valid Arguments**
     - idPrefix, name, composedByBodhi, state
   * - **Fields Available**
     - name, longName, version, id_prefix, branch, distTag, stableTag, testingTag, candidateTag, 
       pendingSigningTag, pendingTestingTag, PendingStableTag, OverrideTag, mailTemplate, state, id, 
       composedByBodhi, createAutomaticUpdates, packageManager, testingRepository
   * - **Curl Request**
     - ``curl -H 'Content-Type: application/json' -X POST -d '{"query": "query{getRelease(composedByBodhi: true, name: "F22"){name state}}"}' https://bodhi.fedoraproject.org/graphql``
   * - **GraphiQL Client Query**
     - ::

         { getReleases(composedByBodhi: true, name: "F22"){
              name
              state
            }
         }
   * - **Output**
     - ::

         {
          "data": {
              "getReleases": [
                {
                  "name": "F22",
                  "state": "archived"
                }
              ]
           }
         }


getUpdate
---------
.. list-table::
   :widths: 28 72
   :header-rows: 0

   * - **Description**
     - Query specific updates in Bodhi using arguments as a filter.
   * - **Object**
     - bodhi.server.models.update
   * - **Valid Arguments**
     - stableKarma, unstableKarma, stableDays, updateType, status, request, severity, pushed, 
       critpath, dateApproved, alias, releaseId, userId, testGatingStatus, FromTag
   * - **Fields Available**
     - autoKarma, autotime, stableKarma, unstableKarma, stableDays, requirements, requireBugs, 
       requireTestCases, displayName, notes, updateType, status, request, severity, locked, pushed, 
       critpath, closeBugs, dateSubmitted, dateModified, dateApproved, datePushed, dateTesting, 
       dateStable, alias, releaseId, userId, testGatingStatus, FromTag
   * - **Curl Request**
     - ``curl -H 'Content-Type: application/json' -X POST -d '{"query": "query{getUpdate(userId: 5136){critpath}}"}' https://bodhi.fedoraproject.org/graphql``
   * - **GraphiQL Client Query**
     - ::

         { getUpdate(userId: 5136){
              critpath
            }
         }
   * - **Output**
     - ::

         {
            "data": {
               "getUpdates": [
              {
               "critpath": false
              }
            ]
           }
         }
