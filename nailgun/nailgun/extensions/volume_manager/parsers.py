import copy
from oslo.serialization import jsonutils
import yaml

from fuel_agent import objects


class VolumesHumanFormatParser(object):

    @classmethod
    def from_path(cls, path):
        with open(path) as f:
            data = yaml.load(f)
        return cls(data)

    def __init__(self, data):
        self._data = data
        self.references = {}

    def is_valid(self):
        for validator in self.validators:
            validator(self.partition_scheme)

    @property
    def json(self):
        return jsonutils.dumps(self.parsed_dict)

    @property
    def yaml(self):
        return yaml.dumps(self.parsed_dict)

    @property
    def partition_scheme(self):
        if not hasattr(self, '_partition_scheme'):
            self.parse()

            p_scheme = objects.PartitionScheme()

            for key, klass in (
                ('lvs', objects.LV),
                ('pvs', objects.PV),
                ('fss', objects.FS),
                ('vgs', objects.VG),
                ('mds', objects.MD),
                ('parteds', objects.Parted),
            ):
                setattr(
                    p_scheme,
                    key,
                    [klass.from_dict(elem) for elem in self.parsed_dict[key]])

            self._partition_scheme = p_scheme

        return self._partition_scheme

    def parse(self):
        self.parsed_dict = {}
        self.data = copy.deepcopy(self._data)

        self.parse_mds()
        self.parse_parteds()
        self.parse_vgs_and_pvs()
        self.parse_lvs()
        self.parse_fss()

        return self.parsed_dict

    def parse_mds(self):
        mds = self.data.get('mds', [])

        for md in mds:
            md_id = md.pop('id')
            self.references["@{0}/{1}".format('md', md_id)] = md

        self.parsed_dict['mds'] = mds

    def parse_parteds(self):
        parteds = self.data.get('parteds', [])

        for parted in parteds:
            partitions = parted.pop('partitions', [])
            parted_id = parted.pop('id')
            parted['name'] = parted.pop('device')

            parted['partitions'] = []
            for partition in partitions:
                tmp_partition = {}
                device = partition.pop('device', None) or parted['name']

                if device.startswith("@"):
                    tmp_partition['device'] = self.references[device]['name']
                else:
                    tmp_partition['device'] = device

                partition_id = partition.pop('id')
                tmp_partition.update(partition)
                parted['partitions'].append(tmp_partition)

                self.references["@{0}/{1}/{2}".format(
                    'parteds',
                    parted_id,
                    partition_id)
                ] = tmp_partition

        self.parsed_dict['parteds'] = parteds

    def parse_vgs_and_pvs(self):
        pvs = self.data.get('pvs', [])
        for pv in pvs:
            if pv['device'].startswith('@'):
                device_ref = pv.pop('device')
                pv['name'] = self.references[device_ref]['device']
            else:
                pv['name'] = pv.pop('device')

        vgs = self.data.get('vgs', [])
        self.parsed_dict['vgs'] = []
        for vg in vgs:
            tmp_vg = {}
            tmp_vg['name'] = vg['name']
            tmp_vg['pvnames'] = []
            for pv_id in vg.get('pvs', []):
                pv = next((elem for elem in pvs if elem['id'] == pv_id), None)
                if pv is not None:
                    tmp_vg['pvnames'].append(pv['name'])

            self.parsed_dict['vgs'].append(tmp_vg)

        # Removing ids from pvs
        for pv in pvs:
            pv.pop('id')

        self.parsed_dict['pvs'] = pvs

    def parse_lvs(self):
        lvs = self.data.get('lvs', [])

        for lv in lvs:
            lv_id = lv.pop('id')
            self.references["@{0}/{1}".format('lvs', lv_id)] = lv

        self.parsed_dict['lvs'] = lvs

    def parse_fss(self):
        fss = self.data.get('fss', [])
        for fs in fss:
            if fs['device'].startswith('@'):
                device_ref = fs.pop('device')
                vg_name = self.references[device_ref]["vgname"]
                lv_name = self.references[device_ref]["name"]
                fs['device'] = "/dev/mapper/{0}-{1}".format(vg_name, lv_name)

            fs.pop('id')

        self.parsed_dict['fss'] = fss
