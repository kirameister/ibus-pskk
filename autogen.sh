#!/bin/sh -xe

export ACLOCAL_PATH=$PWD/m4

aclocal --force
autopoint --force
automake --add-missing --force-missing --copy
autoconf -f
./configure "$@"
