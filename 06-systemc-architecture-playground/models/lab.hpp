#pragma once
#include <systemc>
#include <iostream>
#include <string>
#include <cstdlib>
using namespace sc_core;
using namespace sc_dt;
inline void event(const std::string& kind, const std::string& fields="") {
    std::cout << "@@EVENT@@{\"kind\":\"" << kind << "\",\"time_ns\":"
        << sc_time_stamp().to_seconds()*1e9 << ",\"delta\":" << sc_delta_count()
        << fields << "}" << std::endl;
}
inline int arg(int argc, char** argv, int index, int fallback) {
    return argc>index ? std::stoi(argv[index]) : fallback;
}
inline sc_trace_file* trace_start() {
    auto* t=sc_create_vcd_trace_file("trace"); t->set_time_unit(1,SC_NS); return t;
}
