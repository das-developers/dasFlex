module dasflex.webutil.mime;

import std.string : toLower;
import std.typecons : Tuple, tuple;

struct Mime {
    auto load(const string[string] dConf) { return 0; }

    auto get(int /*table*/, string sType, string sVer, string sSerial) {
        string mime = "application/octet-stream";
        string ext  = "bin";
        string title = "Binary";
        if (sType == "das3" || sType == "das2") {
            if (sSerial == "text") { mime = "text/vnd.das3.das3stream"; ext = "d3t"; title = "Das3 Text"; }
            else { mime = "application/vnd.das3.das3stream"; ext = "d3s"; title = "Das3 Binary"; }
        } else if (sType == "csv") { mime = "text/csv; charset=utf-8"; ext = "csv"; title = "CSV"; }
        return tuple(mime, ext, title);
    }

    auto getMimeByExt(string sFile) {
        auto extPos = sFile.lastIndexOf('.');
        string ext = extPos < 0 ? "" : sFile[extPos+1 .. $].toLower();
        string type = "application/octet-stream";
        final switch (ext) {
        case "html": case "htm": type = "text/html; charset=utf-8"; break;
        case "css": type = "text/css; charset=utf-8"; break;
        case "js": type = "application/javascript"; break;
        case "json": type = "application/json; charset=utf-8"; break;
        case "png": type = "image/png"; break;
        case "jpg": case "jpeg": type = "image/jpeg"; break;
        case "svg": type = "image/svg+xml"; break;
        case "txt": type = "text/plain; charset=utf-8"; break;
        case "d2t": type = "text/vnd.das2.das2stream; charset=utf-8"; break;
        case "d2s": type = "application/vnd.das2.das2stream"; break;
        default: break;
        }
        string disp = "inline";
        return tuple(type, disp, ext);
    }
}
