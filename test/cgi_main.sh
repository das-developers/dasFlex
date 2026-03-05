#!/usr/bin/env bash

# A small wrapper around CGI commands providing the environment
# variables needed for testing services from the build directory
# 
# Run this from the project root, not here!
#
# Variables in here must be consistent with the small server config
# file generated in the test area

SRV_ROOT=${PWD}/test_srv


if [ "$1" = "-h" ] || [ "$1" = "--help" ] ; then
	echo "Usage: cgi_main.sh [ PATH ] [key=val key=val .. ]"
	echo "Examples:"
	echo ""
	echo "  Form Request"
	echo "  ./cgi_main.sh source/example/random.html"
	echo ""
	echo "  Data Return"
	echo "  ./cgi_vars.sh source/example/random/flex \\"
	echo "      read.time.min=2025-01-01  read.time.max=2025-02-01 "
	echo ""
	exit 0
fi

export HTTP_USER_AGENT=bash
export DASFLEX_CONFIG=${SRV_ROOT}/etc/dasflex.conf
export SCRIPT_FILENAME=${SRV_ROOT}/bin/dasflex_cgimain
export SERVER_NAME=localhost
export SCRIPT_NAME=/das/server
export PATH_INFO="$1"


shift 
IFS="&"
export QUERY_STRING="$*"

echo "HTTP_USER_AGENT=${HTTP_USER_AGENT}" 1>&2
echo "SCRIPT_FILENAME=${SCRIPT_FILENAME}" 1>&2
echo "DASFLEX_CONFIG=${DASFLEX_CONFIG}" 1>&2
echo "SERVER_NAME=${SERVER_NAME}" 1>&2
echo "SCRIPT_NAME=${SCRIPT_NAME}" 1>&2
echo "PATH_INFO=${PATH_INFO}" 1>&2
echo "QUERY_STRING=${QUERY_STRING}" 1>&2

$SCRIPT_FILENAME

exit $?
