from enum import Enum
import logging
import pymodbus3.client.sync
from nio.common.block.base import Block
from nio.common.block.controller import BlockStatus
from nio.common.signal.base import Signal
from nio.common.signal.status import BlockStatusSignal
from nio.common.discovery import Discoverable, DiscoverableType
from nio.metadata.properties import StringProperty, IntProperty, \
    ExpressionProperty, VersionProperty, SelectProperty, PropertyHolder
from nio.modules.threading import spawn, Event, Lock
from .mixins.retry.retry import Retry


class FunctionName(Enum):
    read_coils = 'read_coils'
    read_discrete_inputs = 'read_discrete_inputs'
    read_holding_registers = 'read_holding_registers'
    read_input_registers = 'read_input_registers'
    write_single_coil = 'write_coil'
    write_multiple_coils = 'write_coils'
    write_single_holding_register = 'write_register'
    write_multiple_holding_registers = 'write_registers'


@Discoverable(DiscoverableType.block)
class Modbus(Retry, Block):

    """ Communicate with a device using Modbus.

    Parameters:
        host (str): The host to connect to.
        port (int): The modbus port to connect to.
    """

    version = VersionProperty(version='0.1.1')
    host = StringProperty(title='Host', default='127.0.0.1')
    port = IntProperty(title='Port', visible=False)
    function_name = SelectProperty(FunctionName,
                                   title='Function Name',
                                   default=FunctionName.read_coils)
    address = ExpressionProperty(title='Starting Address', default='0')
    value = ExpressionProperty(title='Write Value(s)', default='{{ True }}')
    retry = IntProperty(title='Number of Retries before Error',
                        default=10,
                        visible=False)

    def __init__(self):
        super().__init__()
        self._client = None
        self._process_lock = Lock()
        self._retry_failed = False

    def configure(self, context):
        super().configure(context)
        self.num_retries = self.retry
        # We don't need pymodbus3 to log for us. The block will handle that.
        logging.getLogger('pymodbus3').setLevel(logging.CRITICAL)
        self._connect()

    def process_signals(self, signals, input_id='default'):
        output = []
        for signal in signals:
            if self._retry_failed:
                self._logger.info(
                    "Skipping signal since block is now in error")
                return
            else:
                with self._process_lock:
                    output_signal = self._process_signal(signal)
                    if output_signal:
                        output.append(output_signal)
        if output:
            self.notify_signals(output)

    def _process_signal(self, signal):
        modbus_function = self.function_name.value
        address = self._address(signal)
        params = self._prepare_params(modbus_function, signal)
        params['address'] = address
        if modbus_function is None or address is None or params is None:
            # A warning method has already been logged if we get here
            return
        try:
            return self._execute_with_retry(
                self._execute, modbus_function=modbus_function, params=params)
        except:
            # Execution failed even with retry
            self._logger.exception(
                "Aborting retry and putting block in ERROR")
            status_signal = BlockStatusSignal(
                BlockStatus.error, 'Out of retries.')
            self.notify_management_signal(status_signal)
            self._retry_failed = True

    def stop(self):
        self._client.close()
        super().stop()

    def _connect(self):
        self._logger.debug('Connecting to modbus')
        self._client = pymodbus3.client.sync.ModbusTcpClient(self.host)
        self._logger.debug('Succesfully connected to modbus')

    def _execute(self, modbus_function, params):
        self._logger.debug("Waiting for lock to execute Modbus function '{}' "
                           'with params: {}'
                           .format(modbus_function, params))
        result = getattr(self._client, modbus_function)(**params)
        self._logger.debug('Modbus function returned: {}'.format(result))
        if result:
            signal = Signal(result.__dict__)
            signal.params = params
            self._check_exceptions(signal)
            return signal

    def _before_retry(self, retry_count, **kwargs):
        do_retry = super()._before_retry(retry_count, **kwargs)
        if do_retry:
            self._connect()
        return do_retry

    def _address(self, signal):
        try:
            return int(self.address(signal))
        except:
            self._logger.warning('Address needs to evaluate to an integer',
                                 exc_info=True)

    def _prepare_params(self, modbus_function, signal):
        try:
            if modbus_function in ['write_coil', 'write_register']:
                return {'value': self.value(signal)}
            elif modbus_function in ['write_coils', 'write_registers']:
                return {'values': self.value(signal)}
            else:
                return {}
        except:
            self._logger.warning('Failed to prepare function params',
                                 exc_info=True)

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
