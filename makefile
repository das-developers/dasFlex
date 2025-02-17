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


ifeq ($(PYVER),)
	PYVER=3
endif

ifeq ($(PY_BIN),)
PY_BIN=$(which python)

ifeq ($(PY_BIN),)
PY_BIN=$(which python3)
endif

ifeq ($(PY_BIN),)
$(error Neither python nor python3 were found, set PY_BIN to the path to your python interpreter)
endif
endif


# Only affects the *_old targets
ifeq ($(PREFIX),)
	PREFIX:=/var/www/dasflex
endif

ifeq ($(INST_ETC),)
	INST_ETC:=$(PREFIX)/etc
endif

ifeq ($(N_ARCH),)
	N_ARCH:=/   
endif

PYVER:=$(shell $(PY_BIN) -c "import sys; print('%d.%d'%sys.version_info[:2])")
# ... end old env vars

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
scripts/srctest.py scripts/mkroot.py scripts/todo.py \
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
root/Examples/Auth/source.dsdf.in \
root/Examples/Params/reader.py \
root/Examples/Params/source.dsdf.in \
root/Examples/Params/themis_data/CAA_EST_UG_STA_v36.pdf \
root/Examples/Params/themis_data/tha_l3_sm_20080629_171151_20080629_171152_burst_v01.cdf \
root/Examples/Random/reader.py \
root/Examples/Random/source.dsdf.in \
root/Examples/Spectra/reader.sh.in \
root/Examples/Spectra/source.dsdf.in \
root/Examples/Waveform/reader.py \
root/Examples/Waveform/source.dsdf.in \
root/Examples/Waveform/vgr_data/example_wfrm-spectra.png \
root/Examples/Waveform/vgr_data/PDSFORMAT.LBL \
root/Examples/Waveform/vgr_data/VG1_1979-03-01_12-26-11-956.DAT \
root/Examples/Waveform/vgr_data/VG1_1979-03-01_12-27-47-956.DAT \
root/Examples/Waveform/vgr_data/VG1_1979-03-01_12-26-59-956.DAT \
root/Examples/Waveform/vgr_data/VG1_1979-03-01_12-28-35-956.DAT \
root/Examples/Waveform/vgr_data/WFENGHDR.FMT \
root/Examples/Waveform/vgr_data/WFROWPFX.FMT \

SRC_FILES:=$(patsubst %,src/dasflex/%,$(SRC)) pyproject.toml MANIFEST.in

.PHONY: build install distclean clean

build: dist/dasflex-0.4rc2.tar.gz

dist/dasflex-0.4rc2.tar.gz:$(SRC_FILES)
	python -m build 

install:
	@python -m pip uninstall -y ./dist/dasflex*.whl
	python -m pip install --pre ./dist/dasflex*.whl

distclean:
	-rm -r dist

clean:
	-rm -r dist

# Non-venv installer for use by older projects
build_old:
	$(PY_BIN) legacy/setup.py build

install_old_noex:
	$(PY_BIN) legacy/setup.py install --prefix=${PREFIX} \
 	   --install-lib=${PREFIX}/lib/python${PYVER} \
 	   --install-scripts=${PREFIX}/bin/${N_ARCH} --no-examples
	@echo "-------------------------------------------------------------------"
	@echo "Scripts installed, run dasflex_mkroot to define your server and "
	@echo "symlink dasflex_cgimain and dasflex_logmain from your designated "
	@echo "CGI bin directory"
	@echo "-------------------------------------------------------------------"

install_old:
	python${PYVER} legacy/setup.py install --prefix=${PREFIX} \
	  --install-lib=${PREFIX}/lib/python${PYVER} \
	  --install-scripts=${PREFIX}/bin/${N_ARCH}
	@echo "-------------------------------------------------------------------"
	@echo "Scripts installed, run dasflex_mkroot to define your server and "
	@echo "symlink dasflex_cgimain and dasflex_logmain from your designated "
	@echo "CGI bin directory"
	@echo "-------------------------------------------------------------------"
