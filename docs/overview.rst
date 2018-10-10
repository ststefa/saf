Overview
--------
The `/app/saf` directory on this machine complies to a standardized concept to
manage standalone applications. This concept is called "Standalone Application
Framework" (SAF).

The purpose of SAF is to close a gap between the requirements of development
and operation teams.

It is crucial to the efficiency of operation teams to have a rough, standardised
overview of an application. It enables them to perform standard tasks (starting,
stopping, deploying) without being required to dive into application-internal
details. This idea was implemented with the concept of application servers.

Likewise it is crucial to the efficiency of development teams to have short
development cycles and to be able to choose the most appropriate technology to
implement their solution. This requirement can easily get in conflict with the
concept of application servers.

SAF tries to combine these requirements by enforcing standard procedures on
developer-defined standalone applications. It does so by adding a generic and
customizable indirection layer (called an "overlay") between application and
procedure.

The term "standalone application" in this context means "a self-contained
application with no dependencies to other local to-be-maintained runtime-
services" like e.g. a local web server. The application has to contain
everything required to provide its service. Of course this does not apply
for required remote backend services like databases.