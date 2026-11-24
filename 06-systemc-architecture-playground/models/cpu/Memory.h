#pragma once
#include "cpu_support.hpp"

SC_MODULE(Memory) {
    tlm_utils::simple_target_socket<Memory> socket;
    std::array<unsigned char, 256> data{};
    int latency;

    Memory(sc_module_name name, int delay);
    void transport(tlm_generic_payload& p, sc_time& delay);
};
