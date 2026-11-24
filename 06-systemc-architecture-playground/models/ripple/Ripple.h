#pragma once
#include "FullAdder.h"

SC_MODULE(Ripple) {
    sc_vector<sc_in<bool>> a, b;
    sc_vector<sc_out<bool>> sum;
    sc_vector<sc_signal<bool>> carry;
    sc_vector<FullAdder> cells;

    Ripple(sc_module_name name, int n);
};
