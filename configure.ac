# Copyright (c) 2017-2021 Esrille Inc.
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

# https://www.gnu.org/software/autoconf/manual/autoconf-2.67/html_node/Initializing-configure.html
# AC_INIT (package, version, [bug-report], [tarname], [url])
AC_INIT([ibus-pskk], [0.0.1], [https://github.com/kirameister/ibus-pskk/issues])
AC_CONFIG_AUX_DIR([.])
AM_INIT_AUTOMAKE([foreign tar-ustar])

AM_GNU_GETTEXT_REQUIRE_VERSION([0.21])
AM_GNU_GETTEXT([external])

# Check IBus
#   Note pskk.xml uses icon_prop_key and
#   ibus 1.5.11 or later is required
PKG_CHECK_MODULES(IBUS, [ibus-1.0 >= 1.5.11])
AC_SUBST(IBUS_DATADIR, $($PKG_CONFIG --variable=datadir ibus-1.0) )

# Check Python
AM_PATH_PYTHON([3.7])

# define GETTEXT_* variables
GETTEXT_PACKAGE=AC_PACKAGE_NAME
AC_SUBST(GETTEXT_PACKAGE)
AC_DEFINE_UNQUOTED(
  GETTEXT_PACKAGE, "$GETTEXT_PACKAGE",
    [Define to the read-only architecture-independent data directory.]
)

# GSettings
# see https://developer.gnome.org/gio/stable/GSettings.html
GLIB_GSETTINGS

# OUTPUT files
AC_CONFIG_FILES(
dic/Makefile
dic_tools/Makefile
docs/Makefile
engine/pskk.xml.in
engine/ibus-engine-pskk
engine/Makefile
engine/util.py.in
icons/Makefile
layouts/Makefile
po/Makefile.in
setup/Makefile
setup/util.py.in
setup/ibus-setup-pskk.in
Makefile
ibus-pskk.spec
)

AC_OUTPUT
