# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import copy

import mock
from oslo.serialization import jsonutils
import requests_mock
import unittest2

from fuel_agent import errors
from fuel_agent.drivers import simple_format_validator as sfv
from fuel_agent.tests import base


    

class TestPartitionSchemaValidation(unittest2.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.VALID_PARTITION_DATA = base.load_fixture(
            'simple_format_validator.json')

    def _get_partition_data(self):
        return copy.deepcopy(self.VALID_PARTITION_DATA)

    def test_validation_success(self):
        assert sfv.validate(self.VALID_PARTITION_DATA) is None

    def test_pv_two_devices_fail(self):
        invalid = self._get_partition_data()
        invalid['pvs'][0]['device'] = '/dev/sda1'
        invalid['pvs'][0]['device_id'] = 'partition/1'

        with self.assertRaises(errors.WrongPartitionSchemeError):
            sfv.validate(invalid)

    def test_vg_pvs_ids_fail(self):
        invalid = self._get_partition_data()
        invalid['vgs'][0]['pvs_ids'] = [40, 50] 

        with self.assertRaises(errors.WrongPartitionSchemeError):
            sfv.validate(invalid)

    def test_lv_vg_id_fail(self):
        invalid = self._get_partition_data()
        invalid['lvs'][0]['vg_id'] = 69

        with self.assertRaises(errors.WrongPartitionSchemeError):
            sfv.validate(invalid)

    def test_md_invalid_device_fail(self):
        invalid = self._get_partition_data()
        invalid['mds'][0]['devices'][0] = 'gibberish'

        with self.assertRaises(errors.WrongPartitionSchemeError):
            sfv.validate(invalid)

    def test_partitions_overlap_fail(self):
        invalid = self._get_partition_data()
        invalid['partitions'] = [
            {
              "id": 1,
              "device": "/dev/sda",
              "begin": 0,
              "end": 9001
            },
            {
              "id": 2,
              "device": "/dev/sda",
              "begin": 9001,
              "end": 9100
            },
            {
              "id": 3,
              "device_id": "md/1",
              "begin": 0,
              "end": 10000
            }
        ]

        with self.assertRaises(errors.WrongPartitionSchemeError):
            sfv.validate(invalid)

        invalid['partitions'] = [
            {
              "id": 1,
              "device": "/dev/sda",
              "begin": 0,
              "end": 9050
            },
            {
              "id": 2,
              "device": "/dev/sda",
              "begin": 9000,
              "end": 9100
            },
            {
              "id": 3,
              "device_id": "md/1",
              "begin": 0,
              "end": 10000
            }
        ]

        with self.assertRaises(errors.WrongPartitionSchemeError):
            sfv.validate(invalid)

    def test_partitions_two_devices_fail(self):
        invalid = self._get_partition_data()
        invalid['partitions'][0]['device'] = '/dev/sda1'
        invalid['partitions'][0]['device_id'] = 'partition/1'

        with self.assertRaises(errors.WrongPartitionSchemeError):
            sfv.validate(invalid)

    def test_non_existent_device_by_metadata_fail(self):
        invalid = self._get_partition_data()
        invalid['fss'][0]['device_id'] = 'lv/30'

        with self.assertRaises(errors.WrongPartitionSchemeError):
            sfv.validate(invalid)

    def test_vgs_overlap_fail(self):
        invalid = self._get_partition_data()
        invalid['vgs'][0]['pvs_ids'] = [1, 2, 3]
        invalid['vgs'][1]['pvs_ids'] = [2, 3]

        with self.assertRaises(errors.WrongPartitionSchemeError):
            sfv.validate(invalid)
