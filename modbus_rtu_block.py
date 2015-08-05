from enum import Enum
import minimalmodbus
from nio.common.block.base import Block
from nio.common.signal.base import Signal
from nio.common.discovery import Discoverable, DiscoverableType
from nio.metadata.properties import StringProperty, IntProperty, \
    ExpressionProperty, VersionProperty, SelectProperty, PropertyHolder
from nio.modules.threading import spawn, Event, Lock


class FunctionName(Enum):
    read_coils = 1
    read_discrete_inputs = 2
    read_holding_registers = 3
    read_input_registers = 4
    write_single_coil = 5
    write_multiple_coils = 15
    write_single_holding_register = 6
    write_multiple_holding_registers = 16


@Discoverable(DiscoverableType.block)
class ModbusRTU(Block):

    """ Communicate with a device using Modbus over RTU.

    Parameters:
        host (str): The host to connect to.
        port (int): The modbus port to connect to.
    """

    version = VersionProperty(version='0.1.1')
    port = StringProperty(title='Serial Port', default='/dev/ttyUSB0')
    slave_address = IntProperty(title='Slave Address', default=1)
    function_name = SelectProperty(FunctionName,
                                   title='Function Name',
                                   default=FunctionName.read_input_registers)
    address = ExpressionProperty(title='Starting Address', default='0')
    number_of_address = IntProperty(title='Number of coils/registers to read',
                                    default=1)
    value = ExpressionProperty(title='Write Value(s)', default='{{ True }}')

    def __init__(self):
        super().__init__()
        self._client = None
        self._execute_lock = Lock()

    def configure(self, context):
        super().configure(context)
        self._connect()

    def process_signals(self, signals, input_id='default'):
        output = []
        for signal in signals:
            modbus_function = self._modbus_function()
            params = self._prepare_params(signal)
            if modbus_function is None or params is None:
                # A warning method has already been logged if we get here
                continue
            output_signal = self._execute(modbus_function, params)
            if output_signal:
                output.append(output_signal)
        if output:
            self.notify_signals(output)

    def _connect(self):
        self._logger.debug('Connecting to modbus')
        self._client = minimalmodbus.Instrument(self.port, self.slave_address)
        self._logger.debug('Succesfully connected to modbus')

    def _execute(self, modbus_function, params, retry=False):
        self._logger.debug('Executing Modbus function \'{}\' with params: {}, '
                           'is_retry: {}'
                           .format(modbus_function, params, retry))
        try:
            with self._execute_lock:
                self._logger.debug(
                    'Executing Modbus function \'{}\' with params: {}'
                    .format(modbus_function, params))
                result = getattr(self._client, modbus_function)(**params)
                self._logger.debug('Modbus function returned: {}'.format(result))
            if result:
                signal = Signal({'values': result})
                signal.params = params
                self._check_exceptions(signal)
                return signal
        except:
            if not retry:
                self._logger.exception('Failed to execute Modbus function. '
                                       'Reconnecting and retyring one time.')
                self._connect()
                return self._execute(modbus_function, params, True)
            else:
                self._logger.exception('During retry, failed to execute '
                                       'Modbus function. Aborting execution.')

    def _prepare_params(self, signal):
        try:
            if self.function_name.value in [4]:
                params = {'functioncode': 4,
                          'numberOfRegisters': self.number_of_address}
            else:
                params = {}
            address = self._address(signal)
            params['registeraddress'] = address
            return params
        except:
            self._logger.warning('Failed to prepare function params',
                                 exc_info=True)

    def _modbus_function(self):
        if self.function_name.value == 2:
            return 'read_registers'
        elif self.function_name.value == 4:
            return 'read_registers'

    def _check_exceptions(self, signal):
        ''' Add exception details if the response has an exception code '''
        code = getattr(signal, 'exception_code', None)
        desc = None
        if code and isinstance(code, int):
            if code == 1:
                desc = 'Function code received in the query is not recognized or allowed by slave'
            elif code == 2:
                desc = 'Data address of some or all the required entities are not allowed or do not exist in slave'
            elif code == 3:
                desc = 'Value is not accepted by slave'
            elif code == 4:
                desc = 'Unrecoverable error occurred while slave was attempting to perform requested action'
            elif code == 5:
                desc = 'Slave has accepted request and is processing it, but a long duration of time is required. This response is returned to prevent a timeout error from occurring in the master. Master can next issue a Poll Program Complete message to determine if processing is completed'
            elif code == 6:
                desc = 'Slave is engaged in processing a long-duration command. Master should retry later'
            elif code == 7:
                desc = 'Slave cannot perform the programming functions. Master should request diagnostic or error information from slave'
            elif code == 8:
                desc = 'Slave detected a parity error in memory. Master can retry the request, but service may be required on the slave device'
            elif code == 10:
                desc = 'Specialized for Modbus gateways. Indicates a misconfigured gateway'
            elif code == 11:
                desc = 'Specialized for Modbus gateways. Sent when slave fails to respond'
        if desc:
            signal.exception_details = desc

    def _address(self, signal):
        try:
            return int(self.address(signal))
        except:
            self._logger.warning('Address needs to evaluate to an integer',
                                 exc_info=True)
