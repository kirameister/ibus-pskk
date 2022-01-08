# Copyright (c) 2020 Esrille Inc.
# Modifications Copyright (C) 2021 Akira K.
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

setup_pskk_PYTHON = \
	main.py \
	setup.glade \
	$(NULL)
BUILT_SOURCES = util.py
nodist_setup_pskk_PYTHON = util.py
setup_pskkdir = $(pkgdatadir)/setup

libexec_SCRIPTS = ibus-setup-pskk

desktop_DATA = ibus-setup-pskk.desktop
desktopdir = $(datadir)/applications

CLEANFILES = \
	ibus-setup-pskk \
	ibus-setup-pskk.desktop \
	ibus-setup-pskk.in \
	util.py \
	util.py.in \
	$(NULL)

EXTRA_DIST = \
	ibus-setup-pskk.desktop.in \
	ibus-setup-pskk.in.in \
	util.py.in.in \
	$(NULL)

util.py: util.py.in
	$(AM_V_GEN) \
	( \
		pkgdatadir=${pkgdatadir}; \
		localedir=${localedir}; \
		s=`cat $<`; \
		eval "echo \"$${s}\""; \
	) > $@

ibus-setup-pskk: ibus-setup-pskk.in
	$(AM_V_GEN) \
	( \
		pkgdatadir=${pkgdatadir}; \
		s=`cat $<`; \
		eval "echo \"$${s}\""; \
	) > $@

ibus-setup-pskk.desktop: ibus-setup-pskk.desktop.in
	$(AM_V_GEN) \
	( \
		libexecdir=${libexecdir}; \
		pkgdatadir=${pkgdatadir}; \
		s=`cat $<`; \
		eval "echo \"$${s}\""; \
	) > $@

uninstall-hook:
	-rmdir $(setup_pskkdir)/__pycache__
	-rmdir $(setup_pskkdir)
