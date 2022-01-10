# Copyright (c) 2017-2020 Esrille Inc.
#
# Using source code derived from
#   ibus-tmpl - The Input Bus template project
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

engine_pskk_PYTHON = \
	dictionary.py \
	engine.py \
	event.py \
	main.py \
	$(NULL)
BUILT_SOURCES = util.py
nodist_engine_pskk_PYTHON = util.py
engine_pskkdir = $(pkgdatadir)

libexec_SCRIPTS= ibus-engine-pskk

component_DATA = pskk.xml
componentdir = @IBUS_DATADIR@/ibus/component

gsettings_SCHEMAS = org.freedesktop.ibus.engine.pskk.gschema.xml

@GSETTINGS_RULES@

CLEANFILES = \
	ibus-engine-pskk \
	org.freedesktop.ibus.engine.pskk.gschema.xml \
	util.py \
	pskk.xml \
	$(NULL)

EXTRA_DIST = \
	ibus-engine-pskk.in \
	org.freedesktop.ibus.engine.pskk.gschema.xml.in \
	util.py.in.in \
	pskk.xml.in.in \
	$(NULL)

util.py: util.py.in
	$(AM_V_GEN) \
	( \
		libexecdir=${libexecdir}; \
		localedir=${localedir}; \
		pkgdatadir=${pkgdatadir}; \
		s=`cat $<`; \
		eval "echo \"$${s}\""; \
	) > $@

pskk.xml: pskk.xml.in
	$(AM_V_GEN) \
	( \
		libexecdir=${libexecdir}; \
		pkgdatadir=${pkgdatadir}; \
		s=`cat $<`; \
		eval "echo \"$${s}\""; \
	) > $@

org.freedesktop.ibus.engine.pskk.gschema.xml: org.freedesktop.ibus.engine.pskk.gschema.xml.in
	$(AM_V_GEN) \
	( \
		pkgdatadir=${pkgdatadir}; \
		util=${util}; \
		s=`cat $<`; \
		eval "echo \"$${s}\""; \
	) > $@

uninstall-hook:
	-rmdir $(engine_pskkdir)/__pycache__
	-rmdir $(engine_pskkdir)
