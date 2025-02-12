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

All sources are now on github.com

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
$ export PREFIX=/var/www/dasflex     # Adjust to taste
$ export N_ARCH=/                    # since das2 servers are typically machine bound
$ export PYVER=3.9                   # minimum 3.6
$ export SERVER_ID=solar_orbiter_2   # for example.  ID should not contain whitespace
```

Test your `PYVER` setting by making sure the following command brings up a
python interpreter:

```bash
$ python$PYVER
```

Build and install commands can run without `sudo` if the install directory
is created manually.  The following will make the install directory and set
it's ownership to the current account.  We will lock it down after install.
```bash
$ sudo mkdir $PREFIX
$ sudo chown $LOGNAME $PREFIX
```

The following sequence will build, test, and install das2C and das2py
if you have all prerequisite libraries installed:

```bash
$ cd das2C
$ make
$ make test     # Contacts remote services, okay if those tests fail
$ make install
$ cd ../

$ cd das2py
$ make 
$ make test     # Also contacts remote servers, okay if those tests fail
$ make install
$ cd ../
```

Now build and install the python module and example configuration files.
Set `--install-lib` and `--prefix` as indicated, unless you want to hand
edit dasflex.conf after installation.  There is no need to run `build`
before this step.

```bash
$ cd ../dasFlex
$ python${PYVER} setup.py install --prefix=${PREFIX} --install-lib=${PREFIX}/lib/python${PYVER}
$ make install
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