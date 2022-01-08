# vim:set et ts=4:
#
# ibus-pskk
#
# Copyright (c) Copyright (C) 2021 Akira K.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# if not 1, append datestamp to the version number.
m4_define([package_name], [ibus-pskk])
m4_define([ibus_released], [0])
m4_define([ibus_major_version], [0])
m4_define([ibus_minor_version], [1])

m4_define([ibus_version],
    ibus_major_version.ibus_minor_version)

AC_INIT([package_name], [ibus_version], [http://github.com/kirameister/ibus-pskk/issues], [package_name])
#AM_INIT_AUTOMAKE([package_name],[ibus_version])
AM_INIT_AUTOMAKE([foreign])


# check ibus
PKG_CHECK_MODULES(IBUS, [ibus-1.0 >= 1.5.11])
AC_SUBST(IBUS_DATADIR, $($PKG_CONFIG --variable=datadir ibus-1.0) )

# Define python version
AC_ARG_WITH(python,
    AS_HELP_STRING([--with-python[=PATH]],
        [Select python2 or python3]),
    [PYTHON=$with_python], []
)

#check python
AM_PATH_PYTHON([3.5])

# GSettings
# see https://developer.gnome.org/gio/stable/GSettings.html
GLIB_GSETTINGS



# OUTPUT files
AC_CONFIG_FILES(
Makefile
ibus-pskk.spec
engine/pskk.xml.in
engine/ibus-engine-pskk
engine/Makefile
engine/util.py.in
layouts/Makefile
setup/Makefile
setup/util.py.in
setup/ibus-setup-pskk.in
)

AC_OUTPUT
