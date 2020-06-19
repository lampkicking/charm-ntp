#!/usr/bin/env python3

from random import shuffle
from unittest.mock import Mock, patch
import sys
import unittest

sys.path.append('lib')
import ntp_scoring  # NOQA: E402


class TestNtpScoring(unittest.TestCase):

    def setUp(self):
        patcher = patch('ntp_scoring.log')
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch('charmhelpers.core.unitdata.kv')
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch('ntp_source_score.run_cmd')
    def testGetVirtTypeValues(self, run_cmd):
        def virt_test(expected, return_value):
            run_cmd.return_value = [return_value]
            self.assertEqual(ntp_scoring.get_virt_type(), expected)
            run_cmd.assert_called_once_with('facter virtual')
            run_cmd.reset_mock()

        virt_test('container', 'docker')
        virt_test('container', 'lxc')
        virt_test('container', 'openvz')
        virt_test('physical', 'physical')
        virt_test('physical', 'xen0')
        virt_test('vm', '')
        virt_test('vm', [])
        virt_test('vm', 1.23)
        virt_test('vm', 'a')
        virt_test('vm', 'kvm')
        virt_test('vm', None)
        virt_test('vm', 'something-else')
        virt_test('vm', 'The quick brown fox jumps over the lazy dogs')

    @patch('ntp_source_score.run_cmd')
    def testGetVirtTypeEmptyList(self, run_cmd):
        run_cmd.return_value = []
        self.assertEqual(ntp_scoring.get_virt_type(), 'vm')
        run_cmd.assert_called_once_with('facter virtual')

    @patch('ntp_source_score.run_cmd')
    def testGetVirtTypeWrongType(self, run_cmd):
        run_cmd.return_value = {}
        self.assertEqual(ntp_scoring.get_virt_type(), 'vm')
        run_cmd.assert_called_once_with('facter virtual')

    @patch('ntp_source_score.run_cmd')
    def testGetVirtMultiplier(self, run_cmd):
        def multiplier_test(expected, return_value):
            run_cmd.return_value = [return_value]
            self.assertEqual(ntp_scoring.get_virt_multiplier(), expected)
            run_cmd.assert_called_once_with('facter virtual')
            run_cmd.reset_mock()

        multiplier_test(-1, 'docker')
        multiplier_test(-1, 'lxc')
        multiplier_test(-1, 'openvz')
        multiplier_test(1.25, 'physical')
        multiplier_test(1.25, 'xen0')
        multiplier_test(1, '')
        multiplier_test(1, [])
        multiplier_test(1, 1.23)
        multiplier_test(1, 'a')
        multiplier_test(1, 'kvm')
        multiplier_test(1, None)
        multiplier_test(1, 'something-else')
        multiplier_test(1, 'The quick brown fox jumps over the lazy dogs')

    def testGetPackageDivisor(self):

        def test_divisor(expected, pslist, precision=6):
            def fake_pslist():
                """yield a list of objects for which name() returns the given list"""
                shuffle(pslist)
                for p in pslist:
                    m = Mock()
                    m.name.return_value = p
                    yield m

            with patch('psutil.process_iter', side_effect=fake_pslist):
                divisor = round(ntp_scoring.get_package_divisor(), precision)
                self.assertEqual(round(expected, precision), divisor)

        with self.assertRaises(TypeError):
            test_divisor(1, None)

        test_divisor(1, [])
        test_divisor(1, ['a', 'b', 'c'])
        test_divisor(1, 'The quick brown fox jumps over the lazy dogs'.split())
        test_divisor(1.1, 'The quick brown fox jumps over the lazy dogs'.split() + ['swift-1'])
        test_divisor(1.1, ['swift-1'])
        test_divisor(1.1, ['ceph-1', 'ceph-2'])
        test_divisor(1.25, ['ceph-osd-1', 'ceph-osd-2', 'ceph-osd-3'])
        test_divisor(1.25, ['nova-compute-1', 'nova-compute-2', 'nova-compute-3', 'nova-compute-4'])
        test_divisor(1.1 * 1.25, ['swift-1', 'nova-compute-2'])
        test_divisor(1.1 * 1.25, ['systemd', 'bind', 'swift-1', 'nova-compute-2', 'test'])
        test_divisor(1.1 * 1.25 * 1.1, ['swift-1', 'nova-compute-2', 'ceph-3'])
        test_divisor(1.1 * 1.25 * 1.25, ['swift-1', 'nova-compute-2', 'ceph-osd-3'])
        test_divisor(1.1 * 1.25 * 1.1 * 1.25, ['swift-1', 'nova-compute-2', 'ceph-3', 'ceph-osd-4'])
