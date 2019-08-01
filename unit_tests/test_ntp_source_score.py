#!/usr/bin/env python3

from unittest.mock import patch
import math
import sys
import unittest

sys.path.append('lib')
from ntp_source_score import (
    get_delay_score,
    get_source_delays,
    rms,
    run_cmd,
)

ntpdate_output = """
...
reference time:    dda179ee.3ec34fdd  Mon, Oct 30 2017 20:14:06.245
originate timestamp: dda17a5b.af7c528b  Mon, Oct 30 2017 20:15:55.685
transmit timestamp:  dda17a5b.80b4dc04  Mon, Oct 30 2017 20:15:55.502
filter delay:  0.54126  0.36757  0.36655  0.36743 
         0.00000  0.00000  0.00000  0.00000 
filter offset: 0.099523 0.012978 0.011831 0.011770
         0.000000 0.000000 0.000000 0.000000
delay 0.36655, dispersion 0.01126
offset 0.011831
...
reference time:    dda17695.69e65b2f  Mon, Oct 30 2017 19:59:49.413
originate timestamp: dda17a5b.afcec2dd  Mon, Oct 30 2017 20:15:55.686
transmit timestamp:  dda17a5b.80bb2488  Mon, Oct 30 2017 20:15:55.502
filter delay:  0.36520  0.36487  0.36647  0.36604 
         0.00000  0.00000  0.00000  0.00000 
filter offset: 0.012833 0.013758 0.013731 0.013629
         0.000000 0.000000 0.000000 0.000000
delay 0.36487, dispersion 0.00049
offset 0.013758
...
reference time:    dda1782c.6aec9646  Mon, Oct 30 2017 20:06:36.417
originate timestamp: dda17a5b.d2d04ef4  Mon, Oct 30 2017 20:15:55.823
transmit timestamp:  dda17a5b.b37c4098  Mon, Oct 30 2017 20:15:55.701
filter delay:  0.28581  0.28406  0.28551  0.28596 
         0.00000  0.00000  0.00000  0.00000 
filter offset: -0.00802 -0.00854 -0.00791 -0.00787
         0.000000 0.000000 0.000000 0.000000
delay 0.28406, dispersion 0.00050
offset -0.008544
...
reference time:    dda17735.4a03e3ca  Mon, Oct 30 2017 20:02:29.289
originate timestamp: dda17a5c.1634d231  Mon, Oct 30 2017 20:15:56.086
transmit timestamp:  dda17a5b.e6934fad  Mon, Oct 30 2017 20:15:55.900
filter delay:  0.37044  0.37077  0.37050  0.37086 
         0.00000  0.00000  0.00000  0.00000 
filter offset: 0.013993 0.013624 0.013425 0.013362
         0.000000 0.000000 0.000000 0.000000
delay 0.37044, dispersion 0.00046
offset 0.013993
...
reference time:    dda17695.69e65b2f  Mon, Oct 30 2017 19:59:49.413
originate timestamp: dda17a5c.4944bb52  Mon, Oct 30 2017 20:15:56.286
transmit timestamp:  dda17a5c.19cf5199  Mon, Oct 30 2017 20:15:56.100
filter delay:  0.36873  0.36823  0.36911  0.36781 
         0.00000  0.00000  0.00000  0.00000 
filter offset: 0.014635 0.014599 0.014166 0.014239
         0.000000 0.000000 0.000000 0.000000
delay 0.36781, dispersion 0.00026
offset 0.014239
...
reference time:    dda179ee.3ec34fdd  Mon, Oct 30 2017 20:14:06.245
originate timestamp: dda17a5c.7bbd3828  Mon, Oct 30 2017 20:15:56.483
transmit timestamp:  dda17a5c.4cf92e99  Mon, Oct 30 2017 20:15:56.300
filter delay:  0.36554  0.36617  0.36673  0.36618 
         0.00000  0.00000  0.00000  0.00000 
filter offset: 0.012466 0.012691 0.012863 0.012346
         0.000000 0.000000 0.000000 0.000000
delay 0.36554, dispersion 0.00018
offset 0.012466
...
"""
ntpdate_delays = [0.36655, 0.36487, 0.28406, 0.37044, 0.36781, 0.36554]


class TestNtpSourceScore(unittest.TestCase):

    def test_rms(self):
        self.assertEqual(rms([0, 0, 0, 0, 0]), 0)
        self.assertEqual(rms([0, 1, 0, 1, 0]), math.sqrt(0.4))
        self.assertEqual(rms([1, 1, 1, 1, 1]), 1)
        self.assertEqual(rms([1, 2, 3, 4, 5]), math.sqrt(11))
        self.assertEqual(rms([0.01, 0.02]), math.sqrt(0.00025))
        self.assertEqual(rms([0.02766, 0.0894, 0.02657, 0.02679]), math.sqrt(0.00254527615))
        self.assertEqual(rms([80, 50, 30]), math.sqrt(3266.66666666666666667))
        self.assertEqual(rms([81, 53, 32]), math.sqrt(3464.66666666666666667))
        self.assertEqual(rms([81.1, 53.9, 32.3]), math.sqrt(3508.57))
        self.assertEqual(rms([81.14, 53.93, 32.30]), math.sqrt(3511.8115))
        self.assertEqual(rms([81.141, 53.935, 32.309]), math.sqrt(3512.23919566666666667))
        self.assertTrue(math.isnan(rms([])))
        with self.assertRaises(TypeError):
            rms(['a', 'b', 'c'])

    @patch('subprocess.check_output')
    def test_run_cmd(self, patched):
        patched.return_value = b'a\nb\nc\n'
        self.assertEqual(run_cmd('ls'), ['a', 'b', 'c', ''])

        patched.return_value = b'4.13.0-14-generic\n'
        self.assertEqual(run_cmd('uname -r'), ['4.13.0-14-generic', ''])

        self.assertEqual(patched.call_count, 2)

    def test_get_source_delays(self):

        @patch('ntp_source_score.run_cmd')
        def test_source_delay(data, expect, patched):
            patched.return_value = data
            self.assertEqual(get_source_delays('ntp.example.com'), expect)
            patched.assert_called_once_with('ntpdate -d -t 0.2 ntp.example.com')

        @patch('ntp_source_score.run_cmd')
        def test_source_delay_error(data, e, patched):
            patched.return_value = data
            with self.assertRaises(e):
                get_source_delays('ntp.example.com')
            patched.assert_called_once_with('ntpdate -d -t 0.2 ntp.example.com')

        test_source_delay([], [])
        test_source_delay('', [])
        test_source_delay('123', [])
        test_source_delay(['123 678', '234 asdf', 'yaled 345 901'], [])
        test_source_delay(['123 678', 'delay 345 901', '234 asdf'], [345])
        test_source_delay(['delay 123 678', 'delay 234 asdf', 'delay 345 901'], [123, 234, 345])
        test_source_delay(ntpdate_output.split('\n'), ntpdate_delays)

        test_source_delay_error(None, TypeError)
        test_source_delay_error(123, TypeError)

    def test_get_delay_score_error(self):
        # You can't have a negative or zero response time
        with self.assertRaises(ValueError):
            get_delay_score(-100)
        with self.assertRaises(ValueError):
            get_delay_score(-1)
        with self.assertRaises(ValueError):
            get_delay_score(-0.1)
        with self.assertRaises(ValueError):
            get_delay_score(0)

    def test_get_delay_scores(self):
        scores = [
            get_delay_score(0.001),     # 1ms delay
            get_delay_score(0.01),
            get_delay_score(0.025),
            get_delay_score(0.05),
            get_delay_score(0.1),
            get_delay_score(0.333),     # anything beyond this should never happen
            get_delay_score(0.999),
            get_delay_score(1),
            get_delay_score(3),         # 3s delay - probably on the moon
            get_delay_score(10),
            get_delay_score(9999),      # 2.79h delay - are you orbiting Saturn or something?
        ]

        for i in range(len(scores)):
            # all lower delays should get a higher score
            for higher in range(i):
                self.assertLess(scores[i], scores[higher])
            # all higher delays should get a lower score
            if i < len(scores) - 1:
                for lower in range(i + 1, len(scores)):
                    self.assertGreater(scores[i], scores[lower])
