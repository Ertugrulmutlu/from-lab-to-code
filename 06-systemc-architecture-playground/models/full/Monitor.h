#pragma once
#include "observations.hpp"

SC_MODULE(Monitor) {
    sc_in<bool> a, b, cin, sum, cout, x, ab, xc;

    void sample() {
        signals({
            {"a", a.read()}, {"b", b.read()}, {"cin", cin.read()},
            {"sum", sum.read()}, {"cout", cout.read()},
            {"x", x.read()}, {"ab", ab.read()}, {"xc", xc.read()}
        });
    }

    SC_CTOR(Monitor) {
        SC_METHOD(sample);
        sensitive << a << b << cin << sum << cout << x << ab << xc;
    }
};
