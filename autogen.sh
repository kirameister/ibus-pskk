#!/bin/sh -xe

aclocal --force
automake --add-missing --force-missing --copy
autoconf -f
./configure "$@"
