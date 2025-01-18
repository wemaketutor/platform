#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

readonly cmd="$*"

backend () {
  dockerize -wait 'tcp://backend:8081' -timeout 5s
}

until backend; do
  >&2 echo 'backend service is unavailable - sleeping'
done

>&2 echo 'backend service is up - continuing...'

exec $cmd
