#pragma once
#include "cpu_support.hpp"

SC_MODULE(CPU) {
    tlm_utils::simple_initiator_socket<CPU> socket;
    std::array<uint32_t, 8> regs{};
    Program program;
    sc_signal<unsigned> pc_signal{"pc"}, result_signal{"r0"};
    bool failed = false;

    SC_HAS_PROCESS(CPU);
    CPU(sc_module_name name, const std::string& path);
    uint32_t& reg(const std::string& name);
    void execute(const Instruction& ins, size_t& pc);
    void run();
};
