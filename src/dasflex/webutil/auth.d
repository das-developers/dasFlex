module dasflex.webutil.auth;

import std.string : split;

struct Auth {
    bool addrInRange(auto ref fLog, string ip, string ranges) {
        if (!ranges.length) return true; // default allow
        foreach (tok; ranges.split()) {
            if (tok == ip) return true;
        }
        return false;
    }
}
