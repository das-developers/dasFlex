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

# Directory for the test server
TEST_SRV:=test_srv

# ########################################################################### #
# Pickup the das2C utilities, assume they are next door
DAS2C_PATH=$(abspath ../das2C/build.$(N_ARCH))
DAS2C_BINS=das1_ascii das1_bin_avg das2_ascii das2_bin_avg das2_bin_avgsec \
 das2_bin_peakavgsec das2_bin_ratesec das2_cache_rdr das2_from_das1 \
 das2_from_tagged_das1 das2_hapi das2_histo das2_psd das3_cdf das3_csv \
 das3_spice 

DAS2C_LIBS=libcdf.so

DAS2C_TEST_PROGS=$(patsubst %,test_srv/bin/%,$(DAS2C_BINS))
DAS2C_TEST_LIBS=$(patsubst  %,test_srv/lib/%,$(DAS2C_LIBS))

# ########################################################################### #

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
scripts/das2test.py scripts/mkroot.py scripts/todo.py scripts/cadd.py\
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
root/Examples/Model.dsdf.in \
root/Examples/Model/reader.py \
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

SCRIPTS:=websocd cupdate das2test mkroot cadd
# Task management not yet re-implimented
# todo
SCRIPT_MOD:=$(patsubst %,dasflex.scripts.%,$(SCRIPTS))

# ########################################################################### #
# Implicit rule to copy over test das2C bins and the CDF library

$(TEST_SRV)/bin/%:$(DAS2C_PATH)/%
	cp -p $< $@

$(TEST_SRV)/lib/%:$(DAS2C_PATH)/%
	cp -p $< $@


# ########################################################################### #

.PHONY: build test test_srv test_dsdf install distclean clean dist

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
test_srv:dist/$(WHEEL_FILE)
	$(PY_BIN) -m $(VENV_MOD) $(TEST_SRV)
	./test_srv/bin/python -m pip install $(PIP_ARGS) $(DAS_WHEEL_PATH)
	./test_srv/bin/python -m pip install $(PIP_ARGS) dist/$(WHEEL_FILE)
	@for MOD in $(SCRIPT_MOD) ; do ./test_srv/bin/python -m $$MOD -h ; done
	./test_srv/bin/python -m unittest dasflex.webutil.auth
	./test_srv/bin/dasflex_mkroot $(PWD)/test_srv BUILD_HOST

# Test importing DSDF files
test_dsdf:
	./test_srv/bin/dasflex_cadd -o tmp -c test_srv/etc/dasflex.conf -d test test/Juno/Ephemeris/Jovicentric.dsdf
	./test_srv/bin/dasflex_cadd -I -c test_srv/etc/dasflex.conf -d test
	./test_srv/bin/dasflex_cadd -I -c test_srv/etc/dasflex.conf -d test_srv/dsdf
	./test_srv/bin/dasflex_cupdate $(PWD)/test_srv/etc/dasflex.conf

# Test legacy queries
test_das2:
	./test/cgi_main.sh >/dev/null
	./test/cgi_main.sh "" "server=list"

# Test new flexible queries
test_forms:
	./test/cgi_main.sh "/source/juno.html" > /dev/null
	./test/cgi_main.sh "/source/juno/wav/survey.html" > /dev/null
	./test/cgi_main.sh "/source/juno/ephemeris/jovicentric.html" > /dev/null
	./test/cgi_main.sh "/source/examples/random.html" > /dev/null
	mkdir -p test_data

test_random:
	./test/cgi_main.sh /source/examples/random/flex read.time.min=2025-01-01 read.time.max=2025-02-01 > test_data/random.d2t
	./test_srv/bin/python test/cut_http_hdrs.py test_data/random.d2t
	./test_srv/bin/das_verify test_data/random.d2t

test_model:
	./test/cgi_main.sh /source/examples/model/flex read.time.inter=1800 read.time.min=2026-03-01 read.time.max=2026-03-04 > test_data/model.d2t
	./test_srv/bin/python test/cut_http_hdrs.py test_data/model.d2t
	./test_srv/bin/das_verify test_data/model.d2t

test_avg:
	./test/cgi_main.sh /source/examples/spectra/flex bin.time.max=10 read.time.min=1979-03-01T12:26:11 read.time.max=1979-03-01T12:29:24 > test_data/spectra.d2s
	./test_srv/bin/python test/cut_http_hdrs.py test_data/spectra.d2s
	./test_srv/bin/das_verify test_data/spectra.d2s

test_csv:
	./test/cgi_main.sh /source/examples/random/flex format.type=csv read.time.min=2025-01-01 read.time.max=2025-02-01 > test_data/random.csv
	./test_srv/bin/python test/cut_http_hdrs.py test_data/random.csv
	# no csv verify

test_cdf:
	./test/cgi_main.sh /source/examples/waveform/flex format.type=cdf read.time.min=1979-03-01T12:26:11 read.time.max=1979-03-01T12:29:24 > test_data/waveform.cdf
	./test_srv/bin/python test/cut_http_hdrs.py test_data/waveform.cdf
	./test_srv/bin/das_cdf_info test_data/waveform.cdf

test_data: $(DAS2C_TEST_LIBS) $(DAS2C_TEST_PROGS) test_random test_model test_avg test_csv test_cdf

test:test_srv test_dsdf test_das2 test_forms test_data

install:
	@$(PY_BIN) -m pip uninstall -y ./dist/$(WHEEL_FILE)
	$(PY_BIN) -m pip install --pre ./dist/$(WHEEL_FILE)

distclean:
	-rm -r dist build_venv test_srv test_data

clean:
	-rm -r build_venv test_srv test_data
