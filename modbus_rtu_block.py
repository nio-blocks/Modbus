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
        slave_address (str): Slave address of modbus device.
        port (str): Serial port modbus device is connected to.
    """

    version = VersionProperty(version='0.1.0')
    port = StringProperty(title='Serial Port', default='/dev/ttyUSB0')
    slave_address = IntProperty(title='Slave Address', default=1)
    function_name = SelectProperty(FunctionName,
                                   title='Function Name',
                                   default=FunctionName.read_input_registers)
    address = ExpressionProperty(title='Starting Address', default='0')
    count = IntProperty(title='Number of coils/registers to read',
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
            try:
                modbus_function = self._modbus_function()
                params = self._prepare_params(signal)
                response = self._execute(modbus_function, params)
                output_signal = self._process_response(response, params)
                if output_signal:
                    output.append(output_signal)
            except:
                self._logger.exception(
                    'Failed to process signal: {}'.format(signal))
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
                    'Modbus function \'{}\' with params: {} has lock'
                    .format(modbus_function, params))
                response = getattr(self._client, modbus_function)(**params)
                self._logger.debug(
                    'Modbus function returned: {}'.format(response))
                return response
        except:
            if not retry:
                self._logger.exception('Failed to execute Modbus function. '
                                       'Reconnecting and retyring one time.')
                self._connect()
                return self._execute(modbus_function, params, True)
            else:
                self._logger.exception('During retry, failed to execute '
                                       'Modbus function. Aborting execution.')

    def _modbus_function(self):
        if self.function_name.value in [1, 2]:
            return 'read_bit'
        elif self.function_name.value in [5, 15]:
            return 'write_bit'
        elif self.function_name.value in [3, 4]:
            return 'read_registers'
        elif self.function_name.value in [6]:
            return 'write_register'
        elif self.function_name.value in [16]:
            return 'write_registers'

    def _prepare_params(self, signal):
        params = {}
        params['functioncode'] = self.function_name.value
        params['registeraddress'] = self._address(signal)
        if self.function_name.value in [3, 4]:
            params['numberOfRegisters'] = self.count
        elif self.function_name.value in [5, 6, 15, 16]:
            try:
                params['value'] = self.value(signal)
            except:
                raise Exception('Invalid configuration of `value` property')
        return params

    def _process_response(self, response, params):
        if response:
            signal = Signal({'values': response})
            signal.params = params
            self._check_exceptions(signal)
            return signal

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
