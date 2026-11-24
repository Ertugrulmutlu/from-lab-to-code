#pragma once
#include "observations.hpp"
#include <tlm>
#include <tlm_utils/simple_initiator_socket.h>
#include <tlm_utils/simple_target_socket.h>
#include <fstream>
#include <vector>
#include <map>
#include <cstring>
#include <stdexcept>
using namespace tlm;

struct Instruction {
    std::string op;
    std::vector<std::string> args;
    void require(size_t count) const {
        if (args.size() != count)
            throw std::runtime_error("Wrong argument count for " + op);
    }
};

struct Program {
    std::vector<Instruction> code;
    std::map<std::string, size_t> labels;

    explicit Program(const std::string& path) {
        std::ifstream file(path);
        if (!file) throw std::runtime_error("Cannot open assembly");
        std::string line;
        while (std::getline(file, line)) {
            line = line.substr(0, line.find('#'));
            for (char& ch : line) if (ch == ',') ch = ' ';
            std::istringstream words(line);
            std::string op;
            if (!(words >> op)) continue;
            if (op.back() == ':') {
                op.pop_back();
                if (!labels.emplace(op, code.size()).second)
                    throw std::runtime_error("Duplicate label: " + op);
                if (!(words >> op)) continue;
            }
            Instruction ins{op, {}};
            std::string arg;
            while (words >> arg) ins.args.push_back(arg);
            code.push_back(ins);
        }
    }
};

inline uint32_t immediate(const std::string& text) {
    size_t pos = 0;
    auto value = std::stoll(text, &pos, 0);
    if (pos != text.size()) throw std::runtime_error("Invalid integer: " + text);
    return static_cast<uint32_t>(value);
}

inline uint32_t& register_at(std::array<uint32_t, 8>& regs, const std::string& name) {
    if (name.size() != 2 || name[0] != 'R' || name[1] < '0' || name[1] > '7')
        throw std::runtime_error("Invalid register: " + name);
    return regs[name[1] - '0'];
}

// Pack a 32-bit word into a standard TLM payload. The caller is an SC_THREAD.
template<class Socket>
uint32_t transfer_word(Socket& socket, bool write, uint32_t address, uint32_t value) {
    unsigned char bytes[4];
    for (int i = 0; i < 4; ++i) bytes[i] = static_cast<unsigned char>(value >> (8*i));
    tlm_generic_payload payload;
    payload.set_command(write ? TLM_WRITE_COMMAND : TLM_READ_COMMAND);
    payload.set_address(address);
    payload.set_data_ptr(bytes);
    payload.set_data_length(4);
    payload.set_streaming_width(4);
    payload.set_response_status(TLM_INCOMPLETE_RESPONSE);
    sc_time delay = SC_ZERO_TIME;
    socket->b_transport(payload, delay);
    if (payload.is_response_error())
        throw std::runtime_error("TLM response: " + payload.get_response_string());
    value = 0;
    for (int i = 0; i < 4; ++i) value |= uint32_t(bytes[i]) << (8*i);
    transaction_event(write, address, value, delay);
    sc_core::wait(delay);
    return value;
}
