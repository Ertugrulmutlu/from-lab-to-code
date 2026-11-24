#include "Adder.h"
#include "Monitor.h"

int sc_main(int argc, char** argv) {
    sc_signal<int> a("a"), b("b"), sum("sum");
    Adder dut("adder");
    dut.a(a);
    dut.b(b);
    dut.sum(sum);

    Monitor mon("monitor");
    mon.a(a);
    mon.b(b);
    mon.sum(sum);

    auto* trace = trace_start();
    sc_trace(trace, a, "A");
    sc_trace(trace, b, "B");
    sc_trace(trace, sum, "SUM");

    int A = arg(argc, argv, 1, 7);
    int B = arg(argc, argv, 2, 5);
    sc_start(5, SC_NS);
    a.write(A);
    b.write(B);
    sc_start(10, SC_NS);

    sc_close_vcd_trace_file(trace);
    return sum.read() == A + B ? 0 : 1;
}
