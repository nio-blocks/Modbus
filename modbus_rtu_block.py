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
        self._modbus_function = None

    def configure(self, context):
        super().configure(context)
        self._connect()
        self._modbus_function = \
            self._function_name_from_code(self.function_name.value)

    def process_signals(self, signals, input_id='default'):
        output = []
        for signal in signals:
            try:
                params = self._prepare_params(signal)
                response = self._execute(params)
                if response:
                    output.append(self._process_response(response, params))
            except:
                self._logger.exception(
                    'Failed to process signal: {}'.format(signal))
        if output:
            self.notify_signals(output)

    def _connect(self):
        self._logger.debug('Connecting to modbus')
        self._client = minimalmodbus.Instrument(self.port, self.slave_address)
        self._logger.debug('Succesfully connected to modbus')

    def _execute(self, params, retry=False):
        self._logger.debug('Executing Modbus function \'{}\' with params: {}, '
                           'is_retry: {}'
                           .format(self._modbus_function, params, retry))
        try:
            with self._execute_lock:
                return self._locked_execute(params)
        except:
            if not retry:
                self._logger.exception('Failed to execute Modbus function. '
                                       'Reconnecting and retyring one time.')
                self._connect()
                return self._execute(params, True)
            else:
                self._logger.exception('During retry, failed to execute '
                                       'Modbus function. Aborting execution.')

    def _locked_execute(self, params):
        self._logger.debug('Modbus function \'{}\' with params: {} has lock'
                           .format(self._modbus_function, params))
        response = getattr(self._client, self._modbus_function)(**params)
        self._logger.debug('Modbus function returned: {}'.format(response))
        return response

    def _function_name_from_code(self, code):
        return {
            1: 'read_bit',
            2: 'read_bit',
            5: 'write_bit',
            15: 'write_bit',
            3: 'read_registers',
            4: 'read_registers',
            6: 'write_register',
            16: 'write_registers'
        }.get(code)

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
        signal = Signal({
            'values': response,
            'params': params
        })
        return signal

    def _address(self, signal):
        try:
            return int(self.address(signal))
        except:
            self._logger.warning('Address needs to evaluate to an integer',
                                 exc_info=True)