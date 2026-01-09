module dasflex.webutil.webio;

import std.stdio;
import std.file   : append, exists, mkdirRecurse, isDir;
import std.datetime : Clock, DateTime;
import std.process : environment;
import std.string : format, replace, toLower;

/// Simple log file object; mirrors Python DasLogFile(path, ip)
struct DasLog {
    string path;
    string ip;
    this(string path = null, string ip = null) {
        this.path = path;
        this.ip   = ip;
        if (path.length) {
            auto pdir = path[0 .. path.lastIndexOf('/') < 0 ? 0 : path.lastIndexOf('/')];
            if (pdir.length && !isDir(pdir)) mkdirRecurse(pdir);
        }
    }
    void write(string msg) {
        auto ts = Clock.currTime;
        auto line = format("[%04d-%02d-%02d %02d:%02d:%02d] ip=%s %s\n",
            ts.year, ts.month, ts.day, ts.hour, ts.minute, ts.second,
            ip.length ? ip : environment.get("REMOTE_ADDR"), msg);
        if (path.length) append(path, line);
        else             stderr.write(line);
    }
}

struct WebIO {
    void pout(const(ubyte)[] item) { stdout.rawWrite(item); }
    void pout(string item)         { stdout.write(item); }

    void writeHeaders(string contentType, bool noCache = false) {
        pout("Status: 200 OK\r\n");
        pout("Content-Type: " ~ contentType ~ "\r\n");
        if (noCache) {
            pout("Cache-Control: no-store, no-cache, must-revalidate\r\n");
            pout("Pragma: no-cache\r\n");
        }
        pout("\r\n");
    }

    void queryError(ref DasLog log, string msg) {
        pout("Status: 400 Bad Request\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n");
        pout(msg ~ "\n");
        log.write("QUERY ERROR: " ~ msg.replace("\n", " "));
    }
    void notFoundError(ref DasLog log, string msg) {
        pout("Status: 404 Not Found\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n");
        pout(msg ~ "\n");
        log.write("NOT FOUND: " ~ msg.replace("\n", " "));
    }
    void serverError(ref DasLog log, string msg) {
        pout("Status: 500 Internal Server Error\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n");
        pout(msg ~ "\n");
        log.write("SERVER ERROR: " ~ msg.replace("\n", " "));
    }

    string getUrl() {
        auto sn = environment.get("SCRIPT_NAME");
        auto qs = environment.get("QUERY_STRING");
        auto pi = environment.get("PATH_INFO");
        string url = sn ~ (pi.length ? pi : "");
        if (qs.length) url ~= "?" ~ qs;
        return url;
    }

    string getScriptUrl(const string[string] dConf = null) {
        auto srv = environment.get("SERVER_NAME");
        auto sn  = environment.get("SCRIPT_NAME");
        auto https = environment.get("HTTPS");
        auto scheme = (https == "on" || https == "1") ? "https" : "http";
        return scheme ~ "://" ~ srv ~ sn;
    }

    string httpNextYear() {
        auto dt = Clock.currTime;
        auto next = DateTime(dt.year + 1, dt.month, dt.day, dt.hour, dt.minute, dt.second);
        return format("%04d-%02d-%02d %02d:%02d:%02d GMT", next.year, next.month, next.day, next.hour, next.minute, next.second);
    }

    DasLog DasLogFile(string path = null, string ip = null) { return DasLog(path, ip); }
}

struct UType {
    WebIO webio;
    import dasflex.webutil.misc : Misc;
    import dasflex.webutil.page : Page;
    import dasflex.webutil.mime : Mime;
    import dasflex.webutil.auth : Auth;
    import dasflex.webutil.das2 : Das2;
    Misc  misc;
    Page  page;
    Mime  mime;
    Auth  auth;
    Das2  das2;
}

UType dasflexGetU() {
    UType u;
    u.webio = WebIO();
    u.misc  = Misc();
    u.page  = Page();
    u.mime  = Mime();
    u.auth  = Auth();
    u.das2  = Das2();
    return u;
}
