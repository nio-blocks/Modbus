ModbusTCP
=========
Communicate with a Modbus/TCP device. This block will manage connections to slave devices and send a request for every signal processed. Responses will be emitted as signals containing the raw register values as a list of 16-bit integers or bits (booleans).

See also: The [*Replicator*](https://blocks.n.io/Replicator) block is useful for putting each register into its own signal.

Properties
----------
- **Host**: Host address of slave device.
- **Port**: TCP port of slave device.
- **Unit ID**: Unit ID of slave, defaults to 1.
- **Function Name**: Select one of the standard Modbus functions.
- **Starting Address**: Starting register number to read or write. Address offsets are handled by the selected **Function Name**. For example, if selecting the function *Read Holding Registers* the register address `0` corresponds to register `40001` in the target device.
- **Number of coils/registers to read**: How many values to read in total, including the **Starting Address**. The outgoing signal will contain this many values in a list. Not used when writing values.
- **Write Values(s)**: A list of values to write to the target device. Each value will be written to a consecutive register or coil starting from **Starting Address**. The number of values to write is the length of the list. Not used when reading values.
- **Timeout**: (Advanced) Seconds to wait for a response before failing and executing **Retry Options** configuration.

Example
---
Attributes on outgoing signals include (but are not limited to) the following:
  - `params`: Dictionary of parameters passed to function call.
    - `register_address`: Starting address.
    - `function_code`: Modbus function code.
    - `value` (optional): Value on write.
  - `values` (optional): List of int values when reading coils.
  - `registers` (optional): list of 16-bit integer values when reading registers.
  - `exception_code` (int, optional): Error code when function call is invalid.
  - `exception_details` (str, optional): Error details when function call is invalid.

Commands
--------
None
