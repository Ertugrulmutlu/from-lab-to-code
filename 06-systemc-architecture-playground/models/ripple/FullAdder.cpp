#include "FullAdder.h"

void FullAdder::compute() {
    bool x = a.read() ^ b.read();
    sum.write(x ^ cin.read());
    cout.write((a.read() && b.read()) || (x && cin.read()));
}
