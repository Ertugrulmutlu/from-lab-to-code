#include "Ripple.h"

Ripple::Ripple(sc_module_name name, int n)
    : sc_module(name), a("a", n), b("b", n), sum("sum", n),
      carry("carry", n + 1), cells("FA", n) {
    // Connect each full adder to the next via its carry signal.
    for (int i = 0; i < n; ++i) {
        cells[i].a(a[i]);
        cells[i].b(b[i]);
        cells[i].cin(carry[i]);
        cells[i].sum(sum[i]);
        cells[i].cout(carry[i + 1]);
    }
}
