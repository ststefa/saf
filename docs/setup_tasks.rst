SAF REPO SETUP
--------------
SAF uses two kinds of repositories to build transactions. Both are configured
in /apps/saf/conf/saf.conf.

To setup the artifact-repo the configured directory has to be created. E.g.
if repo.hostname=server.example.com, repo.path=/my/repo/path and
repo.user=johndoe then login to server.example.com, create a directory
/my/repo/path and make sure it's writeable for user johndoe.

To setup the mixin-repo the configured project has to be created there and
permissions have to be granted for ssh pulls and (optionally) API access.


MACHINE SETUP
-------------
A machine needs some one-time preparation steps to enable it for SAF. This is
mainly about access from the machine to the SAF repositories.

1. Establish an ssh trust for the asrun user from the machine to the artifact
   repo. This is done by copying the users public ssh key (~asrun/.ssh/id_rsa.pub)
   to the artifact-repo machine ~software/.ssh/authorized_keys, prefixing
   it with the sshselector method
2. Authorize the machine for sshselector. This is done by adding the required
   commands in the artifact-repo (~software/bin/sshselector.conf, examples
   given there)
3. Add the asrun users public key (see 1.) to the saf_reader user in the
   mixin-repo by logging into the mixin-repo as user saf_reader and adding
   the ssh key
4. If the machine has other 'partner' machines in the same stage: Copy the
   machine secret (/app/saf/conf/secret) from one of the other machines to the
   new machine (see also ENCRYPTION)


APPLICATION SETUP
-----------------
Before an application can be deployed for the first time the deployer has to
prepare it for SAF. The first version that is delivered by the supplier is
usually used to do this.

First the deployer needs to analyze and understand the structure of the
artifact. Things to figure out or to ask the supplier (not exhaustive):

- What should the unique name of the application be?
- Does the artifact comply to basic SAF requirements (e.g. path
  specifications, start script, logfile rotation, ...)? See also
  SAF REQUIREMENTS
- What is the name of the start script inside the artifact?
- Which environment variables must/could be set?
- Are basic parameters configurable which should be modifiable as part of
  regular operating issues (e.g. java Xmx, paths to non-artifact
  resources, connections to databases, ...)?
- What is the regular expression that uniquely identifies to processes that
  belong to the application? Alternatively, what's the name of the pidfile in
  case of a daemonizing application?

Next the SAF repositories need preparation:

- In the artifact-repo on $repo.hostname create a new directory named
  $repo.path/<appname>. E.g. for repo.hostname=localhost,
  repo.path=/my/repo/path and an application named 'my_app' create a directory
  '/my/repo/path/my_app' on your local machine.
- In the GUI of the mixin-repo go to the configured project
  ("mixinrepo.origin.url" in saf.conf). Select the branch of your machine
  ("stage" in saf.conf). Create the application-mixin by creating a directory
  apps/<appname> with an initial application configuration
  (apps/<appname>/app.conf). The local file /app/saf/doc/sample_app.conf may be
  used as a starting point.

Files which require stage-specific modification must be rewritten to EmPy
templates and added to a mixin (either the application-mixin or a mixin
configured in app.conf).

If there are multiple related applications which share the same modification
they should be moved to separate mixins which are then shared between these
applications by including them in app.conf (mixins=...).
