#pragma once
#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#endif
inline size_t process_peak() {
#ifdef _WIN32
    PROCESS_MEMORY_COUNTERS mem{}; mem.cb=sizeof(mem);
    if(!GetProcessMemoryInfo(GetCurrentProcess(),&mem,sizeof(mem))) throw std::runtime_error("memory query failed");
    return mem.PeakWorkingSetSize;
#else
    return 0;
#endif
}
