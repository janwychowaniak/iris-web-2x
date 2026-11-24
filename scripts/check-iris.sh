#!/usr/bin/env bash
# The image checks of CI that run IRIS, against the stock 2.4.29 database:
#   module health  a container of the image imports IRIS, whose post-init sets the database up,
#                  and scripts/iris-health.py checks the registration and both modules' health;
#   start line     the entrypoint, as iriswebapp and as iris-worker, prints the image's version line,
#                  then "Running <target> ...", before the server's first line.
#
#   check-iris.sh <image>
#
# Every secret is generated here, kept in a file only this run reads, masked in the GitHub
# Actions log, and never printed: output that may carry one is redacted first. Containers and
# the network are named iw2x-ci-<pid>-* and removed on exit.
set -euo pipefail
cd "$(dirname "$0")/.."

image=$1
db_image=ghcr.io/dfir-iris/iriswebapp_db@sha256:081ad194332887ca584a9240e8e9dea94129a235e8b38ff42c1938358be432f5
version=$(cat VERSION)
start_line="iris-web-2x ${version} (DFIR-IRIS v${version%-*})"
p=iw2x-ci-$$
work=$(mktemp -d)
failed=0

cleanup() {
    docker rm -f "$p-db" "$p-health" "$p-iriswebapp" "$p-iris-worker" > /dev/null 2>&1 || true
    docker network rm "$p-net" > /dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT

mapfile -t secrets < <(python3 -c 'import secrets; [print(secrets.token_hex(24)) for _ in range(5)]')
[ "${#secrets[@]}" -eq 5 ]
if [ -n "${GITHUB_ACTIONS:-}" ]; then
    for s in "${secrets[@]}"; do echo "::add-mask::$s"; done
fi
pg_password=${secrets[0]} pga_password=${secrets[1]} secret_key=${secrets[2]}
salt=${secrets[3]} adm_password=${secrets[4]}
redact() {
    local s args=()
    for s in "${secrets[@]}"; do args+=(-e "s/$s/***/g"); done
    sed "${args[@]}"
}

(umask 077 && cat > "$work/iris.env" <<EOF
POSTGRES_USER=postgres
POSTGRES_PASSWORD=$pg_password
POSTGRES_ADMIN_USER=raptor
POSTGRES_ADMIN_PASSWORD=$pga_password
POSTGRES_DB=iris_db
POSTGRES_SERVER=$p-db
POSTGRES_PORT=5432
DB_RETRY_COUNT=60
DB_RETRY_DELAY=2
DOCKERIZED=1
IRIS_SECRET_KEY=$secret_key
IRIS_SECURITY_PASSWORD_SALT=$salt
IRIS_ADM_PASSWORD=$adm_password
IRIS_AUTHENTICATION_TYPE=local
CELERY_BROKER=amqp://$p-rabbitmq
PYTHONDONTWRITEBYTECODE=1
EOF
)

docker network create "$p-net" > /dev/null
docker run -d --name "$p-db" --network "$p-net" --env-file "$work/iris.env" "$db_image" > /dev/null
# Ready once it takes TCP connections: the entrypoint's initialisation server never does.
for _ in $(seq 90); do
    docker exec "$p-db" pg_isready -q -h 127.0.0.1 -U postgres && break
    sleep 2
done
if ! docker exec "$p-db" pg_isready -q -h 127.0.0.1 -U postgres; then
    echo "FAIL the stock database did not start"
    docker logs "$p-db" 2>&1 | tail -20 | redact
    exit 1
fi

# Module health. The script's own lines start with "ok" or "FAIL"; IRIS's log is shown on failure.
if docker run --rm -i --name "$p-health" --network "$p-net" --env-file "$work/iris.env" \
        --entrypoint python "$image" - < scripts/iris-health.py > "$work/health.log" 2>&1; then
    grep -E '^(ok|FAIL) ' "$work/health.log"
else
    grep -E '^(ok|FAIL) ' "$work/health.log" || true
    echo "FAIL module health; the end of IRIS's output:"
    tail -40 "$work/health.log" | redact
    failed=1
fi

# The start line, for both targets, from the container's log in time order.
for target in iriswebapp iris-worker; do
    docker run -d --name "$p-$target" --network "$p-net" --env-file "$work/iris.env" \
        "$image" ./iris-entrypoint.sh "$target" > /dev/null
    for _ in $(seq 90); do
        [ "$(docker logs "$p-$target" 2>&1 | wc -l)" -ge 3 ] && break
        sleep 2
    done
    docker logs --timestamps "$p-$target" > "$work/$target.log" 2>&1
    sort -s -k1,1 "$work/$target.log" | cut -d' ' -f2- > "$work/$target.lines"
    first=$(sed -n 1p "$work/$target.lines")
    second=$(sed -n 2p "$work/$target.lines")
    third=$(sed -n 3p "$work/$target.lines")
    if [ "$first" = "$start_line" ] && [ "$second" = "Running $target ..." ] && [ -n "$third" ]; then
        echo "ok   $target prints \"$start_line\" before the server's first line"
    else
        echo "FAIL $target start line; the first lines of its log:"
        head -5 "$work/$target.lines" | redact
        failed=1
    fi
    docker rm -f "$p-$target" > /dev/null
done

exit "$failed"
