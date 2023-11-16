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
