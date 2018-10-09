REPOSITORIES
------------
SAF uses two different repositories for different purpose.

- An artifact-repo to store the delivered artifacts in different versions. The
  contents of this repo are considered immutable. Artifacts/versions can only
  be added or removed but not modified. The repo can hold large amounts of
  data. Versions can be purged, freeing up filesystem space. This repo is
  implemented using plain ssh/scp features.
- A mixin-repo to store mixin information like templates and stage-specific
  artifacts. The repo is meant for small artifacts. The contents of this repo
  are fluid (i.e. there are no fixed versions). The mixins are maintained
  collaboratively by suppliers and deployers each working on his/her
  branch(es). Changes are copied between stages using branch merging. The
  history is maintained throughout the entire lifetime of the application.
  This repo is implemented using a Git server software like GitLab.

Different versions of an application are stored in the artifact-repo with
same name. Naming and handling of versions should conform to the semantic
versioning concept (see http://semver.org/).

Example artifact-repo:

    (artifact-repo-root)
    ├── my_app/
    │   ├── 0.0.1/
    │   │   ├── bin/
    │   │   │   └── start.sh
    │   │   ├── etc/
    │   │   │   └── runtime.conf
    │   │   └── lib/
    │   │       └── myapp_v1.jar
    │   ├── 1.0.0/
    │   │   ├── bin/
    │   │   │   └── start.sh
    │   │   ├── etc/
    │   │   │   ├── db.conf
    │   │   │   └── runtime.conf
    │   │   └── lib/
    │   │       ├── myapp_v2.jar
    │   │       └── app_extension.jar
    │   └── ...
    ├── otherApp/
    │   └── ...
    └── ...


Mixins contain the files and directories which will be added on top of an
application version. Mixins split up into application-mixins and general
mixins. They are further described in the MIXINS paragraph.

Example mixin-repo:

    (mixin-repo-root)
    ├── apps
    │   ├── my_app/
    │   │   ├── app.conf
    │   │   ├── overlay.conf
    │   │   └── overlay/
    │   │       └── ...
    │   ├── other_app/
    │   │   └── ...
    │   └── ...
    └── mixins
        ├── my_mixin/
        │   ├── overlay.conf
        │   └── overlay/
        │       └── ...
        ├── other_mixin/
        │   └── ...
        └── ...

