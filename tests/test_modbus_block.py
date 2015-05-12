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
