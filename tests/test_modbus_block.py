from collections import defaultdict
from unittest import skipUnless
from unittest.mock import MagicMock, patch
from nio.util.support.block_test_case import NIOBlockTestCase
from nio.common.signal.base import Signal


pymodbus3_available = True
try:
    from pymodbus3.exceptions import ModbusIOException
    from ..modbus_block import Modbus
except:
    pymodbus3_available = False


class SampleResponse():
    def __init__(self, value='default'):
        self.value = value


@skipUnless(pymodbus3_available, 'pymodbus3 is not available!!')
class TestModbus(NIOBlockTestCase):

    def setUp(self):
        super().setUp()
        self.signals = defaultdict(list)

    def signals_notified(self, signals, output_id):
        self.signals[output_id].extend(signals)

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_defaults(self, mock_client):
        blk = Modbus()
        self.configure_block(blk, {})
        self.assertEqual(mock_client.call_count, 1)
        # Simulate some response from the modbus read
        blk._client.read_coils.return_value = SampleResponse()
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal()])
        blk._client.read_coils.assert_called_once_with(address=0)
        self.assertTrue(len(self.signals['default']))
        self.assertEqual(self.signals['default'][0].value, 'default')
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_write_coil(self, mock_client):
        blk = Modbus()
        self.configure_block(blk, {'function_name': 'write_coil'})
        self.assertEqual(mock_client.call_count, 1)
        # Simulate some response from the modbus read
        blk._client.write_coil.return_value = SampleResponse()
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal()])
        self.assertEqual(blk._client.write_coil.call_count, 1)
        blk._client.write_coil.assert_called_once_with(address=0, value=True)
        self.assertTrue(len(self.signals['default']))
        self.assertEqual(self.signals['default'][0].value, 'default')
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_write_multiple_coils(self, mock_client):
        blk = Modbus()
        self.configure_block(blk, {'function_name': 'write_multiple_coils'})
        self.assertEqual(mock_client.call_count, 1)
        # Simulate some response from the modbus read
        blk._client.write_coils.return_value = SampleResponse()
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal()])
        self.assertEqual(blk._client.write_coils.call_count, 1)
        blk._client.write_coils.assert_called_once_with(address=0, values=True)
        self.assertTrue(len(self.signals['default']))
        self.assertEqual(self.signals['default'][0].value, 'default')
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_exception_code(self, mock_client):
        ''' Sometimes the response contains an exception_code '''
        blk = Modbus()
        self.configure_block(blk, {})
        # Simulate some exception response from the modbus read
        resp = SampleResponse()
        resp.exception_code = 2
        blk._client.read_coils.return_value = resp
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal()])
        self.assertEqual(self.signals['default'][0].exception_details,
                         'Data address of some or all the required entities '
                         'are not allowed or do not exist in slave')
        blk.stop()

    @patch('pymodbus3.client.sync.ModbusTcpClient')
    def test_execute_exception(self, mock_client):
        blk = Modbus()
        self.configure_block(blk, {})
        self.assertEqual(mock_client.call_count, 1)
        # Simulate some response from the modbus read
        blk._client.read_coils.side_effect = ModbusIOException
        #blk._client.read_coils.return_value = SampleResponse()
        blk.start()
        # Read once and then retry. No output signal.
        blk.process_signals([Signal()])
        self.assertEqual(blk._client.read_coils.call_count, 2)
        self.assertFalse(bool(len(self.signals['default'])))
        # The retry created and new client
        self.assertEqual(mock_client.call_count, 2)
        blk.stop()

    def test_exception_detail_codes(self):
        blk = Modbus()
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
