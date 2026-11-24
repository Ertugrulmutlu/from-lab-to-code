#include "CPU.h"

// One instruction: arithmetic, branches or memory transactions.
void CPU::execute(const Instruction& ins, size_t& pc) {
    const auto& op = ins.op;
    const auto& a = ins.args;
    if (op == "MOVI") {
        ins.require(2); reg(a[0]) = immediate(a[1]);
    } else if (op == "MOV") {
        ins.require(2); reg(a[0]) = reg(a[1]);
    } else if (op == "ADD") {
        ins.require(3); reg(a[0]) = reg(a[1]) + reg(a[2]);
    } else if (op == "ADDI") {
        ins.require(3); reg(a[0]) = reg(a[1]) + immediate(a[2]);
    } else if (op == "JNZ") {
        ins.require(2);
        if (reg(a[0]) != 0) pc = program.labels.at(a[1]);
    } else if (op == "STORE") {
        ins.require(2);
        transfer_word(socket, true, immediate(a[1]), reg(a[0]));
    } else if (op == "LOAD") {
        ins.require(2);
        reg(a[0]) = transfer_word(socket, false, immediate(a[1]), 0);
    } else if (op == "HALT") {
        ins.require(0);
    } else {
        throw std::runtime_error("Unknown opcode: " + op);
    }
}
