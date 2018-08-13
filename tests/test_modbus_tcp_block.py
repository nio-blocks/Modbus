from threading import Event
from unittest import skipUnless
from unittest.mock import patch, MagicMock
from time import sleep

from nio.block.terminals import DEFAULT_TERMINAL
from nio.testing.block_test_case import NIOBlockTestCase
from nio.signal.base import Signal
from nio.util.threading import spawn

pymodbus3_available = True
try:
    import pymodbus3
except ImportError:
    pymodbus3_available = False

try:
    from ..modbus_tcp_block import ModbusTCP
except Exception as e:
    print('Error importing ModbusTCP block: {}'.format(e))
    pass


class SampleResponse():

    def __init__(self, value='default'):
        self.value = value


@skipUnless(pymodbus3_available, 'pymodbus3 is not available!!')
class TestModbusTCP(NIOBlockTestCase):

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_defaults(self, mock_client):
        ''' Test that read_coils is called with default configuration '''
        blk = ModbusTCP()
        self.configure_block(blk, {})
        self.assertEqual(mock_client.call_count, 1)
        # Simulate some response from the modbus read
        blk._client(blk.host()).read_coils.return_value = SampleResponse()
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal()])
        blk._client(blk.host()).read_coils.assert_called_once_with(
            address=0, count=1, unit=1)
        self.assertTrue(len(self.last_notified[DEFAULT_TERMINAL]))
        self.assertEqual(
            self.last_notified[DEFAULT_TERMINAL][0].value, 'default')
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_enrich_signals_mixin(self, mock_client):
        ''' Test that read_coils is called with default configuration '''
        blk = ModbusTCP()
        self.configure_block(blk, {"enrich": {"exclude_existing": False}})
        self.assertEqual(mock_client.call_count, 1)
        # Simulate some response from the modbus read
        blk._client(blk.host()).read_coils.return_value = SampleResponse()
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal({"input": "signal"})])
        blk._client(blk.host()).read_coils.assert_called_once_with(
            address=0, count=1, unit=1)
        self.assertTrue(len(self.last_notified[DEFAULT_TERMINAL]))
        self.assertDictEqual(
            self.last_notified[DEFAULT_TERMINAL][0].to_dict(), {
                "params": {"address": 0, "count": 1, "unit": 1},
                "value": "default",
                "input": "signal",
            })
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_multiple_hosts(self, mock_client):
        ''' Test that read_coils is called for each client'''
        blk = ModbusTCP()
        self.configure_block(blk, {"host": "{{ $host }}"})
        # Initial client connect is skipped since host relies on signal
        self.assertEqual(mock_client.call_count, 0)
        # Simulate some response from the modbus read
        mock_client.return_value.read_coils.side_effect = \
            [SampleResponse("1"), SampleResponse("2")]
        blk.start()
        self.assertEqual(mock_client.call_count, 0)
        # Connect and read from first client
        signal1 = Signal({"host": "host1"})
        blk.process_signals([signal1])
        blk._client(blk.host(signal1)).read_coils.assert_called_once_with(
            address=0, count=1, unit=1)
        self.assertEqual(mock_client.call_count, 1)
        # Connect and read from second client
        signal2 = Signal({"host": "host2"})
        blk.process_signals([signal2])
        self.assertEqual(mock_client.call_count, 2)
        # Check block output
        self.assertEqual(len(self.last_notified[DEFAULT_TERMINAL]), 2)
        self.assertEqual(self.last_notified[DEFAULT_TERMINAL][0].value, '1')
        self.assertEqual(self.last_notified[DEFAULT_TERMINAL][1].value, '2')
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_write_coil(self, mock_client):
        ''' Test write_coil function '''
        blk = ModbusTCP()
        self.configure_block(blk, {'function_name': 'write_coil'})
        self.assertEqual(mock_client.call_count, 1)
        # Simulate some response from the modbus read
        blk._client(blk.host()).write_coil.return_value = SampleResponse()
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal()])
        self.assertEqual(blk._client(blk.host()).write_coil.call_count, 1)
        blk._client(blk.host()).write_coil.assert_called_once_with(
            address=0, value=True, unit=1)
        self.assertTrue(len(self.last_notified[DEFAULT_TERMINAL]))
        self.assertEqual(
            self.last_notified[DEFAULT_TERMINAL][0].value, 'default')
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_modbus_function_from_input_signal(self, mock_client):
        ''' Attributes on input signals can be used to pick modbus function '''
        blk = ModbusTCP()
        self.configure_block(blk, {'function_name': '{{ $function }}'})
        self.assertEqual(mock_client.call_count, 1)
        # Simulate some response from the modbus read
        blk._client(blk.host()).write_coils.return_value = SampleResponse()
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal({'function': 'write_multiple_coils'})])
        self.assertEqual(blk._client(blk.host()).write_coils.call_count, 1)
        blk._client(blk.host()).write_coils.assert_called_once_with(
            address=0, values=True, unit=1)
        self.assertTrue(len(self.last_notified[DEFAULT_TERMINAL]))
        self.assertEqual(
            self.last_notified[DEFAULT_TERMINAL][0].value, 'default')
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_exception_code(self, mock_client):
        ''' Test output signal when response contains an exception_code '''
        blk = ModbusTCP()
        self.configure_block(blk, {})
        # Simulate some exception response from the modbus read
        resp = SampleResponse()
        resp.exception_code = 2
        blk._client(blk.host()).read_coils.return_value = resp
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal()])
        self.assertEqual(
            self.last_notified[DEFAULT_TERMINAL][0].exception_details,
            'Data address of some or all the required entities '
            'are not allowed or do not exist in slave')
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_execute_retry_success(self, mock_client):
        ''' Test behavior when execute retry works '''
        blk = ModbusTCP()
        self.configure_block(blk, {'retry_options': {'multiplier': 0}})
        self.assertEqual(mock_client.call_count, 1)
        # Simulate an exception and then a success.
        blk._client(blk.host()).read_coils.side_effect = \
            [Exception, SampleResponse()]
        blk.start()
        # Read once and then retry.
        blk.process_signals([Signal()])
        # Modbus function is called twice. Once for the retry.
        self.assertEqual(blk._client(blk.host()).read_coils.call_count, 2)
        # A signal is output because of successful retry.
        self.assertTrue(bool(len(self.last_notified[DEFAULT_TERMINAL])))
        self.assertEqual(
            self.last_notified[DEFAULT_TERMINAL][0].value, 'default')
        # The retry created a new client before calling modbus function again.
        self.assertEqual(mock_client.call_count, 2)
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_execute_retry_fails(self, mock_client):
        ''' Test behavior when execute retry fails and runs out of retries '''
        blk = ModbusTCP()
        self.configure_block(blk, {
            "enrich": {"exclude_existing": False},
            "retry_options": {"multiplier": 0}})
        blk._client(blk.host()).read_coils.side_effect = Exception
        blk.start()
        blk.process_signals([Signal({'input': 'signal'})])
        self.assertDictEqual(
            self.last_notified[DEFAULT_TERMINAL][0].to_dict(), {
                'input': 'signal'})
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_limit_lock(self, mock_client):
        ''' Test that signals are dropped when the max locks is reached '''
        blk = ModbusTCP()
        self.configure_block(blk, {})
        event = Event()

        def _process_signals(signals):
            event.wait()
            blk.notify_signals(signals)
        blk._locked_process_signals = MagicMock(side_effect=_process_signals)
        blk.logger = MagicMock()
        blk.start()
        for _ in range(5):
            spawn(blk.process_signals, [Signal(), Signal()])
        blk.process_signals([Signal(), Signal()])
        # The last signal logs a warning because limit lock is reached
        self.assertEqual(blk.logger.warning.call_count, 1)
        # Only the first signal gets to call process signals because of lock
        self.assertEqual(blk._locked_process_signals.call_count, 1)
        # Now let the signals waiting for lock get processed and notify them
        event.set()
        sleep(0.1)
        self.assert_num_signals_notified(10)
        blk.stop()

    def test_exception_detail_codes(self):
        ''' Test that each exception code sets exception_details '''
        blk = ModbusTCP()
        # Check that the message is different for each code
        signal = Signal()
        prev_details = ''
        for code in [1, 2, 3, 4, 5, 6, 7, 8, 10, 11]:
            signal.exception_code = code
            blk._check_exceptions(signal)
            self.assertNotEqual(signal.exception_details, prev_details)
            prev_details = signal.exception_details
        # Check unkown status code does not give details
        signal = Signal()
        signal.exception_code = 12
        blk._check_exceptions(signal)
        self.assertFalse(hasattr(signal, 'exception_details'))
