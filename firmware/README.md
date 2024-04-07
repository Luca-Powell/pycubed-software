# Firmware 🔧
Low-level code implementing CircuitPython (port of Micropython)

# Bootloader
Built from [Adafruit's fork of the Microsoft UF2 SAMD bootloader](https://github.com/adafruit/uf2-samdx1)

Build used for the project: CircuitPython 8.2.10 (Uploaded on 2024-03-05 📅)
   - [CircuitPython port](https://github.com/adafruit/circuitpython/tree/main/ports/atmel-samd/boards/pycubed)
   - built with `gcc-arm-none-eabi-10-2020-q4-major`

Using the SAMD51Jxx, there are now separate bootloaders `J20` and `J19` for each chipset. Make sure to use the correct one!

If you can access bootloader mode (double-click reset button), you can copy over the respective `update-bootloader` UF2 to update the bootloader without having to use JTAG. If your SAMD51Jxx is brand-new, you will need to first flash the bootloader (more details [here](https://pycubed.org/maholli/Programming-the-Bootloader-343b47d1ad6f4863b512d6464aa7b84e)).
<br>
<br>
## [All PyCubed Resources](https://www.notion.so/maholli/All-PyCubed-Resources-8738cab0dd0743239a3cde30c6066452)
Tutorials, design resources, and more!
<br>
<br>
<br>

## License
- Software/firmware in this repository is licensed under MIT unless otherwise indicated.