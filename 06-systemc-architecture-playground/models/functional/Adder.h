#pragma once
#include "lab.hpp"

SC_MODULE(Adder) {
    sc_in<int> a, b;
    sc_out<int> sum;

    SC_CTOR(Adder) {
        SC_METHOD(compute);
        sensitive << a << b;
    }

    void compute();
};
