INSTRUCTION ASSERTION
---------------------
Handling of SAF application is rather simple. Unfortunately this does not hold
true for the overall application construct which might consist of several
other (SAF and/or non-SAF) components. The runtime dependencies between all
these components get complex quickly so that it becomes hard (if at all
possible) to automate. SAF uses written operational instructions
("Handlungs-Anweisungen") to document these procedures. As with all written
instructions these have a certain risk of not being recognized.
  To increase the chances SAF uses configurable assertions which can be added
to the application config file (app.conf) like so:

    <assert> = <url>

If set, the assertion will cause the respective SAF action(s) to interactively
prompt the user to remind him of the existence of such instructions.
  The prompt can be bypassed using the --iknow parameter. This is required in
cases of non-interactive use (e.g. system startup or automated builds).

Supported asserts are:

- knowhow.app.start
  Asks for confirmation just before starting an app. This affects the SAF "app
  start" and "app restart" commands. However it does not affect the "tx deploy"
  and "repo pull --deploy" commands which also cause an app to be started.

- knowhow.app.stop
  Asks for confirmation just before stopping an app. This affects the SAF "app
  stop" and "app restart" commands

- knowhow.tx.deploy
  Asks for confirmation after creating the deployment transaction and just
  before deploying it. This affects the SAF "tx deploy" and "repo pull --deploy"
  commands

An arbitrary URL is used as the value for the assert. The instructions which
reside on that URL should describe the required actions. To reduce the risk of
misunderstanding the instructions and conditions should be written as crisp
and concise as possible. When you phrase the instructions, have a sleepy
operator in mind who just got up at night to handle the situation. Write the
instructions for him. The more precise the instructions, the lower the chance
for misinterpretation.
