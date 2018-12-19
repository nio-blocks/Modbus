ModbusRTU
=========
Communicate with a Modbus/RTU device over serial. This block will open a comm port on the host machine (configurable parameters) and send a request for every signal processed. Responses will be emitted as signals containing the raw register values as a list of 16-bit integers or bits (booleans).

See also: The [*Replicator*](https://blocks.n.io/Replicator) block is useful for putting each register into its own signal.

Properties
----------
- **Slave Address**: Bus address of target slave device. Valid Modbus address are 1 thru 247, or 0 for broadcast.
- **Function Name**: Select one of the standard Modbus functions.
- **Starting Address**: Starting register number to read or write. Address offsets are handled by the selected **Function Name**. For example, if selecting the function *Read Holding Registers* the register address `0` corresponds to register `40001` in the target device.
- **Number of coils/registers to read**: How many values to read in total, including the **Starting Address**. The outgoing signal will contain this many values in a list. Not used when writing values.
- **Write Values(s)**: A list of values to write to the target device. Each value will be written to a consecutive register or coil starting from **Starting Address**. The number of values to write is the length of the list. Not used when reading values.
- **Timeout**: (Advanced) Seconds to wait for a response before failing and executing **Retry Options** configuration.
- **Port Config**: (Advanced) Serial configurations here must be compatible with the target device. The value of **Serial Port** depends on the host operating system, in Windows this is often something like `COM1`, and in POSIX-based systems `/dev/ttyS0` or similar.

Commands
--------
None
