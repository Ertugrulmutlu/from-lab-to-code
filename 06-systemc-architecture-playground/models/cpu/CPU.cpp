#include "CPU.h"

CPU::CPU(sc_module_name name, const std::string& path)
    : sc_module(name), socket("initiator"), program(path) {
    SC_THREAD(run);
}

uint32_t& CPU::reg(const std::string& name) {
    return register_at(regs, name);
}

// Fetch from the program vector, execute, record, wait.
void CPU::run() {
    try {
        size_t pc = 0;
        for (int step = 0; step < 4096; ++step) {
            if (pc >= program.code.size())
                throw std::runtime_error("PC out of range (missing HALT?)");
            size_t current = pc++;
            const auto& ins = program.code[current];
            execute(ins, pc);
            pc_signal.write(static_cast<unsigned>(current));
            result_signal.write(regs[0]);
            instruction_event(current, ins.op, regs);
            wait(1, SC_NS);
            if (ins.op == "HALT") {
                std::cout << "[cpu] HALT R0=" << regs[0] << '\n';
                sc_stop();
                return;
            }
        }
        throw std::runtime_error("Instruction limit exceeded");
    } catch (const std::exception& e) {
        failed = true;
        std::cerr << "[cpu] " << e.what() << '\n';
        sc_stop();
    }
}
