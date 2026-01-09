module dasflex.util.convjson;

import std.json;

/// Python counterpart: util/convjson.py
/// Placeholder: conversions to JSON for catalog/stream metadata.
struct ConvJSON {
    JSONValue wrapString(string s) { JSONValue j; j["value"] = s; return j; }
}
