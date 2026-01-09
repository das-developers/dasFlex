module dasflex.webutil.page;

import std.stdio;
import std.string : format;

struct Page {
    void header(const string[string] dConf, auto ref fLog, string title = "") {
        if (title.length) stdout.write(format("# %s\n\n", title));
    }
    void sidenav(const string[string] dConf, auto ref fLog, bool showForm = false) {
        stdout.write("\n");
    }
    void footer(const string[string] dConf, auto ref fLog) {
        stdout.write("\n");
    }
}
