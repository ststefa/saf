#!/bin/sh
# used by git due to exported GIT_SSH
exec ssh -o StrictHostKeyChecking=no -o BatchMode=yes "$@"