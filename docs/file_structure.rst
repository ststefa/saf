FILE STRUCTURE
--------------
Each application is located in a directory in /app/saf/apps/<appname>.
Applications do not have any conceptual relation. Even multiple streams of the
same application (e.g. different versions) that need to run in parallel are
considered unrelated applications.

This is an overview of how files are structured. "app1" and "app2" are used as
examples for two applications on the machine. The most important locations are:

- apps:         The applications (one sub directory per application) along
                with their configuration and metadata
- transactions: Transactions, i.e. instances of applications which are not
                currently deployed. Multiple transaction types exist, e.g.
                "new" transactions which have been prepared for deployment or
                "backout" transactions which have been undeployed due to some
                reason (like deploying a new version)

The following illustrates the structure

    /app/saf
    ├──apps (applications which can be started or stopped)
    │  ├──app1
    │  │  ├──<unpacked app1 artifact>
    │  │  ├──log (logs of app1)
    │  │  └──...
    │  ├──app1.conf (config for app1)
    │  ├──app1.meta (metadata for app1)
    │  ├──app2
    │  │  └──...
    │  ├──app2.conf (config for app2)
    │  ├──app2.meta (metadata for app2)
    │  └──...
    ├──bin (frequently used operating and deployment scripts)
    ├──conf (SAF configuration)
    ├──doc (SAF documentation)
    ├──log (SAF meta logs)
    ├──lib (SAF internal resources and code)
    └──transactions (deplyoable transactions)
       ├──Iods0C (deployable transaction of app1 with id Iods0C)
       │  ├──conf (app config)
       │  ├──meta (app metadata)
       │  └──instance (actual deployable data of app1)
       │     ├──<unpacked app1 artifact>
       │     ├──log
       │     └──...
       ├──qhV22v
       │  └──...
       └──...
