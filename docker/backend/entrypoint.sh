#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

readonly cmd="$*"

db_service () {
  dockerize -wait 'tcp://db:5432' -timeout 5s
}

until db_service; do
  >&2 echo 'db service is unavailable - sleeping'
done

>&2 echo 'db service is up - continuing...'

exec $cmd
