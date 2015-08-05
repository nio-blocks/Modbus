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
