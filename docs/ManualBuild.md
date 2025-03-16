# Building dasFlex from source

## Installation Prequisites

Compilation and installation of a dasFlex server has only been tested in Linux
environments and depends on the following tools:

1. Python >= 3.7
2. Apache2, any remotely recent version
3. [Redis](https://redis.io), known to work with version 3.2 or higher
4. [redis-py](https://redislabs.com/lp/python-redis/), known to work with version 2.10 or higher
5. [lxml](https://github.com/lxml/lxml), known to work with version 4.2 or higher
6. [das2py](https://github.com/das-developers/das2py), latest version recommended

Installing from PIP will also bring in the python dependencies, but the Apache2
and Redis server software will have have to be installed separately

Since das2C provides small binaries needed by dasFlex, and since these instructions
assume you are not using pre-build das2C binaries, installation instructions for 
das2C, das2py and dasFlex are included below.  In these instructions the '$' character
is used at the beginning of a line to indicate commands that you'll need to run
in a bourne compatible shell (bash, ksh, etc.).

Example prerequisite package installation commands are provided below for CentOS 7 \.\.\.
```bash
$ sudo yum install gcc git                               
$ sudo yum install expat-devel fftw-devel openssl-devel             
$ sudo yum install python3 python3-numpy python3-devel 
$ sudo pip3 install redis
```
\.\.\. and Debian 9:
```bash
$ sudo apt-get install gcc git                           
$ sudo apt-get install libexpat-dev libfftw3-dev libssl-dev          
$ sudo apt-get install python3-dev python3-distutils python3-numpy
$ sudo apt-get install redis-server                                 
$ sudo apt-get install python3-redis
```

## Get the Source

All sources are on github.com

```bash
$ git clone https://github.com/das-developers/das2C.git
$ git clone https://github.com/das-developers/das2py.git
$ git clone https://github.com/das-developers/dasFlex.git
```

## Build and Install

Decide where your dasFlex code and configuration information will reside. 
In the example below I've  selected `/var/www/dasflex` but you can choose
any location you like.  These environment variables will be used through out
the setup, so leaving your terminal window open though the testing stage will
save time.

```bash
$ export PREFIX=/var/www/dasflex # Adjust to taste
$ export N_ARCH=/                # not using shared filesys, no need to separate binaries
```

Build and install commands can run without `sudo` if the install directory
is created manually.  The following will make the install directory and set
it's ownership to the current account.  We will lock it down after install.
```bash
$ sudo mkdir $PREFIX
$ sudo chown $LOGNAME $PREFIX
```

1. We're going to build this in layers. The lowest layer contains the C libraries and fast
   stream parsers.

   ```bash
   $ cd das2C
   $ make
   $ make test          # Contacts remote services, okay if some network tests fail
   $ make util_install  # Only installs the stream processor binaries, not dev files
   $ cd ../
   ```
   When this step is complete you should see the following:
   ```bash
   $ ls $PREFIX/bin
   das1_ascii        das1_inctime          das2_bin_avgsec  das2_cache_rdr  das2_hapi
   das2_psd          das3_test             das1_bin_avg     das2_ascii      das2_bin_peakavgsec
   das2_from_das1    das2_histo            das3_csv         das1_fxtime     das2_bin_avg
   das2_bin_ratesec  das2_from_tagged_das1 das2_prtime      das3_node
   ```

2. Next add the python layer.  First define a virtual environment so that server 
   packages are separate from your system echosystem.  For example:
   ```bash
   /usr/bin/python3.12 -m venv $PREFIX/venv
   $PREFIX/venv/bin/python -m pip install --upgrade pip
   $PREFIX/venv/bin/python -m pip install build
   ```
   Then build and install the python library using your new python virtual environment.  The
   build script will need to find das2C libraries.
   ```bash
   $ env DAS2C_INCDIR=$PWD/das2C DAS2C_LIBDIR=$PWD/das2C/build. $PREFIX/venv/bin/python -m build ./das2py
   # Don't forget the '.' at the end of 'build.'.
   $ $PREFIX/venv/bin/python -m pip install das2py/dist/das2py-*.whl
   ```

3. Now build and install the server itself:
   ```bash
   $ $PREFIX/venv/bin/python -m build ./dasFlex
   $ $PREFIX/venv/bin/python -m pip install ./dist/dasflex*whl
   ```
   This step provides the toplevel server scripts, you can see these in your virtual
   environment via:
   ```bash
   $ ls $PREFIX/venv/bin
   dasflex_cgilog    dasflex_mkroot   dasflex_cgimain   dasflex_todo
   dasflex_cupdate   dasflex_websocd  dasflex_das2test
   # Among other a few other items
   ```

## Configure

If all the steps above completed, you now have all tools to setup an run a server but no 
server is defined.  To do so run the `dasflex_mkroot` script.

```bash
$ $PREFIX/venv/bin/dasflex_mkroot -h  # See help options first
$ $PREFIX/venv/bin/dasflex_mkroot $PREFIX "Test_Server"
```
You can add the argument `--no-examples` to avoid installing the example
data sources if these are not desired.

Copy over the example configuration file:

```bash
$ cd ${PREFIX}/etc
$ cp dasflex.conf.example dasflex.conf
```

We are done with server software installation, lock down the install area (if desired). 
The `cache` subdirectory shoud be owned by the account that runs asynchronous 
data-reduction processing.  The cache subdirectory should not be owned by the
webserver account, or root, but any other account is fine.
```bash
$ sudo chown -R root:root $PREFIX
$ sudo chown $LOGNAME $PREFIX/cache         # i.e. any non-apache, non-root account
```

From here you can return to the *Server Root Setup* section in the primary
[README.md](../README.md).