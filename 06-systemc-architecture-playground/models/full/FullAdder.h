#pragma once
#include "lab.hpp"

SC_MODULE(FullAdder) {
    sc_in<bool> a, b, cin;
    sc_out<bool> sum, cout;
    sc_signal<bool> x{"x"}, ab{"ab"}, xc{"xc"};

    SC_CTOR(FullAdder) {
        SC_METHOD(stage1);
        sensitive << a << b;
        SC_METHOD(stage2);
        sensitive << x << cin;
        SC_METHOD(stage3);
        sensitive << ab << xc;
    }

    void stage1();
    void stage2();
    void stage3();
};
