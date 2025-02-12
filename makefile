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
#   PYVER
#
# though N_ARCH is still set for older install methods.
#
# Also, the new command dasflex_mkroot now set's the variables that
# used to be set via: 
# 
#   PREFIX 
#   INST_ETC
#
# so these are no longer needed as well.  This is a big change.

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

ifeq ($(PYVER),)
	PYVER=3
endif

# ... end old env vars

build:
	python -m build 

install:
	python -m pip install --pre ./dist/dasflex*.whl

distclean:
	-rm -r build
	-rm -r dist

clean:
	-rm -r build
	-rm -r dist

# Non-venv installer for use by older projects
build_old:
	python${PYVER} legacy/setup.py build

install_old_noex:
	python${PYVER} setup.py install --prefix=${PREFIX} \
 	   --install-lib=${PREFIX}/lib/python${PYVER} \
 	   --install-scripts=${PREFIX}/bin/${N_ARCH} --no-examples
	@echo "-------------------------------------------------------------------"
	@echo "Scripts installed, run dasflex_mkroot to define your server and "
	@echo "symlink dasflex_cgimain and dasflex_logmain from your designated "
	@echo "CGI bin directory"
	@echo "-------------------------------------------------------------------"

install_old:
	python${PYVER} setup.py install --prefix=${PREFIX} \
	  --install-lib=${PREFIX}/lib/python${PYVER} \
	  --install-scripts=${PREFIX}/bin/${N_ARCH}
	@echo "-------------------------------------------------------------------"
	@echo "Scripts installed, run dasflex_mkroot to define your server and "
	@echo "symlink dasflex_cgimain and dasflex_logmain from your designated "
	@echo "CGI bin directory"
	@echo "-------------------------------------------------------------------"
