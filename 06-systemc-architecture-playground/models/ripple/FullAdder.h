#pragma once
#include "lab.hpp"

SC_MODULE(FullAdder) {
    sc_in<bool> a, b, cin;
    sc_out<bool> sum, cout;

    SC_CTOR(FullAdder) {
        SC_METHOD(compute);
        sensitive << a << b << cin;
    }

    void compute();
};
