#include "FullAdder.h"
#include "Monitor.h"

int sc_main(int argc, char** argv) {
    sc_signal<bool> a("a"), b("b"), cin("cin"), sum("sum"), cout("cout");
    FullAdder dut("full_adder");
    dut.a(a);
    dut.b(b);
    dut.cin(cin);
    dut.sum(sum);
    dut.cout(cout);

    Monitor m("monitor");
    m.a(a); m.b(b); m.cin(cin);
    m.sum(sum); m.cout(cout);
    m.x(dut.x); m.ab(dut.ab); m.xc(dut.xc);

    auto* trace = trace_start();
    sc_trace(trace, a, "A");
    sc_trace(trace, b, "B");
    sc_trace(trace, cin, "Cin");
    sc_trace(trace, sum, "Sum");
    sc_trace(trace, cout, "Cout");
    sc_trace(trace, dut.x, "X");
    sc_trace(trace, dut.ab, "AB");
    sc_trace(trace, dut.xc, "XC");

    sc_start(5, SC_NS);
    for (int A = 0; A <= 1; ++A) {
        for (int B = 0; B <= 1; ++B) {
            for (int C = 0; C <= 1; ++C) {
                a.write(A); b.write(B); cin.write(C);
                sc_start(10, SC_NS);
                if (sum.read() + 2 * cout.read() != A + B + C) {
                    std::cerr << "Truth table failed\n";
                    sc_close_vcd_trace_file(trace);
                    return 1;
                }
            }
        }
    }

    // Display the user's selected combination at the end.
    a.write(arg(argc, argv, 1, 1) & 1);
    b.write(arg(argc, argv, 2, 1) & 1);
    cin.write(arg(argc, argv, 3, 0) & 1);
    sc_start(10, SC_NS);
    std::cout << "[test] All 8 combinations passed\n";
    sc_close_vcd_trace_file(trace);
    return 0;
}
