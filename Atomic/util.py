import shlex
import sys
import json
import subprocess
import collections
from fnmatch import fnmatch as matches
import os
import selinux
from .client import get_docker_client
"""Atomic Utility Module"""

ReturnTuple = collections.namedtuple('ReturnTuple',
                                     ['return_code', 'stdout', 'stderr'])

if sys.version_info[0] < 3:
    input = raw_input
else:
    input = input


def _decompose(compound_name):
    """ '[reg/]repo[:tag]' -> (reg, repo, tag) """
    reg, repo, tag = '', compound_name, ''
    if '/' in repo:
        reg, repo = repo.split('/', 1)
    if ':' in repo:
        repo, tag = repo.rsplit(':', 1)
    return reg, repo, tag

def image_by_name(img_name, images=None):
    """
    Returns a list of image data for images which match img_name. Will
    optionally take a list of images from a docker.Client.images
    query to avoid multiple docker queries.
    """
    i_reg, i_rep, i_tag = _decompose(img_name)

    # Correct for bash-style matching expressions.
    if not i_reg:
        i_reg = '*'
    if not i_tag:
        i_tag = '*'

    # If the images were not passed in, go get them.
    if images is None:
        c = get_docker_client()
        images = c.images(all=False)

    valid_images = []
    for i in images:
        for t in i['RepoTags']:
            reg, rep, tag = _decompose(t)
            if matches(reg, i_reg) \
                    and matches(rep, i_rep) \
                    and matches(tag, i_tag):
                valid_images.append(i)
                break
            # Some repo after decompose end up with the img_name
            # at the end.  i.e. rhel7/rsyslog
            if rep.endswith(img_name):
                valid_images.append(i)
                break
    return valid_images


def subp(cmd):
    """
    Run a command as a subprocess.
    Return a triple of return code, standard out, standard err.
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out, err = proc.communicate()
    return ReturnTuple(proc.returncode, stdout=out, stderr=err)


def check_call(cmd, env=os.environ, stderr=None, stdout=None):
    # Make sure cmd is a list
    if not isinstance(cmd, list):
        cmd = shlex.split(cmd)
    return subprocess.check_call(cmd, env=env, stderr=stderr, stdout=stdout)

def default_container_context():
    if selinux.is_selinux_enabled() != 0:
        fd = open(selinux.selinux_lxc_contexts_path())
        for i in fd.readlines():
            name, context = i.split("=")
            if name.strip() == "file":
                return context.strip("\n\" ")
    return ""


def writeOut(output, lf="\n"):
    sys.stdout.flush()
    sys.stdout.write(str(output) + lf)


def output_json(json_data):
    ''' Pretty print json data '''
    writeOut(json.dumps(json_data, indent=4, separators=(',', ': ')))


def print_scan_summary(json_data, names=None):
    '''
    Print a summary of the data returned from a
    CVE scan.
    '''
    max_col_width = 50
    min_width = 15

    def _max_width(data):
        max_name = 0
        for name in data:
            max_name = len(data[name]) if len(data[name]) > max_name \
                else max_name
        # If the max name length is less that max_width
        if max_name < min_width:
            max_name = min_width

        # If the man name is greater than the max col leng
        # we wish to use
        if max_name > max_col_width:
            max_name = max_col_width

        return max_name

    clean = True

    if len(names) > 0:
        max_width = _max_width(names)
    else:
        max_width = min_width
    template = "{0:" + str(max_width) + "}   {1:5} {2:5} {3:5} {4:5}"
    sevs = ['critical', 'important', 'moderate', 'low']
    writeOut(template.format("Container/Image", "Cri", "Imp", "Med", "Low"))
    writeOut(template.format("-" * max_width, "---", "---", "---", "---"))
    res_summary = json_data['results_summary']
    for image in res_summary.keys():
        image_res = res_summary[image]
        if 'msg' in image_res.keys():
            tmp_tuple = (image_res['msg'], "", "", "", "")
        else:
            if len(names) < 1:
                image_name = image[:max_width]
            else:
                image_name = names[image][-max_width:]
                if len(image_name) == max_col_width:
                    image_name = '...' + image_name[-(len(image_name)-3):]

            tmp_tuple = tuple([image_name] +
                              [str(image_res[sev]) for sev in sevs])
            sev_results = [image_res[sev] for sev in
                           sevs if image_res[sev] > 0]
            if len(sev_results) > 0:
                clean = False
        writeOut(template.format(*tmp_tuple))
    writeOut("")
    return clean


def print_detail_scan_summary(json_data, names=None):
    '''
    Print a detailed summary of the data returned from
    a CVE scan.
    '''
    clean = True
    sevs = ['Critical', 'Important', 'Moderate', 'Low']
    cve_summary = json_data['host_results']
    image_template = "  {0:10}: {1}"
    cve_template = "     {0:10}: {1}"
    for image in cve_summary.keys():
        image_res = cve_summary[image]
        writeOut("")
        writeOut(image[:12])
        if not image_res['isRHEL']:
            writeOut(image_template.format("Result",
                                           "Not based on Red Hat"
                                           "Enterprise Linux"))
            continue
        else:
            writeOut(image_template.format("OS", image_res['os'].rstrip()))
            scan_results = image_res['cve_summary']['scan_results']

        for sev in sevs:
            if sev in scan_results:
                clean = False
                writeOut(image_template.format(sev,
                                               str(scan_results[sev]['num'])))
                for cve in scan_results[sev]['cves']:
                        writeOut(cve_template.format("CVE", cve['cve_title']))
                        writeOut(cve_template.format("CVE URL",
                                                     cve['cve_ref_url']))
                        writeOut(cve_template.format("RHSA ID",
                                                     cve['rhsa_ref_id']))
                        writeOut(cve_template.format("RHSA URL",
                                                     cve['rhsa_ref_url']))
                        writeOut("")
    return clean

def get_mounts_by_path():
    '''
    Gets all mounted devices and paths
    :return: dict of mounted devices and related information by path
    '''
    mount_info = []
    f = open('/proc/mounts', 'r')
    for line in f:
        _tmp = line.split(" ")
        mount_info.append({'path': _tmp[1],
                           'device': _tmp[0],
                           'type': _tmp[2],
                           'options': _tmp[3]
                           }
                          )
    return mount_info

def is_dock_obj_mounted(docker_obj):
    '''
    Check if the provided docker object, which needs to be an ID,
    is currently mounted and should be considered "busy"
    :param docker_obj: str, must be in ID format
    :return: bool True or False
    '''
    mount_info = get_mounts_by_path()
    devices = [x['device'] for x in mount_info]
    # If we can find the ID of the object in the list
    # of devices which comes from mount, safe to assume
    # it is busy.
    return any(docker_obj in x for x in devices)


def urllib3_disable_warnings():
    if not 'requests' in sys.modules:
        import requests
    else:
        requests = sys.modules['requests']

    # On latest Fedora, this is a symlink
    if hasattr(requests, 'packages'):
        requests.packages.urllib3.disable_warnings() #pylint: disable=maybe-no-member
    else:
        # But with python-requests-2.4.3-1.el7.noarch, we need
        # to talk to urllib3 directly
        have_urllib3 = False
        try:
            if not 'urllib3' in sys.modules:
                import urllib3
                have_urllib3 = True
        except ImportError as e:
            pass
        if have_urllib3:
            # Except only call disable-warnings if it exists
            if hasattr(urllib3, 'disable_warnings'):
                urllib3.disable_warnings()


def skopeo(image):
    """
    Performs remote inspection of an image on a registry
    :param image:  fully qualified name
    :return: Returns json formatted data
    """

    cmd = ['/usr/bin/skopeo', image]
    results = subp(cmd)
    if results.return_code is not 0:
        raise ValueError(results.stderr)
    else:
        return json.loads(results.stdout.decode('utf-8'))

class NoDockerDaemon(Exception):
    def __init__(self):
        Exception.__init__(self, "The docker daemon does not appear to be running.")

class DockerObjectNotFound(ValueError):
    def __init__(self, msg):
        Exception.__init__(self, "Unable to associate '{}' with an image or container".format(msg))
