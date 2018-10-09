MIXINS
------
Usually (but not necessarily) certain files inside the artifact need to be
customized for each stage that is should be deployed to. This is done at
deployment time using an automated process which can modify or add any file in
the deployable. This process is called "overlaying" (until someone coins a
better term ;) ).

A mixin is a directory with a certain structure. The following shows a mixin
named "my_mixin"

    my_mixin/
    ├── overlay.conf
    └── overlay/
        ├── etc/
        │   └── runtime.conf
        └── lib/
            └── driver.jar

A mixin consists of a file "overlay.conf" and an "overlay" directory which
contains the files and directories which should be changed. The structure of
these files is just the same as it appears in the delivered application
artifact.

The contents of the "overlay" directory will be merged over the application
at the time that a deployable transaction is created. Any text file in the
overlay is treated as a template. It can contain tokens which will be replaced
at deployable-creation-time, usually to create a stage- or purpose-specific
version of itself. The templating uses EmPy (https://pypi.python.org/pypi/EmPy).

The file overlay.conf is optional. It uses ini-file-style syntax and contains
separate sections for any stage that it should be deployed to. Each section
contains key/value pairs which are used to render the overlay templates. Any
value may be encrypted (see ENCRYPTION).

The name of the stage (e.g. "test") is configurable and determines the section
that will be used to render the templates (e.g. [test]). The stage should
usually correspond to the OS-stage used by the CM system Puppet (which is used
to manage SAF machines).

Any application must have an application-mixin. The following shows an
application-mixin for application "my_app".

    my_app/
    ├── app.conf
    ├── overlay.conf
    └── overlay/
        └── ...

The same rules like outlined above apply. In addition the application-mixins
must contain a mandatory "app.conf". It is used to create the (optionally
stage specific) application configuration in the same way as described above.

The complete structure of the mixin-repo is shown in REPOSITORIES

The following example illustrates the overlay process of mixins

    --------- my_mixin/overlay/etc/runtime.conf
    ...
    db_tablename=APPTABLE
    db_url=@(url_to_db)
    mail_user=dilbert@@example.com
    ...
    ---------

The stage specific information is taken from the overlay configuration:

    --------- my_mixin/overlay.conf
    [test]
    url_to_db=jbdc:superdb::dbuser@dbserver.example.com:2345/APPDB

    [production]
    url_to_db=jbdc:superdb::produser@prod-dbserver.example.com:3456/APPDB
    ---------

Upon deployment on a "test" system this will result in

    --------- <deployable>/etc/runtime.conf:
    ...
    db_tablename=APPTABLE
    db_url=jbdc:superdb::dbuser@dbserver.example.com:2345/APPDB
    mail_user=dilbert@example.com
    ...
    ---------

If deployed on a "production" system it will result in

    --------- <deployable>/etc/runtime.conf:
    ...
    db_tablename=APPTABLE
    db_url=jbdc:superdb::produser@prod-dbserver.example.com:3456/APPDB
    mail_user=dilbert@example.com
    ...
    ---------

A file with the same name can potentially exist in multiple mixins. This will
cause "collisions" (i.e. overwriting of existing files) at the time a
deployable transaction is created. In this the case the existing file will be
automatically moved aside by appending a suffix to it.

The order in which files are overwritten (bigger number overwrites smaller
number) is as follows:

1. Application version
2. Configured mixin(s) in the order specified in app.conf
3. Application-mixin

The application mixin is typically used to create stage-specific configuration
files. Mixins other than the application-mixin typically contain items which
are not strictly related to an application but instead are shared by multiple
applications.

The mixin approach enables the reuse of files for multiple applications. By
making clever use of mixins the artifact-redundancy can be minimized leading to
more robust and less error-prone application deployments.
