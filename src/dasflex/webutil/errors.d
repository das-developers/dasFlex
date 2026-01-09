module dasflex.webutil.errors;

import std.stdio;
import std.string : replace;

import dasflex.webutil.webio : DasLog;

/// Python counterpart: webutil/errors.py
struct Errors {
    void write500(ref DasLog log, string msg) {
        stdout.write("Status: 500 Internal Server Error\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n");
        stdout.write(msg ~ "\n");
        log.write("SERVER ERROR: " ~ msg.replace("\n"," "));
    }
}
