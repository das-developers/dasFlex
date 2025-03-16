# dasFlex server

[Das](https://das2.org) servers typically provide data relevant to space
plasma and magnetospheric physics research.  To retrieve data, an HTTP GET
request is posted to server by a client program.  The server then replies
with data formatted into the requested MIME-type.  The most flexible
reply is a *dasStream* version 3, though other output types are supported,
such as CSV files.

This software, *dasFlex* provides middleware layer between server-side data
readers, which stream data at full resolution to standard out, and remote client
programs such as [SDDAS](http://www.sddas.org/), [SPEDAS](https://github.com/spedas),
and [Autoplot](https://autoplot.org), or custom programs written in Java
([das2java](https://github.com/das-developers/das2java)), 
Python ([das2py](https://github.com/das-developers/das2py)), IDL
([das2pro](https://github.com/das-developers/das2pro), 
[das2dlm](https://github.com/das-developers/das2dlm) ), or C
([das2C](https://github.com/das-developers/das2C) ).  Since dasFlex is a multi-MIME
server, data may also be output as delimited text [CSV](https://github.com/das-developers/das2C/wiki/das3_csv) and as [CDF](https://github.com/das-developers/das2C/wiki/das3_cdf) files, 
which are common in space-physics research.

When a request for data is received, dasFlex inspects the HTTP GET URL against
local data source definitions and solves for the commands needed to
produced the desired output.  The command pipeline is then excuted and output
is transmitted to the client as an HTTP body, or as part of a WebSocket communication
session.

DasFlex itself is released under the GPL, but the core server merely acts 
as a command runner and output transport agent.  Data producing program may be
writen in **any** language, and released under almost **any** license.

## Installation Prequisites

Compilation and installation of a dasFlex server has only been tested in Linux
environments and depends on the following tools:

1. Python >= 3.7
2. Apache2, any remotely recent version
3. [Redis](https://redis.io), known to work with version 3.2 or higher


## Software Installation

> Currently not all packages are in PyPI, and the system dependencies are
> not distributed as .deb or .rpm files.  Build python packages from source
> using the instructions in [ManualBuild.md](docs/ManualBuild.md)

For Conda Packages (uncommon) issue:
```bash
conda install -c dasdevelopers dasflex
```
For PIP Packages issue:

It assumed that you're running a python binary from your virtual environment.
Theres no need to "enter" the environment, just provide a full path to the
version of python you wish to use for the server.
```bash
/path/to/your/python -m pip install dasFlex
```

## Server Root Setup

All configuration data for the dasFlex web-service itself consists of plain
files.  Redis is only used for work-lists.  Furthermore these files are not
cached in memory, but are read anew as each is needed.

To setup a server root area run `dasflex_mkroot`.  If you're using a python 
virtual environment you'll find the script installed under VENV_ROOT/bin.

```bash
dasflex_mkroot -h                              # see the help text first
dasflex_mkroot /var/www/dasflex  "Test_Server" # For example, adjust to taste
```

The only file that the main CGI programs need to know about is `dasflex.conf`. 
This contains the locations of all other items such as the data source catalog.
Feel free to break-up and move directories as desired.  So long as `dasflex.conf`
is updated with the new locations, top-level programs will be able to find all
the necessary server components.

After the server root has been created, customize `dasflex.conf`.  Starting with
the SERVER_NAME, SERVER_ID settings.

## Configure Apache - CGI

Apache configurations vary widely by Linux distribution and personal taste.
The following procedure is provided as an example and has been tested on
Rocky Linux 9.  It assumes you're using a python virtual environment to host
the main server scripts.

In the root of your SSL server, or in a `<VirtualHost>` section:
```apache
Alias /stream /var/www/dasflex/venv/bin/dasflex_cgimain
<Location /stream>

  # Provide CGI scripts with the location of the dasflex.conf file.
  # The location used here is just an example and changes depending
  # on the area selected by the `dasflex_mkroot` command above.
  SetEnv DASFLEX_CONFIG /var/www/dasflex/etc/dasflex.conf
  
  # Allow HTTP basic authentication to propogate to main script
  RewriteRule ^ - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]

  Options ExecCGI FollowSymLinks
  SetHandler cgi-script
  RewriteEngine on
</Location>

Alias /log /var/www/dasflex/venv/bin/dasflex_cgilog
<Location /log>
  SetEnv DASFLEX_CONFIG /var/www/dasflex/etc/dasflex.conf
  Options ExecCGI FollowSymLinks
  SetHandler cgi-script
  RewriteRule ^ - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]
  RewriteEngine on
  Require ip <LOG_IP_1> <LOG_IP_2>
</Location>
```
For security the log end-point shouldn't be open to the world, hence the `<LOG_IP_1>`
`<LOG_IP_2>` replacement text above.

By default, authorization headers are not made available to CGI scripts.
The re-write rule above allows the `Authorization` header to be passed down
to the `dasflex_cgimain` script.  This is needed to allow your server to
support password protected data sources.

## Try it out

Point your web browser at the path in the `Alias` statements above and see 
what you get.  It should be a simple text message instructing you to

The main server script needs to be able to find the main log reader
script and vice versa.  If you use something other than the default
values above update the following config entries in your `dasflex.conf`.
```ini
VIEW_LOG_URL = "log"
MAIN_SRV_URL = "server"
```

Set the permissions of the log directory so that Apache can write logging
information:

```bash
$ chmod 0777 /var/www/dasflex/log   # Or change the directory ownership
```

Finally, trigger a re-read of the Apache's configuration data:

```bash
$ sudo systemctl restart httpd.service
$ sudo systemctl status httpd.service
```
## Test the server

Test the server by pointing your web browser at:

```
https://localhost/das/server
https://localhost/das/log
```
If this works, try browsing your new server with Autoplot.  To do so, copy the
following URI into the Autoplot address bar and hit the green "Go" button:

```
vap+das2server:https://localhost/das/server
```

## Next steps

The CGI scripts and worker programs read thier configuration data from the
file:

```bash
/var/www/dasflex/etc/dasflex.conf
```

Take time to customize a few items in your config file such as the 
`site_title` and the `contact_email`.   You may also want change the file
`${PREFIX}/static/logo.png` or even the style sheet at 
`${PREFIX}/static/dasflex.css` to something a little nicer.

**DasFlex** is a caching and web-transport layer for data readers.  Readers
are the programs that generate the initial full resolution data streams.  The
entire purpose of dasFlex and das2 clients is to leverage the output of
your reader programs to produce efficient, interactive science data displays.
Example readers are included in the `/var/www/dasflex/examples` directory to assist you
with the task of creating readers for your own data.  These examples happen to
be written in python, however there is no requirement to use python for your
programs, in fact much more efficent compiled languages such as Java,
[D](https://dlang.org/) and C++ are more suitable for the task.  Any language
may be used so long as:

  1) all data are written to standard output
  2) all error messages are written to standard error

For further information on your dasFlex server instance, including:

  * reader programs
  * authentication 
  * request caching
  * [federated catalog](https://das2.org/browse) integration
  
consult the wiki associated with this repository.

## Examples License

All code in the examples directory (not including the temporary pycdf subdirectory)
is release under the UNLICENSE and may be used without restrictions of any kind.


## Experimental Feature: WebSocket support

The dasFlex server includes a websocket daemon for communicating with real-time
data sources.  This is not needed for standard server functionality, but it is
very useful for supporting hardware development, since technicians want to see 
instrument data immediately.  The assumption in the instructions below is that 
Apache will serve as the front door to the included **dasflex_websocd** daemon and
will handle encryption/decription.  The websocket daemon will only listen to the
local host and all backend communication between Apache and dasflex_websocd will
be unencrypted.

First add the trio-websocket package to your server virutal environment:

```bash
$ /var/www/dasflex/venv/bin/python -m pip install trio_websocket
```

Next, make sure mode the following apache modules are enabled:
```bash
a2enmod proxy proxy_wstunnel proxy_http rewrite
```
For RHEL-like systems, check the conf files in `/etc/httpd/conf.modules.d`.

Second in your applicable SSL server add the following.  If you're using 
the default SSL server on Ubuntu the file is located at `/etc/apache2/sites-enabled/default-ssl.conf`
or for RHEL, `/etc/httpd/conf.d/ssl.conf`.
```
<Location "/dasws/" >
  RewriteEngine on
  RewriteRule ^ - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]
  ProxyPreserveHost on
  ProxyPass "ws://localhost:52242/dasws/"
  ProxyPassReverse "ws://localhost:52242/dasws/"
</Location>
```
Here the value ws://localhost:52242/dasws/ should be whatever you've specifed 
for the `WEBSOCKET_URI` in your **dasflex.conf** file.

A client program is included for testing your websocket server.  An example of
running it for the included spectra example would be:
```
$ python3 dasflex/test/ws_test_client.py \
   wss://localhost/dasws/examples/spectra/flexRT \
   read.time.min=1979-03-01T12:26:11 \
   read.time.max=1979-03-01T12:29:24 \
   format.serial=text
```

The websock server should run as the same user as the regular CGI server.  This
is critical because the log to the same files.  That bears reapeating:

> **NOTE** Run dasflex_websocd as the apache user on your system.

To do this the following command will work work on Debian and derivitives:
```bash
sudo su -s /usr/bin/bash -c "/path/to/dasflex_websocd 127.0.0.1 52242 -D /path/to/log/websock.pid" www-data
```
The user account on Rocky Linux is different, but otherwise the command is the 
same.  A system-d unit file will be created as time permits.

To stop your server send **SIGINT** to the runing daemon
```bash
sudo kill -INT $(cat /path/to/log/websock.pid)
```
