// Offline SQLite bulk reader. The deployed V53 replay binary does not link SQLite.
#include <sqlite3.h>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

struct Row {
    int64_t ts;
    double x, y;
    int32_t index;
    char name[36];
};
static_assert(sizeof(Row)==64);
static thread_local std::vector<Row> rows;
static thread_local std::string failure;

extern "C" __declspec(dllexport) const char* read_error() { return failure.c_str(); }
extern "C" __declspec(dllexport) int read_rows(const char* path, const char* device,
        int64_t lo, int64_t hi, const Row** out) {
    rows.clear();
    sqlite3* db=nullptr;
    sqlite3_stmt* query=nullptr;
    auto fail=[&](const std::string& error) {
        failure=error; sqlite3_finalize(query); sqlite3_close(db); return -1;
    };
    if(sqlite3_open_v2(path,&db,SQLITE_OPEN_READONLY,nullptr)!=SQLITE_OK)
        return fail(sqlite3_errmsg(db));
    // Tolerate unrelated malformed catalog objects on read-only forensic snapshots.
    sqlite3_exec(db,"PRAGMA writable_schema=ON",nullptr,nullptr,nullptr);
    std::string table="Marker_"+std::string(device);
    std::string sql="SELECT timestamp,x,y,RoiCalState,markerIndex,markerName FROM "+table+
        " WHERE timestamp>=? AND timestamp<?";
    if(sqlite3_prepare_v2(db,sql.c_str(),-1,&query,nullptr)!=SQLITE_OK)
        return fail(sqlite3_errmsg(db));
    sqlite3_bind_int64(query,1,lo); sqlite3_bind_int64(query,2,hi);
    int status;
    while((status=sqlite3_step(query))==SQLITE_ROW) {
        Row r{};
        r.ts=sqlite3_column_int64(query,0);
        auto coordinate=[&](int col) {
            return sqlite3_column_int(query,3)==1 && sqlite3_column_type(query,col)!=SQLITE_NULL
                ? sqlite3_column_double(query,col) : std::numeric_limits<double>::quiet_NaN();
        };
        r.x=coordinate(1); r.y=coordinate(2); r.index=sqlite3_column_int(query,4);
        const auto* name=sqlite3_column_text(query,5);
        const int length=sqlite3_column_bytes(query,5);
        if(!name || length<1 || length>=int(sizeof(r.name))) return fail("unsupported marker name");
        std::memcpy(r.name,name,length); rows.push_back(r);
    }
    if(status!=SQLITE_DONE) return fail(sqlite3_errmsg(db));
    sqlite3_finalize(query); sqlite3_close(db); *out=rows.data();
    return static_cast<int>(rows.size());
}
