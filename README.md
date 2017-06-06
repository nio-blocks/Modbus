Modbus
======

Communicate with a device using Modbus.

If a modbus function fails, retries will be attempted.

Properties
----------

-   **host**: The host to connect to.
-   **port**: The modbus port to connect to (default 502). If left blank, the default pymodbus3 value will be used.
-   **function_name**: Modbus function call to execute.
-   **address**: The starting address to read from or write to.
-   **value**: The value to write to the specified address.

Dependencies
------------

-   [pymodbus3](https://pypi.python.org/pypi/pymodbus3/1.0.0)

Commands
--------
None

Input
-----
Drive reads and writes with input signals.

Output
------

### default

Notifies a signal for each frame read from Modbus. Attributes on signals include (but are not limited to) the following:

  - `params`: Dictionary of parameters passed to function call.
    - `address`: Starting address.
    - `value` (optional): Value on single write.
    - `values` (optional): Values on multiple write.
  - `bits` (optional): List of boolean values when reading coils or discrete inputs.
  - `register`s (optional): List of int values when reading registers.
  - `exception_code` (int, optional): Error code when function call is invalid.
  - `exception_details` (str, optional): Error details when function call is invalid.

***

ModbusRTU
=========

Communicate with a Modbus device over RTU Serial.

If a modbus function fails, retries will be attempted.

Properties
----------
-   **Serial Port Setup**:
 -   **Serial Port**: COM Port to open
 -   **Baud Rate**: Default 19200
 -   **Timeout**: Default 0.05
 -   **Byte Size**: Default 8
 -   **Stop Bits**: Default 1
 -   **Parity**: Default None
-   **slave_address**: Slave address of modbus device.
-   **function_name**: Modbus function call to execute.
-   **address**: The starting address to read from or write to.
-   **value**: The value to write to the specified address.
-   **count**: The number of coils/discretes/registers to read.

Dependencies
------------

-   [minimalmodbus](https://pypi.python.org/pypi/MinimalModbus)

Commands
--------
None

Input
-----
Drive reads and writes with input signals.

Output
------

### default

Notifies a signal for each frame read from Modbus. Attributes on signals include (but are not limited to) the following:

  - `params`: Dictionary of parameters passed to function call.
    - `register_address`: Starting address.
    - `function_code`: Modbus function code.
    - `value` (optional): Value on write.
  - `values` (optional): List of int values when reading registers.
  - `exception_code` (int, optional): Error code when function call is invalid.
  - `exception_details` (str, optional): Error details when function call is invalid.
