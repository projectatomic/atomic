from . import Atomic
from . import mount
from . import util
from datetime import datetime
import os
from shutil import rmtree
import json
import sys
from Atomic.backendutils import BackendUtils

def cli(subparser):
    # atomic scan
    scanners = util.get_scanners()
    scanp = subparser.add_parser(
        "scan", help=_("scan an image or container for CVEs or configuration compliance"),
        epilog="atomic scan <input> scans a container or image for CVEs or configuration compliance")
    scanp.set_defaults(_class=Scan, func='scan')
    scan_group = scanp.add_mutually_exclusive_group()
    scanp.add_argument("scan_targets", nargs='*', help=_("container image"))
    scanp.add_argument("--scanner", choices=[x['scanner_name'] for x in scanners], default=None, help=_("define the intended scanner"))
    scanp.add_argument("--scan_type", default=None, help=_("define the intended scan type"))
    scanp.add_argument("--list", action='store_true', default=False, help=_("List available scanners"))
    scanp.add_argument("--scanner_args", default=None, help=_("Specify arguments to be passed to the scanner"))
    disp_group = scanp.add_mutually_exclusive_group()
    disp_group.add_argument("--verbose", action='store_true', default=False, help=_("Show more output from scanning container"))
    disp_group.add_argument("--json", action='store_true', default=False, help=_("Output results in JSON format"))
    scan_group.add_argument("--rootfs", nargs='?', default=[], action='append', help=_("Rootfs path to scan"))
    scan_group.add_argument("--all", default=False, action='store_true', help=_("scan all images (excluding intermediate layers) and containers"))
    scan_group.add_argument("--images", default=False, action='store_true', help=_("scan all images (excluding intermediate layers)"))
    scan_group.add_argument("--containers", default=False, action='store_true', help=_("scan all containers"))


class Scan(Atomic):
    """
    Scan class that can generically work any scanner
    """


    def __init__(self):
        super(Scan, self).__init__()
        self.scan_dir = None
        self.scan_list = []
        self.rootfs_paths = []
        self.cur_time = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
        self.chroot_dir = '/run/atomic/{}'.format(self.cur_time)
        self.results_dir = None
        self.scan_content = {}
        self.atomic_config = util.get_atomic_config()
        self.scanners = util.get_scanners()
        self.debug = False
        self.rootfs_mappings = {}
        self.scanner = None
        self.mount_paths = {}

    def get_scanners_list(self):
        return self.scanners

    def scan(self):
        def get_scan_info(scanner, scan_type):
            for i in self.scanners:
                if i['scanner_name'] == scanner:
                    for x in i['scans']:
                        if x['name'] == scan_type:
                            return i['image_name'], x['args'], i.get('custom_args')

        def set_scanner():
            # If no scanners are defined
            if len(self.scanners) == 0:
                raise ValueError("No scanners are configured for your system.")

            if self.args.scanner:
                self.scanner = self.args.scanner
            elif len(self.scanners) == 1:
                self.scanner = self.scanners[0]['scanner_name']
            # Use default
            else:
                self.scanner = self.atomic_config['default_scanner']

            if self.scanner is None:
                raise ValueError("You must specify a scanner (--scanner) or set a default in /etc/atomic.conf")

            # Check if the scanner name is valid
            if self.scanner not in [x['scanner_name'] for x in self.scanners]:
                raise ValueError("Unknown scanner '{}' defined in {}".format(self.scanner, util.ATOMIC_CONF))

        def get_additional_args():
            if self.args.scanner_args is None:
                return []
            additional_args = []
            for pair in self.args.scanner_args.split(","):
                key, _, value = pair.partition("=")
                additional_args.append("--" + key.strip())
                if value:
                    additional_args.append(value.strip())
            return additional_args

        if self.args.debug:
            self.debug = True

        # Set debug bool
        self.set_debug()

        # Show list of scanners and exit
        if self.args.list:
            self.print_scan_list()

        set_scanner()

        scan_type = self.get_scan_type()

        # Load the atomic config file and check scanner settings
        yaml_error = "The image name or scanner arguments for '{}' is not " \
                     "defined in /etc/atomic.conf".format(self.scanner)

        scanner_image_name, scanner_args, custom_args = get_scan_info(self.scanner, scan_type)

        if not isinstance(scanner_args, list):
            raise ValueError("The scanner arguments for {} must be in list"
                             " ([]) form.".format(self.scanner))

        if None in [scanner_image_name, scanner_args]:
            raise ValueError(yaml_error)

        self.results_dir = os.path.join(self.results, self.scanner, self.cur_time)

        # Create the input directory
        if not os.path.exists(self.chroot_dir):
            os.makedirs(self.chroot_dir)
        if self.debug:
            util.write_out("Created {}".format(self.chroot_dir))

        if len(self.args.rootfs) == 0:
            self.scan_list = self._get_scan_list()
            security_args = []
        else:
            # Check to make sure all the chroots provided are legit
            for _path in self.args.rootfs:
                if not os.path.exists(_path):
                    raise ValueError("The path {} does not exist".format(_path))
            self.setup_rootfs_dirs()
            # Have to disable SELinux checking of scanning not docker images
            security_args = [ "--security-opt", "label:disable" ]

        # Create the output directory
        os.makedirs(self.results_dir)

        docker_args = ['docker', 'run', '-t', '--rm', '-v', '/etc/localtime:/etc/localtime',
                       '-v', '{}:{}'.format(self.chroot_dir, '/scanin'), '-v',
                       '{}:{}:rw,Z'.format(self.results_dir, '/scanout')]

        # Assemble the cmd line for the scan
        scan_cmd = docker_args + security_args
        if custom_args is not None:
            scan_cmd = scan_cmd + custom_args
        scan_cmd = scan_cmd + [scanner_image_name] + scanner_args + get_additional_args()
        scan_cmd = self.sub_env_strings(" ".join(scan_cmd))

        # Show the command being run
        if self.useTTY and not self.args.json:
            util.write_out(scan_cmd)

        # Show stdout from container if --debug or --verbose
        stdout = None if (self.args.verbose or self.args.debug) else open(os.devnull, 'w')

        try:
            if len(self.args.rootfs) == 0:
                # mount all the rootfs
                self._mount_scan_rootfs(self.scan_list)

                if self.debug:
                    util.write_out("Creating the output dir at {}".format(self.results_dir))

            # do the scan
            util.check_call(scan_cmd, stdout=stdout, env=self.cmd_env())

            # output results
            if self.useTTY:
                self.output_results()

            # record environment
            self.record_environment()

            self.write_persistent_data()
        finally:
            # unmount all the rootfs
            self._unmount_rootfs_in_dir()

        if not self.useTTY:
            return (json.dumps(self.get_scan_data()))


        for json_file in self._get_json_files():
            json_results = json.load(open(json_file))
            if json_results['Successful'].upper() != 'TRUE':
                return 1
        return 0

    def _get_scan_list(self):
        beu = BackendUtils()
        if self.args.images:
            scan_list = beu.get_images()
        elif self.args.containers:
            scan_list = beu.get_containers()
        elif self.args.all:
            scan_list = beu.get_images() + beu.get_containers()
        else:
            scan_list = []
            for scan_target in self.args.scan_targets:
                try:
                    # get_backend_and_container throws a ValueError when it cannot find anything
                    _, scan_obj = beu.get_backend_and_container_obj(scan_target)
                except ValueError:
                    try:
                        # get_backend_and_image throws a ValueError when it cannot find anything
                        _, scan_obj = beu.get_backend_and_image_obj(scan_target)
                    except ValueError:
                        raise ValueError("Unable to locate the container or image '{}' locally. Check the "
                                         "input name for typos or pull the image first.".format(scan_target))
                scan_list.append(scan_obj)
        return scan_list

    def _get_roots_path_from_bind_name(self, in_bind_name):
        for _path, bind_path in self.rootfs_mappings.items():
            if bind_path == os.path.basename(os.path.split(in_bind_name)[0]):
                return _path

    def get_scan_data(self):
        results = []
        json_files = self._get_json_files()
        for json_file in json_files:
            results.append(json.load(open(json_file)))
        return results

    def _mount_scan_rootfs(self, scan_list):
        for docker_object in scan_list:
            mount_path = os.path.join(self.chroot_dir, docker_object.id.replace("/", "_"))
            os.mkdir(mount_path)
            if self.debug:
                util.write_out("Created {}".format(mount_path))
            new_mount_path = self.mount(mountpoint=mount_path, image=docker_object.id)
            if new_mount_path != mount_path:
                rmtree(mount_path)
                os.symlink(new_mount_path, mount_path)
            self.mount_paths[new_mount_path.rstrip('/')] = docker_object.id
            if self.debug:
                util.write_out("Mounted {} to {}".format(docker_object.id, mount_path))

    def _unmount_rootfs_in_dir(self):
        for rootfs_dir in self.get_rootfs_paths():
            if len(self.args.rootfs) == 0:
                try:
                    self.unmount(rootfs_dir)
                except (ValueError, mount.MountError):
                    pass
            else:
                # Clean up bind mounts if the chroot feature is used
                mcmd = ['umount', rootfs_dir]
                util.check_call(mcmd)

            # Clean up temporary containers
            if not self.debug:
                # Remove the temporary container dirs
                rmtree(rootfs_dir)
            else:
                util.write_out("Unmounted {}".format(rootfs_dir))
        if not self.debug:
            rmtree(self.chroot_dir)

    def get_rootfs_paths(self):
        """
        Returns the list of rootfs paths (not fully qualified)
        :return: list
        """
        return self.mount_paths.keys()

    def output_results(self):
        """
        Write results of the scan to stdout
        :return: None
        """
        json_files = self._get_json_files()
        for json_file in json_files:
            json_results = json.load(open(json_file))
            if self.args.json:
                util.output_json(json_results)
            else:
                uuid = next(self.mount_paths[x] for x in self.mount_paths.keys() if
                            os.path.basename(json_results['UUID'].rstrip('/')) in x) if len(self.args.rootfs) == 0 \
                    else self._get_roots_path_from_bind_name(json_file)

                name1 = uuid if len(self.args.rootfs) > 1 else self._get_input_name_for_id(uuid)
                if len(self.args.rootfs) == 0 and not self._is_iid(uuid):
                    name2 = uuid[:15]
                else:
                    # Containers do not have repo names
                    if len(self.args.rootfs) == 0 and uuid not in [x['Id'] for x in self.get_containers()]:
                        name2 = self._get_repo_names(uuid)
                    else:
                        name2 = uuid[:15]
                util.write_out("\n{} ({})\n".format(name1, name2))
                if json_results['Successful'].upper() == "TRUE":
                    if 'Custom' in json_results:
                        self._output_custom(json_results['Custom'], 3)
                    if 'Vulnerabilities' in json_results and len(json_results['Vulnerabilities']) > 0:
                        util.write_out("The following issues were found:\n")
                        for vul in json_results['Vulnerabilities']:
                            if 'Title' in vul:
                                util.write_out("{}{}".format(' ' * 5, vul['Title']))
                            if 'Severity' in vul:
                                util.write_out("{}Severity: {}".format(' ' * 5, vul['Severity']))
                            if 'Custom' in vul.keys() and len(vul['Custom']) > 0:
                                custom_field = vul['Custom']
                                self._output_custom(custom_field, 7)
                            util.write_out("")
                    elif 'Results' in json_results and len(json_results['Results']) > 0:
                        util.write_out("The following results were found:\n")
                        for result in json_results['Results']:
                            if 'Custom' in result.keys() and len(result['Custom']) > 0:
                                custom_field = result['Custom']
                                self._output_custom(custom_field, 7)
                        util.write_out("")
                    else:
                        util.write_out("{} passed the scan".format(self._get_input_name_for_id(uuid)))
                else:
                    util.write_out("{}{} is not supported for this scan."
                                   .format(' ' * 5, self._get_input_name_for_id(uuid)))
        if not self.args.json:
            util.write_out("\nFiles associated with this scan are in {}.\n".format(self.results_dir))

    def _output_custom(self, value, indent):
        space = ' ' * indent
        next_indent = indent + 2
        if isinstance(value, dict):
            for x in value:
                if isinstance(value[x], dict):
                    util.write_out("{}{}:".format(space, x))
                    self._output_custom(value[x], next_indent)
                elif isinstance(value[x], list):
                    util.write_out("{}{}:".format(space, x))
                    self._output_custom(value[x], next_indent)
                else:
                    util.write_out("{}{}: {}".format(space, x, value[x]))
        elif isinstance(value, list):
            for x in value:
                if isinstance(x, dict):
                    self._output_custom(x, next_indent)
                elif isinstance(x, list):
                    self._output_custom(x, next_indent)
                else:
                    util.write_out('{}{}'.format(space, x))

    def _get_json_files(self):
        json_files = []
        for files in os.walk(self.results_dir):
            for jfile in files[2]:
                if jfile == 'json':
                    json_files.append(os.path.join(files[0], jfile))
        return json_files


    def _get_object_by_id(self, iid):
        scan_obj = next((x for x in self.scan_list if x.id == iid))
        return scan_obj

    def _get_input_name_for_id(self, iid):
        if len(self.args.rootfs) > 0:
            return iid
        else:
            return self._get_object_by_id(iid).input_name

    def _is_iid(self, input_name):
        scan_obj = next((x for x in self.scan_list if x.id == input_name))
        if scan_obj.id == scan_obj.input_name:
            return True
        return False

    def _get_repo_names(self, docker_id):
        _match = next((x for x in self.get_images() if x['Id'] == docker_id), None)
        if _match is None:
            _match = next((x for x in self.get_containers() if x['Id'] == docker_id), None)
        if'<none>' in _match['RepoTags'][0]:
            return docker_id[:15]
        else:
            return ', '.join(_match['RepoTags'])

    def record_environment(self):
        """
        Grabs a "snapshot" the results of docker info and inspect results for
        all images and containers.  Write it to results_dir/environment.json
        :return: None
        """

        environment = {}
        environment['info'] = self.d.info()
        environment['images'] = []
        for iid in [x['Id'] for x in self.get_images()]:
            environment['images'].append(self._inspect_image(image=iid))

        environment['containers'] = []
        for cid in [x['Id'] for x in self.get_containers()]:
            environment['containers'].append(self._inspect_container(name=cid))

        with open(os.path.join(self.results_dir, 'environment.json'), 'w') as f:
            json.dump(environment, f, indent=4, separators=(',', ': '))

    def get_scan_type(self):
        default_scan_type = None
        scan_types = []
        for i in self.scanners:
            if i['scanner_name'] == self.scanner:
                default_scan_type = i.get('default_scan')
                if self.args.scan_type is None and default_scan_type is None:
                    raise ValueError("No scan type was given and there is no "
                                     "default scan type defined for '{}'".format(self.args.scanner))
                for x in i['scans']:
                    scan_types.append(x['name'])
        if default_scan_type not in scan_types:
            raise ValueError("The default scan type '{}' is not defined as a valid scan type for "
                             "the scanner '{}'".format(default_scan_type, self.scanner))
        if self.args.scan_type is None:
            return default_scan_type
        elif self.args.scan_type in scan_types:
            return self.args.scan_type
        else:
            raise ValueError("Unable to find the scan type '{}' for '{}'.".
                             format(self.args.scan_type, self.scanner))

    def print_scan_list(self):
        if len(self.scanners) == 0:
            util.write_out("There are no scanners configured for this system.")
            sys.exit(0)
        default_scanner = self.atomic_config['default_scanner']
        if default_scanner is None:
            default_scanner = ''
        for scanner in self.scanners:
            scanner_name = scanner['scanner_name']
            df = '* ' if scanner_name == default_scanner else ''
            default_scan_type = scanner.get('default_scan')
            if default_scan_type is None:
                raise ValueError("Invalid configuration file: At least one scan type must be "
                                 "declared as the default for {}.".format(scanner_name))
            util.write_out("Scanner: {} {}".format(scanner_name, df))
            util.write_out("{}Image Name: {}".format(" " * 2, scanner['image_name']))
            for scan_type in scanner['scans']:
                df = '* ' if default_scan_type == scan_type['name'] else ''
                util.write_out("{}Scan type: {} {}".format(" " * 5, scan_type['name'], df))
                util.write_out("{}Description: {}\n".format(" " * 5, scan_type['description']))
        util.write_out("\n* denotes defaults")
        sys.exit(0)

    def mount(self, mountpoint, image):
        m = mount.Mount()
        m.set_args(self.args)
        m.mountpoint = mountpoint
        m.image = image
        m.shared = True
        m.mount(best_mountpoint_for_storage=True)
        return m.mountpoint

    def unmount(self, mountpoint):
        m = mount.Mount()
        m.set_args(self.args)
        m.mountpoint = mountpoint
        m.unmount()

    def setup_rootfs_dirs(self):
        for _dir in self.args.rootfs:
            bind_dir = _dir.replace("/", "_")
            chroot_scan_dir = os.path.join(self.chroot_dir, bind_dir)
            os.mkdir(chroot_scan_dir)
            mcmd = ['mount', '-o', 'ro,bind', _dir, chroot_scan_dir]
            util.check_call(mcmd)
            self.rootfs_mappings[_dir] = bind_dir

    def get_persist_data(self, json_results, json_file):
        persist = {}
        if json_results.get('Successful').upper() == "FALSE":
            return {}
        persist['UUID'] = json_results['UUID'].replace("/scanin/", "")
        persist['Scanner'] = json_results['Scanner']
        persist['Time'] = json_results['Time']
        persist['Scan Type'] = json_results['Scan Type']
        if 'Vulnerabilities' in json_results and len(json_results['Vulnerabilities']) > 0:
            persist["Vulnerable"] =  True
        elif json_results.get('Vulnerable') is True:
            persist["Vulnerable"] =  True
        else:
            persist["Vulnerable"] =  False
        persist['json_file'] = json_file
        return persist


    def write_persistent_data(self):
        new_data = dict()
        json_files = self._get_json_files()
        for json_file in json_files:
            json_results = json.load(open(json_file))
            uuid = os.path.basename(json_results['UUID']) if len(self.args.rootfs) == 0 \
                else self._get_roots_path_from_bind_name(json_file)
            new_data[uuid] = self.get_persist_data(json_results, json_file)
        summary_file = os.path.join(self.results, "scan_summary.json")
        if not os.path.exists(summary_file):
            persistent_data = new_data
        else:
            persistent_data = json.loads(open(summary_file, "r").read())
            iids = [x['Id'] for x in self.get_images()]
            cids = [x['Id'] for x in self.get_containers()]
            for uuid in new_data.keys():
                if len(new_data[uuid]) > 0:
                    persistent_data[uuid] = new_data[uuid]

            # Clean up old data
            for uuid in list(persistent_data):
                if uuid not in iids and uuid not in cids:
                    del persistent_data[uuid]

        with open(summary_file, 'w') as f:
            json.dump(persistent_data, f, indent=4)
