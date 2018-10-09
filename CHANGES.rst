
.. _important_notes:

Important notes
===============

This section provides information about security and corruption issues.

.. _tam_vuln:

Pre-1.0.9 manifest spoofing vulnerability (CVE-2016-10099)
----------------------------------------------------------

A flaw in the cryptographic authentication scheme in Borg allowed an attacker
to spoof the manifest. The attack requires an attacker to be able to

1. insert files (with no additional headers) into backups
2. gain write access to the repository

This vulnerability does not disclose plaintext to the attacker, nor does it
affect the authenticity of existing archives.

The vulnerability allows an attacker to create a spoofed manifest (the list of archives).
Creating plausible fake archives may be feasible for small archives, but is unlikely
for large archives.

The fix adds a separate authentication tag to the manifest. For compatibility
with prior versions this authentication tag is *not* required by default
for existing repositories. Repositories created with 1.0.9 and later require it.

Steps you should take:

1. Upgrade all clients to 1.0.9 or later.
2. Run ``borg upgrade --tam <repository>`` *on every client* for *each* repository.
3. This will list all archives, including archive IDs, for easy comparison with your logs.
4. Done.


.. _changelog:

Changelog
=========

2.2.2 (not released yet)
------------------------


2.2.1 (Bugfix Release) 2018-06-11
---------------------------------

- fix: saf logfile rotation did not work
- fix: saf produced useless https warnings
- fix: OS boot autostart did not bypass configured asserts

2.2.0 (Feature Release) 2018-04-10
----------------------------------

- add: Any overlay git branch can now be specified on "repo pull" using a new
  "--branch" parameter. This enables the use of feature branches (gitlab
  issue #5)
- add: New configurable and interactive "KnowHow asserts" in case of nonstandard
  operating and deployment instructions. Can be defined in app.conf and
  overriden with the "--iknow" parameter  (gitlab issue #31)
- change: Report chmod actions when pushing new version with "repo push"
- change: Removed ambiguous -i parameter in "repo pull". Longname --ignore_mr
  still there, valid and working
- fix: Now deleting temp dir after push
- fix: Proper CPU usage display in "saf app ps" (gitlab issue #12)
- minor: Remove legacy SAF shell artifacts
- minor: Reorganize packages and imports
- minor: Update psutil to 5.4.3

2.1.8 (Bugfix Release) 2018-03-21
---------------------------------

- fix: Automatically remove stale pidfile (gitlab issue #27)

2.1.7 (Bugfix Release) 2018-01-21
---------------------------------
- change: Removed ambiguous params -d/-v in favour of --debug/--verbose
- fix: Fixed error in edge case when stopping app (gitlab issue #26)

2.1.6 (Feature Release) 2017-11-21
---------------------------------
- add: New "repo ll" command
- minor: Changed they way that shell commands are called (gitlab issue #24)

2.1.5 (Bugfix Release) 2017-06-13
---------------------------------
- fix: Specifying an non-existing appname will cause an error now (gitlab
  issue #4)

2.1.4 (Bugfix Release)
---------------------------------
- fix: Overlaying will no longer be attempted on binary files (gitlab issue #21)

