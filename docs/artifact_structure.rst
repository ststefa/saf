Artifact Structure
------------------
An artifact is delivered by the customer in a single archive. There are almost
no requirements about the contents of the archive. This gives the developer
freedom to create a structure which best suits his needs. There are however
certain requirements regarding behaviour and handling of the application. These
are specified in "SAF REQUIREMENTS"

Here is a simple example artifact for application "my_app" that is used
throughout this document for illustration

    (my_app.zip)
    ├── bin/
    │   └── start.sh
    ├── etc/
    │   └── runtime.conf
    └── lib/
        └── myapp_v1.jar

Different versions of an application are stored in a remote repository in
separate directories.

The delivered artifact can be modified at deployment time using MIXINS
