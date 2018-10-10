Application Requirements
------------------------

The application needs to comply to the following requirements to be "SAF
compatible" (some "must", others "should"). Although these requirements have
been carefully selected and reduced to a minimum there is no guarantee that
they will be completely constant over time. New requirements, new insights or
elimination of conceptual weaknesses might make it necessary to add, remove or
rephrase requirements.

Structural:

- Artifact delivery format

The artifact must be delivered as a single .zip artifact without additional
resources. There are no requirements about the internal structure of the
artifact. However the SAF-configurable application properties (like path and
name of the start script or values of environment variables) must remain as
constant as possible throughout versions. E.g. the artifact must not store
the start script in a directory whose name contains the app version because
that would require the "launcher.file" property to change for every version.
Modifications to properties are considered exceptional.

- Start routine

    The artifact must contain a start routine which is used by SAF to start
    the application. This is usually (but not necessarily) implemented using
    a simple shell script. Behavioural requirements for this start routine
    exist, see below.

- Stage neutrality

    The artifact must be applicable to all stages (e.g. test, integration,
    production) without requiring modifications which exceed the capabilities of
    SAF overlaying.

- Configurability

    Parameters which are relevant to deployment or operation teams (like DB
    URLs or other backends) must be configurable using ASCII text files which are
    located inside the artifact. The (and only the) SAF overlay mechanism is
    responsible for creating stage-specific versions of such files at deployment
    time.

- Self-containedness

    The artifact must only use files which are located under its artifact root
    (i.e. inside the .zip file). Files/directories (e.g. logfiles, config-files,
    anyfiles) must be configured relative to the artifact root.
    If access to files outside the artifact root is required then this must be
    configurable as described above. This also holds true for temporary files
    that the application might create (e.g. do not write to "/tmp/". Write to
    "tmp/" instead).

- Check-Servlet

    The application must implement a self-check routine which is accessible
    using a HTTP GET request without authentication ("anonymous Check-Servlet").
    The application should perform all checks that the developer considers
    relevant for the service that the application provides (e.g. check of backend
    systems).

    If the self-check classifies the application as operational it must output a
    distinct literal in the body of the HTTP response (e.g. "sbb access"). The
    literal must not appear in the response body otherwise.

    If the self-check classifies the application as not operational it should
    output meaningful information about the (confirmable or assumed) cause of the
    failure in the response body.

    The self-check should return an HTTP 200 response code in any case. (hint:
    if the application does not implement HTTP functionality it may be added using
    https://github.com/NanoHttpd)

Behavioural:

- Startup behaviour

    When starting the application using the configured command ('launcher.file')
    it must directly (i.e. without additional steps) boot to a fully operational
    state. The start routine may or may not daemonize (see "Process behaviour").
    The start routine must return Posix standard return values (success=0,
    failure!=0). The output of the start routine does not need to be redirected
    to a file as this is done by SAF which creates a default stdout/stderr
    logfile "log/startup.log" in the application directory.

- Process behaviour

    An application my or may not daemonize.

    If an application daemonizes then it should do so in the moment that it
    considers itself fully operational. The daemonized application must write a
    pidfile (i.e. a plain textfile containing nothing but the PID of the daemon
    process) somewhere below the artifact root. The name of the pidfile (relative
    to the artifact root) must be specified in the app config. SAF will (at most)
    wait for the configured start-timeout for the pidfile to appear. It considers
    the start attempt as failed otherwise. SAF will control (e.g. stop or
    determine status of) the app processes based on the content of the PID file.

    If the app does not daemonize then SAF will automatically background the
    process after a configured start-timeout. This timeout should be set to a
    value after which the application is typically fully initialized and
    operational. A regular expression matching the (and only the!) processes
    belonging to the app must be specified in the app config. SAF will control
    (e.g. stop or determine status of) the app processes based on the processes
    matching that regular expression.

- Immediate config activation

    Changes to the configuration must directly become active by simply restarting
    the application (i.e. without performing additional steps).

- Runtime Dependencies

    The application should intelligently handle its runtime dependencies. If a
    required resource (database, LDAP Server, ...) is unavailable then the
    application should probe their availability or otherwise fail. This
    requirement is valid for any dependency including dependencies to other
    applications.

- Logfile handling

    The application must manage its logfiles. It must ensure that application
    logfiles do not grow indefinitely. Logfile rotation should primarily
    consider file size and optionally also time range. I.e. logfiles should be
    rotated if exceeding a certain size and optionally also once a
    day | week | month (whatever comes first).

    Logfiles must be written to an application internal directory named "log"
    or subdirectories thereof.

    SAF will automatically capture stdout and stderr of the (non-daemonizing)
    process and write it to the file "log/startup.log" in the application
    directory. This file is rotated once a day using OS mechanisms. The
    startup.log is meant as a general "catch-all" mechanism. After startup the
    application must not write excessively to stdout/stderr as this might lead to
    storage exhaustion (due to the daily rotation cycle).

- Non-privileged execution

  The application is running in a process of a non-privileged user. As such
  the application must not require or depend on services or mechanisms that
  need privileged access (e.g. opening listening network ports < 1024).
