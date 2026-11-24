#pragma once
#include "lab.hpp"
#include <initializer_list>
#include <utility>
#include <sstream>
#include <array>
#include <cstdint>

// Presentation infrastructure: keep JSON out of the hardware models.
inline void signals(std::initializer_list<std::pair<const char*, int>> values) {
    std::string fields;
    for (const auto& [name, value] : values)
        fields += ",\"" + std::string(name) + "\":" + std::to_string(value);
    event("signal", fields);
}

SC_MODULE(RippleObserver) {
    sc_vector<sc_in<bool>> a, b, s, c;
    int n;
    SC_HAS_PROCESS(RippleObserver);
    RippleObserver(sc_module_name name, int width)
        : sc_module(name), a("a", width), b("b", width),
          s("s", width), c("c", width + 1), n(width) {
        SC_METHOD(sample);
        for (int i = 0; i < n; ++i) sensitive << a[i] << b[i] << s[i] << c[i];
        sensitive << c[n];
    }
    void sample() {
        std::ostringstream out;
        out << ",\"bits\":[";
        for (int i = 0; i < n; ++i) {
            if (i) out << ',';
            out << '[' << a[i].read() << ',' << b[i].read() << ','
                << c[i].read() << ',' << s[i].read() << ',' << c[i+1].read() << ']';
        }
        event("ripple", out.str() + "]");
    }
};

inline void instruction_event(size_t pc, const std::string& op,
                              const std::array<uint32_t, 8>& regs) {
    std::ostringstream out;
    out << ",\"pc\":" << pc << ",\"op\":\"" << op << "\",\"registers\":[";
    for (size_t i = 0; i < regs.size(); ++i) {
        if (i) out << ',';
        out << regs[i];
    }
    event("instruction", out.str() + "]");
}

inline void transaction_event(bool write, uint32_t address, uint32_t value, sc_time delay) {
    std::ostringstream out;
    out << ",\"op\":\"" << (write ? "WRITE" : "READ") << "\",\"address\":"
        << address << ",\"value\":" << value << ",\"latency_ns\":" << delay.to_seconds()*1e9;
    event("transaction", out.str());
}
