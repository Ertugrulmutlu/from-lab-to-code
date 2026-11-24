#include "Ripple.h"
#include "observations.hpp"

int sc_main(int argc, char** argv) {
    int n = arg(argc, argv, 4, 4);
    if (n != 4 && n != 8 && n != 16 && n != 32) return 2;
    auto A = argc > 1 ? std::stoull(argv[1]) : 7ULL;
    auto B = argc > 2 ? std::stoull(argv[2]) : 5ULL;
    bool C = arg(argc, argv, 3, 0) & 1;

    sc_vector<sc_signal<bool>> a("a", n), b("b", n), s("s", n);
    Ripple dut("ripple", n);
    RippleObserver m("monitor", n);
    auto* trace = trace_start();

    for (int i = 0; i < n; ++i) {
        dut.a[i](a[i]);
        dut.b[i](b[i]);
        dut.sum[i](s[i]);
        m.a[i](a[i]); m.b[i](b[i]); m.s[i](s[i]);
        sc_trace(trace, a[i], "A" + std::to_string(i));
        sc_trace(trace, b[i], "B" + std::to_string(i));
        sc_trace(trace, s[i], "S" + std::to_string(i));
    }
    for (int i = 0; i <= n; ++i) {
        m.c[i](dut.carry[i]);
        sc_trace(trace, dut.carry[i], "C" + std::to_string(i));
    }

    sc_start(5, SC_NS);
    for (int i = 0; i < n; ++i) {
        a[i].write((A >> i) & 1);
        b[i].write((B >> i) & 1);
    }
    dut.carry[0].write(C);
    sc_start(10, SC_NS);

    // Read the N sum bits and the final carry as a number.
    unsigned long long actual = 0;
    for (int i = 0; i < n; ++i)
        if (s[i].read()) actual |= 1ULL << i;
    if (dut.carry[n].read()) actual |= 1ULL << n;
    auto mask = (1ULL << n) - 1;
    auto expected = (A & mask) + (B & mask) + C;
    std::cout << "[test] actual=" << actual << " expected=" << expected << '\n';
    sc_close_vcd_trace_file(trace);
    return actual == expected ? 0 : 1;
}
