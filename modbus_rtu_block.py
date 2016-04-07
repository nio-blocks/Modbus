from enum import Enum
import minimalmodbus
from nio.block.base import Block
from nio.common.block.controller import BlockStatus
from nio.signal.base import Signal
from nio.common.signal.status import BlockStatusSignal
from nio.util.discovery import discoverable
from nio.properties import StringProperty, IntProperty, \
    Property, VersionProperty, SelectProperty, PropertyHolder
from nio.util.threading.spawn import spawn, Event, Lock, sleep
from nio.block.mixins.retry.retry import Retry


class FunctionName(Enum):
    read_coils = 1
    read_discrete_inputs = 2
    read_holding_registers = 3
    read_input_registers = 4
    write_single_coil = 5
    write_multiple_coils = 15
    write_single_holding_register = 6
    write_multiple_holding_registers = 16


@discoverable
class ModbusRTU(Retry, Block):

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
    address = Property(title='Starting Address', default='0')
    count = IntProperty(title='Number of coils/registers to read',
                        default=1)
    value = Property(title='Write Value(s)', default='{{ True }}')
    retry = IntProperty(title='Number of Retries before Error',
                        default=10,
                        visible=False)

    def __init__(self):
        super().__init__()
        self._client = None
        self._process_lock = Lock()
        self._modbus_function = None
        self._retry_failed = False
        self._num_locks = 0
        self._max_locks = 5

    def configure(self, context):
        super().configure(context)
        self._connect()
        self.num_retries = self.retry
        self._modbus_function = \
            self._function_name_from_code(self.function_name.value)

    def process_signals(self, signals, input_id='default'):
        output = []
        for signal in signals:
            if self._num_locks >= self._max_locks:
                self.logger.debug(
                    "Skipping signal; max numbers of signals waiting")
                continue
            self._num_locks += 1
            with self._process_lock:
                if self._retry_failed:
                    self.logger.debug(
                        "Skipping signal since block is now in error")
                    return
                else:
                    output_signal = self._process_signal(signal)
                    if output_signal:
                        output.append(output_signal)
            self._num_locks -= 1
        if output:
            self.notify_signals(output)

    def _process_signal(self, signal):
        try:
            params = self._prepare_params(signal)
            return self._execute_with_retry(self._execute, params=params)
        except:
            # Execution failed even with retry
            # Note: this should never happen because retries go forever
            self.logger.exception(
                "Aborting retry and putting block in ERROR")
            status_signal = BlockStatusSignal(
                BlockStatus.error, 'Out of retries.')
            self.notify_management_signal(status_signal)
            self._retry_failed = True

    def _connect(self):
        self.logger.debug('Connecting to modbus')
        self._client = minimalmodbus.Instrument(self.port, self.slave_address)
        self.logger.debug('Succesfully connected to modbus')

    def _execute(self, params, retry=False):
        self.logger.debug('Executing Modbus function \'{}\' with params: {}, '
                           'is_retry: {}'
                           .format(self._modbus_function, params, retry))
        response = getattr(self._client, self._modbus_function)(**params)
        self.logger.debug('Modbus function returned: {}'.format(response))
        return self._process_response(response, params)

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
        if not response:
            return
        signal = Signal({
            'values': response,
            'params': params
        })
        return signal

    def _before_retry(self, retry_count, **kwargs):
        if retry_count >= self.num_retries:
            time_before_retry = 60
            self.logger.error(
                "Modbus function continues to fail; retrying in 60 seconds")
        else:
            time_before_retry = retry_count
        self.logger.debug(
            "Waiting {} seconds before retrying execute method".format(
                time_before_retry))
        sleep(time_before_retry)
        self._connect()
        # Return True to confirm that we should retry
        return True

    def _address(self, signal):
        try:
            return int(self.address(signal))
        except:
            self.logger.warning('Address needs to evaluate to an integer',
                                 exc_info=True)
