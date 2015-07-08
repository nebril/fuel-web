# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import itertools

import jsonschema

from fuel_agent import errors
from fuel_agent.openstack.common import log as logging

LOG = logging.getLogger(__name__)


SIMPLE_FORMAT_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'Volume Management Metadata',
    'type': 'object',
    'properties': {
        'pvs': {
            'title': 'Physical volumes',
            'type': 'array',
            'items': {
                'title': 'Physical volume',
                'type': 'object',
                'properties': {
                    'id': {
                        'description': 'Index of physical volume',
                        'type': 'number'
                    }
                },
                'required': ['id'],
                'oneOf': [
                    {
                        '$ref': '#/definitions/deviceBySystem'
                    },
                    {
                        '$ref': '#/definitions/deviceByMetadata'
                    }
                ],
            },
        },
        'vgs': {
            'title': 'Volume groups',
            'type': 'array',
            'items': {
                'title': 'Volume group',
                'type': 'object',
                'properties': {
                    'id': {
                        'description': 'Index of volume group',
                        'type': 'number',
                    },
                    'name': {
                        'type': 'string'
                    },
                    'pvs_ids': {
                        'type': 'array',
                        'title': 'Physical volumes indices',
                        'items': {
                            'type': 'number'
                        }
                    }
                },
                'required': ['id', 'name', 'pvs_ids']
            }
        },
        'lvs': {
            'title': 'Logical volumes',
            'type': 'array',
            'items': {
                'title': 'Logical volume',
                'type': 'object',
                'properties': {
                    'id': {
                        'description': 'Index of logical volume',
                        'type': 'number',
                    },
                    'name': {
                        'type': 'string'
                    },
                    'vg_id': {
                        'description': 'Volume group id',
                        'type': 'number'
                    },
                    'size': {
                        'type': 'string',
                        'pattern': '^[1-9][0-9]*(k|M|G|T)?B'
                    }
                },
                'required': ['id', 'name', 'vg_id', 'size']
            }
        },
        'mds': {
            'title': 'Multiple devices',
            'type': 'array',
            'items': {
                'title': 'Multiple device',
                'type': 'object',
                'properties': {
                    'id': {
                        'description': 'Index of multiple device',
                        'type': 'number',
                    },
                    'devices': {
                        'type': 'array',
                        'minItems': 1,
                        'items': {
                            '$ref': '#/definitions/pathPattern'
                        }
                    },
                    'spares': {
                        'type': 'array',
                        'items': {
                            '$ref': '#/definitions/pathPattern'
                        }
                    },
                },
                'required': ['id', 'devices', 'spares']
            }
        },
        'partitions': {
            'title': 'Partitions',
            'type': 'array',
            'items': {
                'title': 'Partition',
                'type': 'object',
                'required': ['id', 'begin', 'end'],
                'allOf': [
                    {'properties': {
                        'id': {
                            'description': 'Index of partition',
                            'type': 'number',
                        },
                        'begin': {
                            'type': 'number'
                        },
                        'end': {
                            'type': 'number'
                        }
                    }},
                    {'oneOf': [
                        {
                            '$ref': '#/definitions/deviceBySystem'
                        },
                        {
                            '$ref': '#/definitions/deviceByMetadata'
                        }
                    ]}
                ]
            }
        },
        'fss': {
            'title': 'File systems',
            'type': 'array',
            'items': {
                'title': 'File system',
                'type': 'object',
                'required': ['id', 'mount', 'type'],
                'allOf': [
                    {'properties': {
                        'id': {
                            'description': 'Index of filesystem',
                            'type': 'number',
                        },
                        'mount': {
                            '$ref': '#/definitions/pathPattern'
                        },
                        'type': {
                            'type': 'string' 
                        }
                    }},
                    {'$ref': '#/definitions/deviceByMetadata'}
                ]
            }
        }
    },
    'definitions': {
        'deviceBySystem': {
            'required': ['device'],
            'properties': {
                'device': {
                    'description': 'Device system path',
                    '$ref': '#/definitions/pathPattern'
                },
                "device_id": {
                    "not": {}
                }
            },
        },
        'deviceByMetadata': {
            'required': ['device_id'],
            'properties': {
                'device_id': {
                    'description': 'Device metadata path',
                    '$ref': '#/definitions/metadataReferencePattern'
                },
                "device": {
                    "not": {}
                }
            },
        },
        'pathPattern': {
            'pattern': '^((\/)|((\/[^\/]+)+))$',
            'type': 'string'
        },
        'metadataReferencePattern': {
            'pattern': '^(lv|partition|md)\/[1-9][0-9]*$',
            'type': 'string'
        }
    }
}


def validate(scheme):
    """Validates a given partition scheme.

    :param scheme: partition scheme to validate
    """
    try:
        checker = jsonschema.FormatChecker()
        jsonschema.validate(scheme, SIMPLE_FORMAT_SCHEMA,
                            format_checker=checker)
    except Exception as exc:
        LOG.exception(exc)
        raise errors.WrongPartitionSchemeError(str(exc))


    all_objects = itertools.chain.from_iterable([y for _, y in
                                                 scheme.iteritems()])
    for object in (x for x in all_objects if 'device_id' in x):
        key, id = object['device_id'].split('/')
        key = key + 's'

        matching_devices = [x for x in scheme[key] if int(x['id']) == int(id)]
        if len(matching_devices) != 1:
            error = errors.WrongPartitionSchemeError(
                ('Device {0} does not exist or is duplicated'
                ).format(object['device_id']))
            LOG.exception(error)
            raise error


    partition_groups = itertools.groupby(
        scheme['partitions'],
        lambda x: x['device'] if 'device' in x else  x['device_id'])

    for group in partition_groups:
        for pair in itertools.combinations(group[1], 2):
            if len(xrange(
                    max(pair[0]['begin'], pair[1]['begin']),
                    min(pair[0]['end'], pair[1]['end']) + 1)) > 0:

                error = errors.WrongPartitionSchemeError(
                    ('Partitions {0} and {1} overlap on device {2}.'
                    ).format(pair[0]['id'], pair[1]['id'], group[0]))
                LOG.exception(error)
                raise error

    
    pvs_ids = [x['id'] for x in scheme['pvs']]
    for vg in scheme['vgs']:
        if any([pv_id not in pvs_ids for pv_id in vg['pvs_ids']]):
            error = errors.WrongPartitionSchemeError(
                ('Volume group {0} consists of non-existent physical volumes'
                ).format(vg['id']))
            LOG.exception(error)
            raise error

    used_pvs_ids = itertools.chain.from_iterable([vg['pvs_ids'] for vg in
                                                  scheme['vgs']]) 
    pvs_frequencies = [(key, len(list(group))) for key, group in
                       itertools.groupby(sorted(used_pvs_ids))]
    if any(x[1] > 1 for x in pvs_frequencies):
        failed_pvs = [x for x in pvs_frequencies if x[1] > 1]
        error = errors.WrongPartitionSchemeError(
            ('Following pvs were used too many times: {0}'
            ).format(failed_pvs))
        LOG.exception(error)
        raise error


    vgs_ids = [x['id'] for x in scheme['vgs']]
    for lv in scheme['lvs']:
        if lv['vg_id'] not in vgs_ids:
            error = errors.WrongPartitionSchemeError(
                ('Logical volume {0} tries to use non-existent volume group'
                 ' with id {1}').format(lv['id'], lv['vg_id']))
            LOG.exception(error)
            raise error
