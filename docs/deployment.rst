Deployment
----------
Deployments are performed in a generalized way with the goal of standardization
and fault resilience. The deployment process is initially customized once for
each application to fit the applications requirements. The varying needs are
abstracted in such a way that the deployment process remains constant.

Before an application can be deployed for the first time it requires an initial
setup to prepare it for SAF (see APPLICATION SETUP).

Once prepared the deployment process in a nutshell goes like this:

1. Get the artifact from some URL and store it in the repo (only done once
   for any version)
2. Verify that the mixin-repo is up to date, handle merge-requests
3. Create a deployable transaction from repo contents
4. Activate the deployable transaction
5. Test
6. Fallback if tests fail

In more detail the deployment process is performed in sequential steps as
follows. For each step you see the shell command(s) to execute ("How?")
followed by an explanation of what these commands do ("What?")

Deployment step D0 (only for new applications): Customize for SAF. This is
usually the most time consuming step.
How?    Go to APPLICATION SETUP. Come back here if completed.

Deployment step D1: (only done once for any version) Retrieve artifact from
supplier and store in artifact-repository
How?    $ saf repo push my_app 1.2.3 [url]
What?   - Downloads artifact from [url] (specified by supplier, might also be
          "file:///..." in case of network issues)
        - Unpacks artifact in temp directory.
        - Uploads unpacked artifact to repository creating version 1.2.3

Deployment step D2: Create new deployable transaction on local machine
How?    $ saf repo pull my_app 1.2.3
What?   - Copies artifact from artifact-repo to a deployable transaction in
          /app/saf/transactions/<deployable id>. Write down the id because it
          is required for deployment.
        - Overlays artifact with mixins specified in app.conf
        - Overlays artifact with application-mixin.

Deployment step D3: Stop application
How?    $ saf app stop my_app
What?   - Stops the running application. This is the latest moment that the
          downtime can start.

Deployment step D4: Activate the deployable transaction
How?    $ saf tx deploy <deployable id>
What?   - Makes sure the application is not running, otherwise aborts.
        - If the application already exists then it is moved to a new backout
          transaction in /app/saf/transactions/<backout id>. Write down this id
          because in case of a fallback this the transaction to fallback to.
        - Copies the deployable transaction (created in D2) to
          /app/saf/apps/my_app
        - Starts the application.
        - If successful, removes deployable transaction. Otherwise aborts.

Deployment step D5: Check application
How?    $ saf app check my_app
What?   - Verifies artifact self check routine by requesting the
          check.*.url URL(s) defined in /app/saf/apps/my_app.conf

Only if the new version of the application does not work:

Fallback step F1: Stop application (only in case the application started but
check failed)
How?    $ saf app stop my_app
What?   - Stops the running application

Fallback step F2: Fallback to backed out transaction (created in D4)
How?    $ saf tx deploy <backout id>
What?   - Makes sure the application is not running, otherwise aborts.
        - If /app/saf/apps/my_app exists then move it to a new
          backout transaction in /app/saf/transactions
        - Moves backout transaction from /app/saf/transactions/<backout id> to
          /app/saf/apps/my_app
        - Starts the application.

Deployment step F3: Check application
How?    $ saf app check my_app
What?   - Verifies artifact self check routine by requesting the
          check.*.url URL(s) defined in /app/saf/apps/my_app.conf
