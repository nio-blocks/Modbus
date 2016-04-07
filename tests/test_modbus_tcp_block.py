from collections import defaultdict
from unittest import skipUnless
from unittest.mock import patch
from nio.block.terminals import DEFAULT_TERMINAL
from nio.testing.block_test_case import NIOBlockTestCase
from nio.signal.base import Signal


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
        blk._client.read_coils.return_value = SampleResponse()
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal()])
        blk._client.read_coils.assert_called_once_with(address=0)
        self.assertTrue(len(self.last_notified[DEFAULT_TERMINAL]))
        self.assertEqual(self.last_notified[DEFAULT_TERMINAL][0].value, 'default')
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_write_coil(self, mock_client):
        ''' Test write_coil function '''
        blk = ModbusTCP()
        self.configure_block(blk, {'function_name': 'write_coil'})
        self.assertEqual(mock_client.call_count, 1)
        # Simulate some response from the modbus read
        blk._client.write_coil.return_value = SampleResponse()
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal()])
        self.assertEqual(blk._client.write_coil.call_count, 1)
        blk._client.write_coil.assert_called_once_with(address=0, value=True)
        self.assertTrue(len(self.last_notified[DEFAULT_TERMINAL]))
        self.assertEqual(self.last_notified[DEFAULT_TERMINAL][0].value, 'default')
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_write_multiple_coils(self, mock_client):
        ''' Test write_multiple_coil function '''
        blk = ModbusTCP()
        self.configure_block(blk, {'function_name': 'write_multiple_coils'})
        self.assertEqual(mock_client.call_count, 1)
        # Simulate some response from the modbus read
        blk._client.write_coils.return_value = SampleResponse()
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal()])
        self.assertEqual(blk._client.write_coils.call_count, 1)
        blk._client.write_coils.assert_called_once_with(address=0, values=True)
        self.assertTrue(len(self.last_notified[DEFAULT_TERMINAL]))
        self.assertEqual(self.last_notified[DEFAULT_TERMINAL][0].value, 'default')
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_exception_code(self, mock_client):
        ''' Test output signal when response contains an exception_code '''
        blk = ModbusTCP()
        self.configure_block(blk, {})
        # Simulate some exception response from the modbus read
        resp = SampleResponse()
        resp.exception_code = 2
        blk._client.read_coils.return_value = resp
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal()])
        self.assertEqual(self.last_notified[DEFAULT_TERMINAL][0].exception_details,
                         'Data address of some or all the required entities '
                         'are not allowed or do not exist in slave')
        blk.stop()

    @patch("{}.sleep".format(ModbusTCP.__module__))
    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_execute_retry_forever(self, mock_client, mock_sleep):
        ''' Test that retries will continue forever '''
        blk = ModbusTCP()
        self.configure_block(blk, {})
        blk._backoff_strategy.retry_num = 0
        self.assertTrue(blk._backoff_strategy.next_retry())
        # And even when we've passed the number of allowed retries
        blk._backoff_strategy.retry_num = 99
        self.assertTrue(blk._backoff_strategy.next_retry())

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_execute_retry_success(self, mock_client):
        ''' Test behavior when execute retry works '''
        blk = ModbusTCP()
        self.configure_block(blk, {})
        self.assertEqual(mock_client.call_count, 1)
        # Simulate an exception and then a success.
        blk._client.read_coils.side_effect = \
            [Exception, SampleResponse()]
        blk.start()
        # Read once and then retry.
        blk.process_signals([Signal()])
        # Modbus function is called twice. Once for the retry.
        self.assertEqual(blk._client.read_coils.call_count, 2)
        # A signal is output because of successful retry.
        self.assertTrue(bool(len(self.last_notified[DEFAULT_TERMINAL])))
        self.assertEqual(self.last_notified[DEFAULT_TERMINAL][0].value, 'default')
        # The retry created a new client before calling modbus function again.
        self.assertEqual(mock_client.call_count, 2)
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_lock_counter(self, mock_client):
        ''' Test that the num_locks counter works '''
        blk = ModbusTCP()
        def _process_signal(signal):
            self.assertEqual(blk._num_locks, 1)
            return signal
        blk._process_signal = _process_signal
        self.configure_block(blk, {})
        blk.start()
        self.assertEqual(blk._num_locks, 0)
        blk.process_signals([Signal()])
        self.assertEqual(blk._num_locks, 0)
        self.assertEqual(len(self.last_notified[DEFAULT_TERMINAL]), 1)
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_max_locks(self, mock_client):
        ''' Test that signals are dropped when the max locks is reached '''
        blk = ModbusTCP()
        self.configure_block(blk, {})
        # Put the block in a state where all the max locks is reached
        blk._num_locks = blk._max_locks
        blk.start()
        blk.process_signals([Signal()])
        self.assertEqual(len(self.last_notified[DEFAULT_TERMINAL]), 0)
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
