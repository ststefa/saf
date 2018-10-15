Operating
=========

SAF uses a single command called `(/app/saf/bin/)saf`. The functionality is
clustered into command groups like e.g. `app` for application commands or `repo`
for repository commands.

Online help is available on all levels. I.e. `saf -h` will show general help
about using saf. "saf app -h" will explain the commands in the app group and
"saf app start -h" will show detailed help for starting applications.

The scripts are meant to cover all usecases that occur in daily operating. If
you feel something is missing please report to stefan.steinert@t-systems.ch.

Example usages
--------------

List applications on the system
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


```
$ saf app ls
NAME               VERSION    SIZE       DEPLOY_TIME
cisi-mancenter     1605.0.11  121226920  Wed Oct 19 08:42:07 CEST 2016
cisi-storage-1     1605.1.11  121226920  Wed Oct 19 08:45:32 CEST 2016
cisi-storage-2     1705.1.10  126276991  Wed Nov 19 08:48:00 CEST 2016
```

List applications matching regex ".*mancenter.*" with details (JSON formatted
output):

    $ saf app ls .*mancenter.* -dj
    {'cisi-mancenter': {'deploy_user': 'u202279', 'deploy_time': 'Wed Oct 19 08:42:07 CEST 2016',
    'create_user': 'u202279', 'create_time': 'Wed Oct 19 08:41:23 CEST 2016', 'app_version': '1605.0.11',
    'app_size': 70591162}}

Show the runtime status of all applications (POSIX style):

    $ saf app status
    cisi-hazelcast-mancenter is running (PID 22918)
    cisi-storage-1 is running (PID 25195)
    cisi-storage-2 is stopped

Show details about using the app status command:

    $ saf app status -h
    usage: saf app status [-h] [-b] [-a] [-j] [app_regex]

    positional arguments:
      app_regex        A python regular expression specifying the app name(s)

    optional arguments:
      -h, --help       show this help message and exit
      -b, --bootstart  Consider only apps which are enabled for automatic start
                       upon OS boot (i.e. bootstart=true in
                       /app/saf/apps/<app>.conf)
      -a, --all        All apps. Default for the commands ls, ps, status
      -j, --asjson     Produce json formatted output

Start an application:

    $ saf app start cisi-storage-1
    Starting cisi-storage-1 ...
    OK
    # The start sequence consists of:
    #    - Export env.* variables defined in /app/saf/apps/<app_name>.conf
    #    - Set ulimit to process.maxfiles
    #    - Change directory to /app/saf/apps/<app_name>
    #    - Call launcher.file with launcher.args
    #    - Wait timeout.start seconds or until launcher.file terminates
    #      (whatever comes first)

Stop an application:

    $ saf app stop cisi-storage-1
    Stopping cisi-storage-1 ...
    OK
    # The stop sequence consists of:
    #     - (WIP: Call the optional stop script of the application)
    #     - Send a TERM signal to all processes of the application
    #     - Wait (at most) timeout.stop seconds for termination
    #     - If the processes do not disappear then send them a KILL signal

Show running app processes:

    $ saf app ps
    PID    APP             START                %CPU  RSS      #FD  #THR
    11383  cisi-storage-1  2017-03-28 11:42:26  0.0   9564160  7    1

Tail logfiles of all applications to stdout ("tail -f"):

    $ saf app tail cisi-storage-1
    ...
    ^C
    $

List artifact repository content:

    $ saf repo ls
    cisi-hazelcast-mancenter
    cisi-jms-spy
    cisi-loppis-activemq
    cisi-loppis-gateway
    cisi-loppis-launcher
    cisi-loppis-monitor
    cisi-monithor
    cisi-storage-1
    cisi-storage-2

List local transaction:

    $ saf tx ls
    ID        APP             VERSION    TYPE     TIME                 SIZE
    xy5r0bpu  cisi-storage-1  1605.1.10  backout  2017-02-14 14:31:22  62889444
    yym8bzk0  cisi-storage-1  1805.1.11  new      2017-04-24 12:44:10  832718
