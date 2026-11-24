# Independent educational ISA. R0-R7, unsigned 32-bit registers.
# Fibonacci(10): result 55 in R0 and memory address 0.
MOVI R0 0
MOVI R1 1
MOVI R2 10
loop:
ADD R3 R0 R1
MOV R0 R1
MOV R1 R3
ADDI R2 R2 -1
JNZ R2 loop
STORE R0 0
LOAD R4 0
HALT
