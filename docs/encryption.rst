Encryption
----------
SAF encourages collaboration between different teams. It does so by using git
branches and assigning distinct branches to distinct stages (stage == branch).

Storing files on GIT also means they are visible by a broad audience. It is
therefore a security risk if sensitive information is specified as plain text.

To address this SAF offers a "shared secret" encryption mechanism which
combines a given string with a machine-specific secret. This secret is stored
in /app/saf/conf/secret and consists of an arbitrary literal. This literal is
combined with the sensitive information resulting in an encrypted literal which
can be safely stored in an overlay configuration on GIT (see MIXINS for details
on overlaying). At deployment-time the encrypted string will be  automatically
decrypted and the resulting file will again contain the sensitive information.

The following example illustrates the encryption/decryption process. Say our
application my_app wants to safely specify the password for its database
backend. my_app wants to see this information in its etc/db.conf file. The
application-mixin contains ...

    --------- apps/my_app/overlay/etc/db.conf
    ...
    db_url=@(url_to_db)
    db_password=@(db_pass)
    ...
    ---------

Now an encrypted version of the password needs to be created. This is done by
using "saf encrypt" on the machine where the deployment should be done (i.e.
the machine with the proper secret).

    testsys $ saf encrypt mySuperSecretPass
    {ENC}PAADTY/ODQVLUM0AyksGR8=
    testsys $

    productionsys $ saf encrypt alsoVerySecret
    {ENC}MBUjVxA/OB4jK1IjEg0=
    productionsys $


The encrypted passwords are then specified in the overlay configuration of the
application-mixin:

    --------- apps/my_app/overlay.conf
    [test]
    url_to_db=jbdc:superdb::dbuser@dbserver.example.com:2345/APPDB
    db_pass={ENC}PAADTY/ODQVLUM0AyksGR8=

    [production]
    url_to_db=jbdc:superdb::produser@prod-dbserver.example.com:3456/APPDB
    db_pass={ENC}MBUjVxA/OB4jK1IjEg0=
    ---------

Upon deployment on e.g. a "test" system this will result in

    --------- <deployable>/etc/db.conf:
    ...
    db_url=jbdc:superdb::dbuser@dbserver.example.com:2345/APPDB
    db_pass=mySuperSecretPass
    ...
    ---------

The deployment process will recognize if an overlay file contains an encrypted
value and remove world-readability from it in the deployable transaction.

Because the overlay configuration is related to a specific branch all machines
of that branch need to use the same shared secret.
