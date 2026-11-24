#include "CPU.h"
#include "Memory.h"

int sc_main(int argc, char** argv) {
    try {
        CPU cpu("cpu", "/input/program.asm");
        Memory mem("memory", arg(argc, argv, 5, 10));
        cpu.socket.bind(mem.socket);

        auto* trace = trace_start();
        sc_trace(trace, cpu.pc_signal, "PC");
        sc_trace(trace, cpu.result_signal, "R0");
        sc_start();
        sc_close_vcd_trace_file(trace);
        return cpu.failed ? 1 : 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
