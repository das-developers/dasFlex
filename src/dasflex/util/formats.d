module dasflex.util.formats;

import std.typecons : Tuple, tuple;
import std.string   : toLower;

/// Python counterpart: util/formats.py
/// Provide a format negotiation helper returning (mime, ext, title)
struct Formats {
    auto pick(string fmt, string ver = null, string serial = null) {
        fmt = fmt.toLower();
        serial = serial.toLower();
        if (fmt == "das3" || fmt == "das2") {
            if (serial == "text") return tuple("text/vnd.das3.das3stream", "d3t", "Das3 Text");
            return tuple("application/vnd.das3.das3stream", "d3s", "Das3 Binary");
        }
        if (fmt == "csv") return tuple("text/csv; charset=utf-8", "csv", "CSV");
        if (fmt == "json") return tuple("application/json", "json", "JSON");
        return tuple("application/octet-stream", "bin", "Binary");
    }
}
