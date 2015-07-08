import abc
import itertools

import jsonschema

from nailgun.extensions.volume_manager import errors
from nailgun.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class ValidationError(Exception):
    pass


class BaseValidator(object):

    @abc.abstractmethod
    def validate(self, *args, **kwargs):
        pass


class PartitionSchemeValidator(BaseValidator):

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
                        },
                    },
                    '$ref': '#/definitions/deviceBySystemOrReference',
                    'required': ['id'],
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
                        'label': {
                            'type': 'string'
                        },
                        'pvs': {
                            'type': 'array',
                            'title': 'Physical volumes indices',
                            'items': {
                                'type': 'number'
                            }
                        }
                    },
                    'required': ['id', 'name', 'pvs', 'label']
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
                        'vgname': {
                            'description': 'Volume group name',
                            'type': 'string'
                        },
                        'size': {
                            'type': 'string',
                            'pattern': '^[1-9][0-9]*(k|M|G|T)?B'
                        }
                    },
                    'required': ['id', 'name', 'vgname', 'size']
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
            'parteds': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    '$ref': '#/definitions/deviceBySystemOrReference',
                    'properties': {
                        'id': {
                            'type': 'number',
                        },
                        'label': {
                            'type': 'string',
                        },
                        'name': {
                            'type': 'string',
                        },
                        'partitions': {
                            'title': 'Partitions',
                            'type': 'array',
                            'items': {
                                'title': 'Partition',
                                'type': 'object',
                                'required': ['id', 'begin', 'end', 'partition_type'],
                                'properties': {
                                    'id': {
                                        'type': 'number',
                                    },
                                    'begin': {
                                        'type': 'number'
                                    },
                                    'end': {
                                        'type': 'number'
                                    },
                                    'name': {
                                        'type': 'string'
                                    },
                                    'count': {
                                        'type': 'number'
                                    },
                                    'partition_type': {
                                        'type': 'string',
                                    },
                                    'guid': {
                                        'type': 'string',
                                    },
                                },
                                '$ref': '#/definitions/deviceBySystemOrReference',
                            }
                        }
                    }
                }
            },
            'fss': {
                'title': 'File systems',
                'type': 'array',
                'items': {
                    'title': 'File system',
                    'type': 'object',
                    'required': ['id', 'mount', 'fs_type', 'fs_label'],
                    'allOf': [
                        {'properties': {
                            'id': {
                                'description': 'Index of filesystem',
                                'type': 'number',
                            },
                            'mount': {
                                '$ref': '#/definitions/pathPattern'
                            },
                            'fs_type': {
                                'type': 'string'
                            },
                            'fs_label': {
                                'type': 'string'
                            }
                        }},
                        {'$ref': '#/definitions/deviceBySystemOrReference'}
                    ]
                }
            }
        },
        'definitions': {
            'deviceBySystemOrReference': {
                'required': ['device'],
                'properties': {
                    'device': {
                        'description': 'Device metadata path',
                        '$ref': '#/definitions/devicePattern'
                    },
                }
            },
            'pathPattern': {
                'pattern': '^((\/)|((\/[^\/]+)+))$',
                'type': 'string'
            },
            'metadataReferencePattern': {
                'pattern': '^(lv|partition|md)\/[1-9][0-9]*$',
                'type': 'string'
            },
            'devicePattern': {
                'pattern': '^((@(lvs|parteds|mds)(\/[1-9][0-9]*)+)|((\/)|((\/[^\/]+)+)))$',
                'type': 'string'
            }
        }
    }

    def validate(self, dict_scheme):
        # TODO(mkwiek): partition overlap check
        try:
            checker = jsonschema.FormatChecker()
            jsonschema.validate(dict_scheme, self.SIMPLE_FORMAT_SCHEMA,
                                format_checker=checker)
        except Exception as exc:
            LOG.exception(exc)
            raise errors.WrongPartitionSchemeError(str(exc))

        all_objects = itertools.chain.from_iterable([y for _, y in
                                                     dict_scheme.iteritems()])
        for object in (x for x in all_objects
                       if 'device' in x and x['device'][0] == '@'):
            splitted = object['device'].split('/')
            key, ids = splitted[0], splitted[1:]
            key = key[1:]

            if key == 'parteds':
                matching_parteds = [x for x in dict_scheme[key]
                                    if int(x['id']) == int(ids[0])]
                if len(matching_parteds) != 1:
                    self.raise_error('Parted with id {0} does not exist'
                                     ' or is duplicated'.format(ids[0]))
                parent = matching_parteds[0]['partitions']
                id = ids[1]
            else:
                parent = dict_scheme[key]
                id = ids[0]

            matching_devices = [
                x for x in parent if int(x['id']) == int(id)]
            if len(matching_devices) != 1:
                error = errors.WrongPartitionSchemeError(
                    'Device {0} does not exist or is duplicated'.format(
                        object['device'])
                )
                LOG.exception(error)
                raise error

        pvs_ids = [x['id'] for x in dict_scheme['pvs']]
        for vg in dict_scheme['vgs']:
            if any([pv_id not in pvs_ids for pv_id in vg['pvs']]):
                error = errors.WrongPartitionSchemeError('Volume group {0}'
                                                         ' consists of'
                                                         ' non-existent physical'
                                                         ' volumes'.format(
                                                             vg['id']))
                LOG.exception(error)
                raise error

        used_pvs_ids = itertools.chain.from_iterable([vg['pvs'] for vg in
                                                      dict_scheme['vgs']])
        pvs_frequencies = [(k, len(list(group))) for k, group in
                           itertools.groupby(sorted(used_pvs_ids))]
        if any(x[1] > 1 for x in pvs_frequencies):
            failed_pvs = [x for x in pvs_frequencies if x[1] > 1]
            error = errors.WrongPartitionSchemeError(
                'Following pvs were used too many times: {0}'.format(failed_pvs)
            )
            LOG.exception(error)
            raise error

        vgs_names = [x['name'] for x in dict_scheme['vgs']]
        for lv in dict_scheme['lvs']:
            if lv['vgname'] not in vgs_names:
                error = errors.WrongPartitionSchemeError(
                    ('Logical volume {0} tries to use non-existent volume group'
                     ' with name {1}').format(lv['id'], lv['vgname']))
                LOG.exception(error)
                raise error

    def raise_error(self, message):
        error = errors.WrongPartitionSchemeError(message)
        LOG.exception(error)
        raise error
