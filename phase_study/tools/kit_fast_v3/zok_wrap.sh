#!/bin/bash
# Calls the instrumented ZoKrates binary and adds "--backend $ZBACKEND" to the three commands that take a back end.
B=${ZTIMERS:-$(dirname "$0")/zokrates_timers}
[ -n "$ZFAST" ] && export ZOK_MATRIX_CACHE="$PWD/matrices.bin"
case "$1" in setup|generate-proof|verify) [ -n "$ZBACKEND" ] && exec "$B" "$@" --backend "$ZBACKEND" ;; esac
exec "$B" "$@"
