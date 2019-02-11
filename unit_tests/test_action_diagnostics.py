#!/usr/bin/env python3

import os
import unittest
import unittest.mock as mock
import sys

# This is necessary to stop charmhelpers.contrib.templating.jinja (called from ntp_implementation,
# called from diagnostics) from trying to install apt packages, by giving it an existing jinja2 module.
# The templating engine isn't required for these tests.
sys.modules['jinja2'] = mock.MagicMock()

import diagnostics      # NOQA: E402


class TestNTPActionDiagnostics(unittest.TestCase):

    _file_contents = {
        '/tmp/apple': b'This is an apple\nHere are more apples.\nAnd more.\n',
        '/tmp/apricot': b'This is an apricot\n',
        '/tmp/avocado': b'This is an avocado\n',
    }

    def test_command(self):
        testkey = 'os.uname'
        (key, out) = diagnostics.command(testkey, 'uname -r')
        release = os.uname().release
        self.assertEqual(key, testkey)
        self.assertEqual(out, release)

    @mock.patch('subprocess.check_output')
    def test_command_mock(self, check_output):
        testkey = 'cattmpa'
        testcmd = 'cat /tmp/a'
        check_output.return_value = b'These are the contents of /tmp/a\n \n \n'
        (key, out) = diagnostics.command(testkey, testcmd)
        check_output.assert_called_once_with(['cat', '/tmp/a'])
        self.assertEqual(key, testkey)
        self.assertEqual(out, 'These are the contents of /tmp/a')

    @staticmethod
    def _fake_glob(names):
        """Mock method to return a list of file names
        when glob is called with the correct arguments."""
        if names == '/tmp/a*':
            return sorted(TestNTPActionDiagnostics._file_contents.keys())
        else:
            return []

    @staticmethod
    def _fake_check_output(args):
        """Mock method to return a byte array containing fake file contents
        when check_output is called with the correct arguments."""
        if args[0] == 'tail' and args[1] in TestNTPActionDiagnostics._file_contents:
            return TestNTPActionDiagnostics._file_contents[args[1]]
        else:
            return b''

    @mock.patch('os.path.exists')
    @mock.patch('subprocess.check_output')
    @mock.patch('glob.glob')
    def test_tail_no_regex(self, glob, check_output, exists):
        testkey = 'test.glob'
        testfiles = '/tmp/a*'
        exists.return_value = True
        glob.side_effect = self._fake_glob
        check_output.side_effect = self._fake_check_output
        results = list(diagnostics.tail(testkey, testfiles))
        glob.assert_called_once_with(testfiles)
        exists.assert_has_calls([
            mock.call('/tmp/apple'),
            mock.call('/tmp/apricot'),
            mock.call('/tmp/avocado'),
        ])
        check_output.assert_has_calls([
            mock.call(['tail', '/tmp/apple']),
            mock.call(['tail', '/tmp/apricot']),
            mock.call(['tail', '/tmp/avocado']),
        ])
        self.assertEqual(results[0], (
            'test.glob.apple',
            TestNTPActionDiagnostics._file_contents['/tmp/apple'].decode().rstrip(),
        ))
        self.assertEqual(results[1], (
            'test.glob.apricot',
            TestNTPActionDiagnostics._file_contents['/tmp/apricot'].decode().rstrip(),
        ))
        self.assertEqual(results[2], (
            'test.glob.avocado',
            TestNTPActionDiagnostics._file_contents['/tmp/avocado'].decode().rstrip(),
        ))
        self.assertEqual(len(results), 3)

    @mock.patch('os.path.exists')
    @mock.patch('subprocess.check_output')
    @mock.patch('glob.glob')
    def test_tail_with_regex(self, glob, check_output, exists):
        testkey = 'test.glob'
        testfiles = '/tmp/a*'
        testregex = r'^/tmp/(ap.*)'
        exists.return_value = True
        glob.side_effect = self._fake_glob
        check_output.side_effect = self._fake_check_output
        results = list(diagnostics.tail(testkey, testfiles, testregex))
        glob.assert_called_once_with(testfiles)
        exists.assert_has_calls([
            mock.call('/tmp/apple'),
            mock.call('/tmp/apricot'),
        ])
        check_output.assert_has_calls([
            mock.call(['tail', '/tmp/apple']),
            mock.call(['tail', '/tmp/apricot']),
        ])
        self.assertEqual(results[0], (
            'test.glob.apple',
            TestNTPActionDiagnostics._file_contents['/tmp/apple'].decode().rstrip(),
        ))
        self.assertEqual(results[1], (
            'test.glob.apricot',
            TestNTPActionDiagnostics._file_contents['/tmp/apricot'].decode().rstrip(),
        ))
        self.assertEqual(len(results), 2)

    @mock.patch('ntp_implementation.detect_implementation')
    def test_collect_actions_unknown_implementation(self, detect_implementation):
        """None of these implementations should ever be detected"""
        def test_collect_action(return_value):
            detect_implementation.return_value = return_value
            diagnostics.collect_actions()
            detect_implementation.reset_mock()

        with self.assertRaises(diagnostics.UnsupportedNTPImplementationError):
            test_collect_action(None)
        with self.assertRaises(diagnostics.UnsupportedNTPImplementationError):
            test_collect_action(1)
        with self.assertRaises(diagnostics.UnsupportedNTPImplementationError):
            test_collect_action('')
        with self.assertRaises(diagnostics.UnsupportedNTPImplementationError):
            test_collect_action('ntpsec')
        with self.assertRaises(diagnostics.UnsupportedNTPImplementationError):
            test_collect_action('openntpd')
        with self.assertRaises(diagnostics.UnsupportedNTPImplementationError):
            test_collect_action('systemd.timesyncd')

    @staticmethod
    def _fake_glob_known_implementation(spec):
        if spec == '/sys/devices/system/clocksource/clocksource*/*_clocksource':
            return ['/sys/devices/system/clocksource/clocksource0/current_clocksource']
        elif spec == '/var/log/chrony/*.log':
            return ['/var/log/chrony/measurements.log']

    @mock.patch('os.path.exists')
    @mock.patch('glob.glob')
    @mock.patch('subprocess.check_output')
    @mock.patch('ntp_implementation.detect_implementation')
    def test_collect_actions_known_implementation(self, detect_implementation, check_output, glob, exists):
        """Test overall action collection if chrony is the detected implementation."""
        detect_implementation.return_value = 'chrony'
        glob.side_effect = self._fake_glob_known_implementation
        exists.return_value = True
        check_output.return_value = b'check_output fake output\n\n'

        result = dict(diagnostics.collect_actions())

        self.assertEqual(detect_implementation.call_count, 1)

        glob.assert_has_calls([
            mock.call('/sys/devices/system/clocksource/clocksource*/*_clocksource'),
            mock.call('/var/log/chrony/*.log'),
        ])
        self.assertEqual(glob.call_count, 2)

        exists.assert_has_calls([
            mock.call('/sys/devices/system/clocksource/clocksource0/current_clocksource'),
            mock.call('/var/log/chrony/measurements.log'),
        ])
        self.assertEqual(exists.call_count, 2)

        check_output.assert_has_calls([
            mock.call(['/usr/bin/chronyc', '-n', 'sources']),
            mock.call(['/usr/bin/chronyc', '-n', 'tracking']),
            mock.call(['tail', '/sys/devices/system/clocksource/clocksource0/current_clocksource']),
            mock.call(['tail', '/var/log/chrony/measurements.log']),
        ])
        self.assertEqual(check_output.call_count, 4)

        self.assertEqual(result, {
            'kernel.release': os.uname().release,
            'kernel.clocksource0.current': 'check_output fake output',
            'ntp.implementation': 'chrony',
            'ntp.sources': 'check_output fake output',
            'ntp.tracking': 'check_output fake output',
            'ntp.log.measurements': 'check_output fake output',
        })
