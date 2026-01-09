module dasflex.webutil.command;

import std.process : spawnProcess, Pid, wait;
import std.string  : format;
import std.stdio;

/// Python counterpart: webutil/command.py
struct Command {
    int run(string exe, string[] args) {
        auto p = spawnProcess([exe] ~ args);
        auto code = wait(p);
        return code;
    }
}
