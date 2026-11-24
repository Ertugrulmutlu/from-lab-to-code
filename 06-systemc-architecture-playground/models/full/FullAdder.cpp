#include "FullAdder.h"

// First half adder.
void FullAdder::stage1() {
    x.write(a.read() ^ b.read());
    ab.write(a.read() && b.read());
}

// Second half adder: include the carry input.
void FullAdder::stage2() {
    sum.write(x.read() ^ cin.read());
    xc.write(x.read() && cin.read());
}

// Combine the two carry outputs.
void FullAdder::stage3() {
    cout.write(ab.read() || xc.read());
}
