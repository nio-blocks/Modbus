from collections import defaultdict
from unittest import skipUnless
from unittest.mock import MagicMock, patch
from nio.util.support.block_test_case import NIOBlockTestCase
from nio.common.signal.base import Signal


minimalmodbus_available = True
try:
    from ..modbus_rtu_block import ModbusRTU
except:
    minimalmodbus_available = False


class SampleResponse():
    def __init__(self, value='default'):
        self.value = value


@skipUnless(minimalmodbus_available, 'minimalmodbus is not available!!')
class TestModbusRTU(NIOBlockTestCase):

    def setUp(self):
        super().setUp()
        self.signals = defaultdict(list)

    def signals_notified(self, signals, output_id):
        self.signals[output_id].extend(signals)

    @patch('minimalmodbus.Instrument')
    def test_defaults(self, mock_client):
        ''' Test that read_regisers is called with default configuration '''
        blk = ModbusRTU()
        self.configure_block(blk, {})
        self.assertEqual(mock_client.call_count, 1)
        # Simulate some response from the modbus read
        blk._client.read_registers.return_value = [42]
        blk.start()
        # Read once and assert output
        blk.process_signals([Signal()])
        blk._client.read_registers.assert_called_once_with(registeraddress=0,
                                                           functioncode=4,
                                                           numberOfRegisters=1)
        self.assertTrue(len(self.signals['default']))
        self.assertEqual(self.signals['default'][0].values, [42])
        blk.stop()

    @patch('minimalmodbus.Instrument')
    def test_config(self, mock_client):
        ''' Test non-default configuration '''
        blk = ModbusRTU()
        self.configure_block(blk, {
            'function_name': 'write_single_coil',
            'value': '{{ False }}',
            'address': 1
        })
        self.assertEqual(mock_client.call_count, 1)
        blk._client.write_bit.return_value = [42]
        blk.start()
        blk.process_signals([Signal()])
        blk._client.write_bit.assert_called_once_with(registeraddress=1,
                                                      functioncode=5,
                                                      value=False)
        self.assertTrue(len(self.signals['default']))
        self.assertEqual(self.signals['default'][0].values, [42])
        blk.stop()

    @patch('minimalmodbus.Instrument')
    def test_config2(self, mock_client):
        ''' Test some non-default configuration '''
        blk = ModbusRTU()
        self.configure_block(blk, {
            'function_name': 'read_holding_registers',
            'address': 1,
            'count': 3
        })
        self.assertEqual(mock_client.call_count, 1)
        blk._client.read_registers.return_value = [42, 43, 44]
        blk.start()
        blk.process_signals([Signal()])
        blk._client.read_registers.assert_called_once_with(registeraddress=1,
                                                           functioncode=3,
                                                           numberOfRegisters=3)
        self.assertTrue(len(self.signals['default']))
        self.assertEqual(self.signals['default'][0].values, [42, 43, 44])
        blk.stop()

    @patch('minimalmodbus.Instrument')
    def test_invalid_value_property(self, mock_client):
        ''' Test when value is invalid '''
        blk = ModbusRTU()
        self.configure_block(blk, {
            'function_name': 'write_single_coil',
            'value': '{{ $$ }}'
        })
        self.assertEqual(mock_client.call_count, 1)
        blk.start()
        blk.process_signals([Signal()])
        self.assertEqual(blk._client.write_bit.call_count, 0)
        self.assertFalse(len(self.signals['default']))
        blk.stop()

    @patch('minimalmodbus.Instrument')
    def test_no_response(self, mock_client):
        ''' Test when value is invalid '''
        blk = ModbusRTU()
        self.configure_block(blk, {})
        self.assertEqual(mock_client.call_count, 1)
        blk._client.read_registers.return_value = None
        blk.start()
        blk.process_signals([Signal()])
        self.assertEqual(blk._client.read_registers.call_count, 1)
        self.assertFalse(len(self.signals['default']))
        blk.stop()
