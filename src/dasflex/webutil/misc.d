module dasflex.webutil.misc;

import std.process : environment;
import std.regex   : regex, match;
import std.string  : toLower, format;

struct Misc {
    void envPathMunge(string key, string extra) {
        if (!extra.length) return;
        auto old = environment.get(key);
        environment[key] = old.length ? (extra ~ ":" ~ old) : extra;
    }

    bool checkParams(ref typeof(this).LogProto log, auto form) {
        auto suspicious = regex(`(?:\b(?:;|&&|\|\|)|[`"\\]|<(?:script|\?|%)|%[0-9A-Fa-f]{2})`);
        foreach (k, v; form.params) {
            if (match(v, suspicious)) {
                log.write(format("Param suspicious: %s=%s", k, v));
                return false;
            }
        }
        return true;
    }

    bool isTrue(string key, const string[string] dConf) {
        if (!(key in dConf)) return false;
        auto s = dConf[key].toLower();
        return s == "true" || s == "1" || s == "yes";
    }

    alias LogProto = struct { void write(string) {} };
}
