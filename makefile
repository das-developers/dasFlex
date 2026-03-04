# Just pushes commands down to setupuptools

# The python wrecking ball swings again, "setup.py install" is no longer
# supported.  This is a major adjustment.
#
# Going forward we assume that the end user has setup thier path so that
# the command "python" is the version of python desired, most likely from
# a python virtual environment.  Thus the following environment variables
# are no longer used for python3.12:
#
#   N_ARCH
#   PY_VER
#
# though N_ARCH is still set for older install methods.

# Make sure this matches with pyproject.toml
VERSION:=0.6rc1

ifeq ($(PY_BIN),)
PY_BIN=$(shell which python)

ifeq ($(PY_BIN),)
PY_BIN=$(shell which python3)
endif

ifeq ($(PY_BIN),)
$(error Neither python nor python3 were found, set PY_BIN to the path to your python interpreter)
endif
endif

# ########################################################################### #
# Try to predict the wheel name and our das2py depenency name. This is a fool's
# game but most standard tools will skip this makefile anyway and jump straight
# to a python -m build style command. I'd prefer not to do that so than I can 
# run unittests without consulting pypi.

PY_VER_TOK:=$(shell $(PY_BIN) -c "import sys; print('%d%d'%sys.version_info[0:2])")
PY_MAJ_VER_TOK:=$(shell $(PY_BIN) -c "import sys; print(sys.version_info[0])")

WHEEL_FILE:=dasflex-$(VERSION)-py$(PY_MAJ_VER_TOK)-none-any.whl
VENV_MOD:=venv

DAS_MOD:=das2py
DAS_VER:=3.0rc5

DAS_WHEEL_FILE:=$(DAS_MOD)-$(DAS_VER)-cp$(PY_VER_TOK)-cp$(PY_VER_TOK)-linux_x86_64.whl
DAS_WHEEL_PATH=$(abspath ../das2py/dist/$(DAS_WHEEL_FILE))

PIP_ARGS=--isolated --no-python-version-warning

# ########################################################################### #

SRC:= \
__init__.py \
\
handlers/__init__.py handlers/catalog.py handlers/coverage.py \
handlers/d3data.py handlers/d3data_save.py handlers/d3form.py \
handlers/debug.py handlers/directory.py handlers/id.py handlers/image.py \
handlers/info.py handlers/intro.py handlers/logo.py handlers/peers.py \
handlers/resource.py handlers/timedata.py handlers/verify.py \
\
scripts/cgimain.py scripts/cgilog.py scripts/websocd.py scripts/cupdate.py \
scripts/das2test.py scripts/mkroot.py scripts/todo.py scripts/add.py\
\
tasks/__init__.py tasks/cachetask.py tasks/covertask.py tasks/listtask.py \
tasks/usagetask.py \
\
util/__init__.py util/catalog.py util/convdsdf.py util/convjson.py util/formats.py \
\
webutil/__init__.py webutil/auth.py webutil/cache.py webutil/command.py \
webutil/dsdf.py webutil/errors.py webutil/mime.py webutil/misc.py webutil/page.py \
webutil/task.py webutil/webio.py \
\
root/etc/dasflex.conf.example.in \
root/etc/mime.json.example \
root/etc/das2peers.ini.example.in \
root/Examples/_dirinfo_.dsdf \
root/Examples/UNLICENSE \
root/Examples/Auth/sine.py \
root/Examples/Auth.dsdf.in \
root/Examples/Params/reader.py \
root/Examples/Params.dsdf.in \
root/Examples/Params/themis_data/CAA_EST_UG_STA_v36.pdf \
root/Examples/Params/themis_data/tha_l3_sm_20080629_171151_20080629_171152_burst_v01.cdf \
root/Examples/Random/reader.py \
root/Examples/Random.dsdf.in \
root/Examples/Spectra/reader.sh.in \
root/Examples/Spectra.dsdf.in \
root/Examples/Waveform/reader.py \
root/Examples/Waveform.dsdf.in \
root/Examples/Waveform/vgr_data/example_wfrm-spectra.png \
root/Examples/Waveform/vgr_data/PDSFORMAT.LBL \
root/Examples/Waveform/vgr_data/VG1_1979-03-01_12-26-11-956.DAT \
root/Examples/Waveform/vgr_data/VG1_1979-03-01_12-27-47-956.DAT \
root/Examples/Waveform/vgr_data/VG1_1979-03-01_12-26-59-956.DAT \
root/Examples/Waveform/vgr_data/VG1_1979-03-01_12-28-35-956.DAT \
root/Examples/Waveform/vgr_data/WFENGHDR.FMT \
root/Examples/Waveform/vgr_data/WFROWPFX.FMT \

SRC_FILES:=$(patsubst %,src/dasflex/%,$(SRC)) pyproject.toml MANIFEST.in

SCRIPTS:=websocd cupdate das2test mkroot add
# Task management not yet re-implimented
# todo
SCRIPT_MOD:=$(patsubst %,dasflex.scripts.%,$(SCRIPTS))

# ########################################################################### #

.PHONY: build test install distclean clean

# We have no C-code here, easy to guess the wheelfile name (until some new
# fad takes over)
build: dist/$(WHEEL_FILE)

dist/$(WHEEL_FILE):$(SRC_FILES) build_venv/bin/python
	build_venv/bin/python -m build

build_venv/bin/python:
	$(PY_BIN) -m $(VENV_MOD) build_venv
	build_venv/bin/python -m pip install build

# Make sure top level scripts can at least run well enough to print their help
# text, then run unittests.  Only auth.py has unittests so far. 
test:dist/$(WHEEL_FILE)
	$(PY_BIN) -m $(VENV_MOD) test_venv
	./test_venv/bin/python -m pip install $(PIP_ARGS) $(DAS_WHEEL_PATH)
	./test_venv/bin/python -m pip install $(PIP_ARGS) dist/$(WHEEL_FILE)
	@for MOD in $(SCRIPT_MOD) ; do ./test_venv/bin/python -m $$MOD -h ; done
	./test_venv/bin/python -m unittest dasflex.webutil.auth
	mkdir -p $(PWD)/test_srv
	./test_venv/bin/dasflex_mkroot $(PWD)/test_srv BUILD_HOST
	./test_venv/bin/dasflex_add -I -c test_srv/etc/dasflex.conf -d test
	./test_venv/bin/dasflex_add -I -c test_srv/etc/dasflex.conf -d test_srv/dsdf
	./test_venv/bin/dasflex_cupdate $(PWD)/test_srv/etc/dasflex.conf

install:
	@$(PY_BIN) -m pip uninstall -y ./dist/$(WHEEL_FILE)
	$(PY_BIN) -m pip install --pre ./dist/$(WHEEL_FILE)

distclean:
	-rm -r dist test_venv test_srv build_venv

clean:
	-rm -r test_venv test_srv build_venv
