import logging
import pymodbus.client.sync
from enum import Enum
from time import sleep

from nio.block.base import Block
from nio.properties import IntProperty, Property, VersionProperty, \
    SelectProperty, FloatProperty
from nio.block.mixins.limit_lock.limit_lock import LimitLock
from nio.block.mixins.retry.retry import Retry
from nio.block.mixins.enrich.enrich_signals import EnrichSignals


class FunctionName(Enum):
    read_coils = 'read_coils'
    read_discrete_inputs = 'read_discrete_inputs'
    read_holding_registers = 'read_holding_registers'
    read_input_registers = 'read_input_registers'
    write_single_coil = 'write_coil'
    write_multiple_coils = 'write_coils'
    write_single_holding_register = 'write_register'
    write_multiple_holding_registers = 'write_registers'


class ModbusTCP(LimitLock, EnrichSignals, Retry, Block):

    """ Communicate with a device using Modbus over TCP.

    Parameters:
        host (str): The host to connect to.
        port (int): The modbus port to connect to.
        timeout (float): Seconds to wait for a response before failing.
    """

    version = VersionProperty('1.0.0', order=100)
    host = Property(title='Host', default='127.0.0.1', order=10)
    port = IntProperty(title='Port', default=502, order=11)
    function_name = SelectProperty(FunctionName,
                                   title='Function Name',
                                   default=FunctionName.read_coils,
                                   order=13)
    address = IntProperty(title='Starting Address', default=0, order=14)
    value = Property(title='Write Value(s)', default='{{ True }}', order=16)
    count = IntProperty(title='Number of coils/registers to read',
                        default=1,
                        order=15)
    unit_id = IntProperty(title='Unit ID', default=1, order=12)
    timeout = FloatProperty(title='Timeout', default=1, advanced=True)

    def __init__(self):
        super().__init__()
        self._clients = {}

    def configure(self, context):
        super().configure(context)
        # We don't need pymodbus to log for us. The block will handle that.
        logging.getLogger('pymodbus').setLevel(logging.CRITICAL)
        # Make sure host is able to evaluate without a signal before connecting
        try:
            host = self.host()
            port = self.port()
        except:
            # host uses an expression so don't connect yet
            self.logger.debug(
                "Host is an expression that uses a signal so don't connect")
            host = None
            port = 0
        self._connect(host, port)

    def process_signals(self, signals):
        try:
            self.execute_with_lock(
                self._locked_process_signals, 5, signals=signals
            )
        except:
            # a warning has already been logged by LimitLock mixin
            pass

    def _locked_process_signals(self, signals):
        output = []
        for signal in signals:
            output_signal = self._process_signal(signal)
            if output_signal:
                output.append(output_signal)
        if output:
            self.notify_signals(output)

    def _process_signal(self, signal):
        modbus_function = self.function_name(signal).value
        params = self._prepare_params(modbus_function, signal)
        params['address'] = self.address(signal)
        params['unit'] = self.unit_id(signal)
        if modbus_function is None or \
                self.address(signal) is None or \
                params is None:
            # A warning method has already been logged if we get here
            return
        try:
            return self.execute_with_retry(
                self._execute,
                signal=signal,
                modbus_function=modbus_function,
                params=params)
        except:
            self.logger.exception(
                'Failed to execute on host: {}'.format(self.host(signal)))
            return self.get_output_signal({}, signal)

    def stop(self):
        for client in self._clients:
            self._clients[client].close()
        super().stop()

    def _connect(self, host=None, port=502):
        # If host is specifed connect to that, else reconnect to existing hosts
        if host:
            self._connect_to_host(host, port)
        else:
            for client in self._clients:
                host, port = client.split(":")
                self._connect_to_host(host, int(port))

    def _connect_to_host(self, host, port):
        self.logger.debug('Connecting to modbus host: {}'.format(host))
        client = pymodbus.client.sync.ModbusTcpClient(host,
                                                      port=port,
                                                      timeout=self.timeout())
        self._clients['{}:{}'.format(host,port)] = client
        self.logger.debug(
            'Succesfully connected to modbus host: {}'.format(host))

    def _client(self, host, port):
        if '{}:{}'.format(host,port) not in self._clients:
            self._connect(host, port)
        return self._clients['{}:{}'.format(host,port)]

    def _execute(self, signal, modbus_function, params):
        self.logger.debug(
            "Execute Modbus function '{}' with params: {}".format(
                modbus_function, params))
        result = getattr(self._client(self.host(signal), self.port(signal)),
                         modbus_function)(**params)
        self.logger.debug('Modbus function returned: {}'.format(result))
        if result:
            results = result.__dict__
            results["params"] = params
            signal = self.get_output_signal(results, signal)
            self._check_exceptions(signal)
            return signal

    def _prepare_params(self, modbus_function, signal):
        try:
            if modbus_function in ['write_coil', 'write_register']:
                return {'value': self.value(signal)}
            elif modbus_function in ['write_coils', 'write_registers']:
                return {'values': self.value(signal)}
            elif modbus_function.startswith('read'):
                return {'count': self.count(signal)}
            else:
                return {}
        except:
            self.logger.warning('Failed to prepare function params',
                                exc_info=True)

    def before_retry(self, *args, **kwargs):
        ''' Reconnect before making retry query. '''
        self._connect()

    def _check_exceptions(self, signal):
        ''' Add exception details if the response has an exception code '''
        code = getattr(signal, 'exception_code', None)
        desc = None
        if code and isinstance(code, int):
            if code == 1:
                desc = 'Function code received in the query is not ' \
                       'recognized or allowed by slave'
            elif code == 2:
                desc = 'Data address of some or all the required entities ' \
                       'are not allowed or do not exist in slave'
            elif code == 3:
                desc = 'Value is not accepted by slave'
            elif code == 4:
                desc = 'Unrecoverable error occurred while slave was ' \
                       'attempting to perform requested action'
            elif code == 5:
                desc = 'Slave has accepted request and is processing it, ' \
                       'but a long duration of time is required. ' \
                       'This response is returned to prevent a ' \
                       'timeout error from occurring in the master. ' \
                       'Master can next issue a Poll Program Complete ' \
                       'message to determine if processing is completed'
            elif code == 6:
                desc = 'Slave engaged in processing a long-duration command. '\
                       'Master should retry later'
            elif code == 7:
                desc = 'Slave cannot perform the programming functions. ' \
                       'Master should request diagnostic ' \
                       'or error information from slave'
            elif code == 8:
                desc = 'Slave detected a parity error in memory. ' \
                       'Master can retry the request, ' \
                       'but service may be required on the slave device'
            elif code == 10:
                desc = 'Specialized for Modbus gateways. ' \
                       'Indicates a misconfigured gateway'
            elif code == 11:
                desc = 'Specialized for Modbus gateways. ' \
                       'Sent when slave fails to respond'
        if desc:
            signal.exception_details = desc
