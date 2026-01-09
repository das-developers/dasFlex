module dasflex.webutil.das2;

struct Das2 {
    string getSchemaName(string ver) {
        if (ver.length == 0) return "unknown";
        if (ver.startsWith("3")) return "das3.xsd";
        if (ver.startsWith("2")) return "das2.xsd";
        return "das.xsd";
    }
}
