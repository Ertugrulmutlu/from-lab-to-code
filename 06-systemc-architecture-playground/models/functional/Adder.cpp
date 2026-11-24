#include "Adder.h"

void Adder::compute() {
    sum.write(a.read() + b.read());
}
