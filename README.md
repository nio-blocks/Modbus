ModbusRTU
=========
Communicate with a Modbus device over RTU Serial.

Properties
----------
- **address**: The starting address to read from or write to.
- **count**: The number of coils/discretes/registers to read.
- **function_name**: Modbus function call to execute.
- **port_config**: The modbus port to connect to (default 502). If left blank, the default pymodbus3 value will be used.
- **retry**: How many times to retry connection on failure.
- **retry_options**: Configurables for retry attempts.
- **slave_address**: Slave address of modbus device.
- **value**: The value to write to the specified address.

Inputs
------
- **default**: Drive reads and writes with input signals.

Outputs
-------
- **default**: Notifies a signal for each frame read from Modbus.

Commands
--------
None

Dependencies
------------
-   [minimalmodbus](https://pypi.python.org/pypi/MinimalModbus)
-   [pymodbus](https://pypi.org/project/pymodbus/1.3.1/)

***

ModbusTCP
=========
Communicate with a device using Modbus TCP.

Properties
----------
- **address**: The starting address to read from or write to.
- **count**: Number of coils/registers to read
- **enrich**: If true, the incoming signal will be attached to the output signal.
- **function_name**: Modbus function call to execute.
- **host**: The host to connect to.
- **port**: The port to connect to.
- **retry**: How many times to retry connection on failure.
- **retry_options**: Configurables for retry attempts.
- **unit_id**: ID of modbus unit
- **value**: The value to write to the specified address.

Inputs
------
- **default**: Drive reads and writes with input signals.

Outputs
-------
- **default**: Notifies a signal for each frame read from Modbus.

Commands
--------
None

Output Example
--------------
Attributes on signals include (but are not limited to) the following:
  - `params`: Dictionary of parameters passed to function call.
    - `register_address`: Starting address.
    - `function_code`: Modbus function code.
    - `value` (optional): Value on write.
  - `values` (optional): List of int values when reading registers.
  - `exception_code` (int, optional): Error code when function call is invalid.
  - `exception_details` (str, optional): Error details when function call is invalid.

