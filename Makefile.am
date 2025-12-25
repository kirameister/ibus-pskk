# Copyright (c) 2017-2020 Esrille Inc.
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

SUBDIRS = \
	dic \
	dic_tools \
	docs \
	engine \
	icons \
	layouts \
	setup \
	$(NULL)


EXTRA_DIST = \
	debian/changelog \
	debian/compat \
	debian/control \
	debian/copyright \
	debian/rules \
	debian/source/format \
	autogen.sh \
	@PACKAGE_NAME@.spec \
	@PACKAGE_NAME@.spec.in \
	CONTRIBUTING.md \
	LICENSE \
	NOTICE \
	README.md \
	README.txt \
	$(NULL)

noinst_DIST = \
	$(NULL)

DISTCLEANFILES = \
	ABOUT-NLS \
	$(NULL)

uninstall-hook:
	-rmdir $(pkgdatadir)

# make l to clean all the auto-generated files
l:
	rm -rf m4
	rm -rf autom4te.cache
	rm -f ABOUT-NLS
	rm -f Makefile
	rm -f Makefile.in
	rm -f aclocal.m4
	rm -f compile
	rm -f config.guess
	rm -f config.log
	rm -f config.rpath
	rm -f config.status
	rm -f config.sub
	rm -f configure
	rm -f configure~
	rm -f dic/Makefile
	rm -f dic/Makefile.in
	rm -f dic_tools/Makefile
	rm -f dic_tools/Makefile.in
	rm -f docs/Makefile
	rm -f docs/Makefile.in
	rm -f engine/Makefile
	rm -f engine/Makefile.in
	rm -f engine/ibus-engine-pskk
	rm -f engine/pskk.xml.in
	rm -f engine/util.py.in
	rm -f ibus-pskk.spec
	rm -f icons/Makefile
	rm -f icons/Makefile.in
	rm -f install-sh
	rm -f layouts/Makefile
	rm -f layouts/Makefile.in
	rm -f missing
	rm -f py-compile
	rm -f setup/Makefile
	rm -f setup/Makefile.in
	rm -f setup/ibus-setup-pskk.in
	rm -f setup/util.py.in
	rm -rf engine/__pycache__
	rm -f engine/org.freedesktop.ibus.engine.pskk.gschema.valid
	rm -f engine/org.freedesktop.ibus.engine.pskk.gschema.xml
	rm -f engine/pskk.xml
	rm -f engine/util.py
	rm -f setup/ibus-setup-pskk
	rm -f setup/ibus-setup-pskk.desktop
	rm -f setup/util.py

