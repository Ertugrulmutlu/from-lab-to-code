#include "Memory.h"

Memory::Memory(sc_module_name name, int delay)
    : sc_module(name), socket("target"), latency(delay) {
    socket.register_b_transport(this, &Memory::transport);
}

void Memory::transport(tlm_generic_payload& p, sc_time& delay) {
    auto address = p.get_address();
    auto* bytes = p.get_data_ptr();

    // Only aligned 4-byte accesses are supported.
    if (!bytes || address > 252 || address % 4 || p.get_data_length() != 4) {
        p.set_response_status(TLM_ADDRESS_ERROR_RESPONSE);
        return;
    }
    if (p.get_byte_enable_ptr() || p.get_streaming_width() < 4) {
        p.set_response_status(TLM_GENERIC_ERROR_RESPONSE);
        return;
    }

    if (p.is_write()) {
        std::memcpy(data.data() + address, bytes, 4);
    } else if (p.is_read()) {
        std::memcpy(bytes, data.data() + address, 4);
    } else {
        p.set_response_status(TLM_COMMAND_ERROR_RESPONSE);
        return;
    }
    delay += sc_time(latency, SC_NS);
    p.set_response_status(TLM_OK_RESPONSE);
}
