import collections
import docker
import selinux
import subprocess
import sys
from fnmatch import fnmatch as matches
import json

"""Atomic Utility Module"""

ReturnTuple = collections.namedtuple('ReturnTuple',
                                     ['return_code', 'stdout', 'stderr'])

if sys.version_info[0] < 3:
    input = raw_input
else:
    input = input


def image_by_name(img_name):
    """
    Returns a list of image data for images which match img_name.
    """
    def _decompose(compound_name):
        """ '[reg/]repo[:tag]' -> (reg, repo, tag) """
        reg, repo, tag = '', compound_name, ''
        if '/' in repo:
            reg, repo = repo.split('/', 1)
        if ':' in repo:
            repo, tag = repo.rsplit(':', 1)
        return reg, repo, tag

    c = docker.Client()

    i_reg, i_rep, i_tag = _decompose(img_name)
    # Correct for bash-style matching expressions.
    if not i_reg:
        i_reg = '*'
    if not i_tag:
        i_tag = '*'

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


def print_scan_summary(json_data):
    '''
    Print a summary of the data returned from a
    CVE scan.
    '''
    clean = True
    template = "{0:15}   {1:5} {2:5} {3:5} {4:5}"
    sevs = ['critical', 'important', 'moderate', 'low']
    writeOut(template.format("Container/Image", "Cri", "Imp", "Med", "Low"))
    writeOut(template.format("---------------", "---", "---", "---", "---"))
    res_summary = json_data['results_summary']
    for image in res_summary.keys():
        image_res = res_summary[image]
        if 'msg' in image_res.keys():
            tmp_tuple = (image_res['msg'], "", "", "", "")
        else:
            tmp_tuple = tuple([image[:12]] +
                              [str(image_res[sev]) for sev in sevs])
            sev_results = [image_res[sev] for sev in
                           sevs if image_res[sev] > 0]
            if len(sev_results) > 0:
                clean = False
        writeOut(template.format(*tmp_tuple))
    writeOut("")
    return clean


def print_detail_scan_summary(json_data):
    '''
    Print a detailed summary of the data returned from
    a CVE scan.
    '''
    sevs = ['Critical', 'Important', 'Moderate', 'Low']
    cve_summary = json_data['host_results']
    image_template = "  {0:10}: {1}"
    cve_template = "     {0:10}: {1}"
    for image in cve_summary.keys():
        image_res = cve_summary[image]
        writeOut("")
        writeOut(image[:12])
        if not image_res['isRHEL']:
            writeOut(image_template.format(
                  "Result", "Not based on Red Hat Enterprise Linux"))
            continue
        else:
            writeOut(image_template.format("OS", image_res['os'].rstrip()))
            scan_results = image_res['cve_summary']['scan_results']

        for sev in sevs:
            if sev in scan_results:
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
