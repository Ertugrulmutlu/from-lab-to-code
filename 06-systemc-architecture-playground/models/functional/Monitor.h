#pragma once
#include "observations.hpp"

SC_MODULE(Monitor) {
    sc_in<int> a, b, sum;

    void sample() {
        signals({{"a", a.read()}, {"b", b.read()}, {"sum", sum.read()}});
    }

    SC_CTOR(Monitor) {
        SC_METHOD(sample);
        sensitive << a << b << sum;
    }
};
