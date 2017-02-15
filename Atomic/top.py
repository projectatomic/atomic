from . import Atomic
from . import util
import argparse
import json as Json
import tty
import sys
import termios
import select
from os import isatty
from operator import itemgetter
import requests
from Atomic.backends._docker_errors import NoDockerDaemon

def check_negative(value):
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError("%s must be a positive integer value greater than 0." % value)
    return ivalue

def cli(subparser):
    # atomic top
    topp = subparser.add_parser("top",
                                help=_("Show top-like stats about processes running in containers"))
    topp.set_defaults(_class=Top, func='atomic_top')
    topp.add_argument("-d", type=int, default=1, help=_("Interval (secs) to refresh process information"))
    topp.add_argument("-o", "--optional", help=_("Additional fields to display"), nargs='?', action='append',
                      choices=['time', 'stime', 'ppid', 'uid', 'gid', 'user', 'group'])
    topp.add_argument("-n", help=_("Number of iterations"), type=check_negative)
    topp.add_argument("containers", nargs="*", help=_("list of containers to monitor, leave blank for all"))


class Top(Atomic):
    """
    Class to support atomic top; based on the Atomic class
    """
    # Set to true to output debug information

    def __init__(self):
        super(Top, self).__init__()
        self.input_var = None
        self._sort = 'CID'
        self.name_id = {}
        self.optional = None
        self.titles = None
        self.debug = False
        # To add a new column to the output, create a new dict inside self.headers
        # The fields are as follows:
        # shortname: <str> a unique key used to describe the dict
        # column: <str> column title, use parans to define a sort character
        # character: <str> a single character the user presses to sort on that column
        # sort: <bool> to determine IF the column can be sorted upon
        # index: <int> order the columns display left to right. Do not change 0-5
        # _field: <str> If the width of the column needs to be dynamically sized, put
        #               the formatting in _field, set field to None, and be sure to
        #               add a key for _min_width
        # field: <str> the preferred format for the column
        # active: if the column should be active by default
        # ps_opt: <str> the descriptor for ps to get the column's data (ps -o)
        # sort_order: <bool> True reverses the sort order from ascending to descending
        # _min_width: <int> Minimum field width if you are using dynamic fields
        self.headers = [
            {'shortname': '%CPU', 'column': '(C)PU', 'character': 'c', 'sort': True, 'index': 3,
             'field': '{:6}', 'active': True, 'ps_opt': 'pcpu', 'sort_order': True},
            {'shortname': 'CID', 'column': 'CONTA(I)NER', 'character': 'i', 'sort': True, 'index': 0,
             'field': '{:12.12}', 'active': True, 'ps_opt': None, 'sort_order': False},
            {'shortname': 'NAME', 'column': '(N)AME', 'character': 'n', 'sort': True, 'index': 1,
             '_field': '{:WIDTH}', 'field': None, 'active': True, 'ps_opt': None, 'sort_order': False,
             '_min_width': 10},
            {'shortname': 'PID', 'column': '(P)ID', 'character': 'p', 'sort': True, 'index': 2,
             'field': '{:<10}', 'active': True, 'ps_opt': 'pid', 'sort_order': False},
            {'shortname': '%MEM', 'column': '(M)EM', 'character': 'm', 'sort': True, 'index': 4,
             'field': '{:6}', 'active': True, 'ps_opt': 'pmem', 'sort_order': True},
            {'shortname': 'CMD', 'column': 'CMD', 'character': None, 'sort': False, 'index': 99,
             '_field': '{:WIDTH}', 'field': None, 'active': True, 'ps_opt': 'cmd', '_min_width': 10},
            {'shortname': 'TIME', 'column': '(T)IME', 'character': 't', 'sort': True, 'index': 6,
             'field': '{:10}', 'active': False, 'ps_opt': 'time', 'sort_order': True},
            {'shortname': 'STIME', 'column': '(S)TIME', 'character': 's', 'sort': True, 'index': 7,
             'field': '{:10}', 'active': False, 'ps_opt': 'stime', 'sort_order': True},
            {'shortname': 'PPID', 'column': 'PPI(D)', 'character': 'd', 'sort': True, 'index': 8,
             'field': '{:10}', 'active': False, 'ps_opt': 'ppid', 'sort_order': False},
            {'shortname': 'UID', 'column': '(U)ID', 'character': 'u', 'sort': True, 'index': 9,
             'field': '{:6}', 'active': True, 'ps_opt': 'uid', 'sort_order': True},
            {'shortname': 'GID', 'column': '(G)ID', 'character': 'g', 'sort': True, 'index': 10,
             'field': '{:6}', 'active': True, 'ps_opt': 'gid', 'sort_order': True},
            {'shortname': 'USER', 'column': 'USER', 'character': None, 'sort': False, 'index': 11,
             'field': '{:10}', 'active': False, 'ps_opt': 'user'},
            {'shortname': 'GROUP', 'column': 'GROUP', 'character': None, 'sort': False, 'index': 12,
             'field': '{:10}', 'active': False, 'ps_opt': 'group'}
        ]

    def _activate_optionals(self):
        """
        Sets the active bool to True for any optional  ps
        arguments.
        :return: None
        """
        if self.args.optional:
            for option in self.args.optional:
                for header in self.headers:
                    if header['ps_opt'] == option:
                        header['active'] = True

    def _set_dynamic_column_widths(self, ps_info):
        for header in self.headers:
            if '_field' in header:
                max_widths = [len(x[header['shortname']]) for x in ps_info]
                max_width = header['_min_width'] if not max_widths else max(max_widths)
                header['field'] = header['_field'].replace('WIDTH', str(max_width))

    def json(self):
        """
        Main sub-function for top
        :return: None
        """
        # Make sure the docker daemon is running
        self.ping()
        # Activate optional columns
        self._activate_optionals()
        proc_info = []
        if len(self.args.containers) < 1:
            try:
                con_ids = [x['Id'] for x in self.get_active_containers(refresh=True)]
            except requests.exceptions.ConnectionError:
                raise NoDockerDaemon()
        else:
            con_ids = []
            self.get_active_containers(refresh=True)
            # verify the inputs are valid
            for user_input in self.args.containers:
                con_ids.append(self.get_input_id(user_input))
        for cid in con_ids:
            proc_info += self.get_pids_by_container(cid)

        return Json.dumps(self.reformat_ps_info(proc_info))

    def atomic_top(self):
        """
        Main sub-function for top
        :return: None
        """
        # Make sure the docker daemon is running
        self.ping()
        # Set debug bool
        self.set_debug()
        # Activate optional columns
        self._activate_optionals()
        # Do we have a tty?
        # Can run ./atomic top <&- to replicate no tty
        has_tty = isatty(0)
        # Set up terminal, input handling
        if has_tty:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
        sort_vals = [x['character'].upper() for x in self.headers if x['active'] and x['sort']]
        counter = 0
        while True:
            proc_info = []
            if len(self.args.containers) < 1:
                try:
                    con_ids = [x['Id'] for x in self.get_active_containers(refresh=True)]
                except requests.exceptions.ConnectionError:
                    raise NoDockerDaemon()
            else:
                con_ids = []
                self.get_active_containers(refresh=True)
                # verify the inputs are valid
                for user_input in self.args.containers:
                    con_ids.append(self.get_input_id(user_input))
            for cid in con_ids:
                proc_info += self.get_pids_by_container(cid)
            # Reset screen
            if not self.debug and has_tty:
                util.write_out("\033c")
            sorted_info = self.reformat_ps_info(proc_info)
            self._set_dynamic_column_widths(sorted_info)
            self.output_top(sorted_info)
            if has_tty:
                tty.setraw(sys.stdin.fileno())
            i, _, _ = select.select([sys.stdin], [], [], self.args.d)
            if i and has_tty:
                ch = sys.stdin.read(1)
                # Detect 'q' or Cntrl-c
                if ch.upper() == 'q'.upper() or ord(ch) == 3:
                    # reset terminal
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    raise SystemExit
                # Detect of the character pushed is one in self.headers
                elif ch.upper() in sort_vals:
                    self._sort = next((header['shortname'] for header in self.headers if header['character'] is not
                                       None and header['character'].upper() == ch.upper()), False)

            # reset terminal
            if has_tty:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            counter += 1
            if counter == self.args.n:
                raise SystemExit

    def get_pids_by_container(self, con_id):
        """
        Call the custom API for docker python
        :param con_id: id of the container
        :return: dict
        """

        if len(self.active_containers) == 0:
            raise ValueError("No containers running")
        f_procs = []
        # Get the name of the container by ID
        con_name = str(next((l for l in self.active_containers if l['Id'].startswith(con_id)), None)['Names'][0])
        if con_name.startswith("/"):
            con_name = con_name.replace("/", "")
        # Assemble the ps args
        ps_args = [header['ps_opt']for header in sorted(self.headers, key=itemgetter('index')) if header['ps_opt']
                   is not None and header['active']]
        con_procs = self.d.top(con_id, ps_args="-eo {}".format(",".join(ps_args)))
        # Set the column header titles one-time
        if self.titles is None:
            self.titles = con_procs['Titles']

        if con_procs['Processes'] != None:
            # Massage the information into a dict
            for proc in con_procs['Processes']:
                t_dict = {'CID': con_id,
                          'NAME': con_name}
                for place in range(0, len(proc)):
                    t_dict[self.titles[place]] = proc[place]
                f_procs.append(t_dict)
        return f_procs

    def output_top(self, sorted_info):
        """
        Primary function for output to stdout
        :param sorted_info: list of dicts containing process information
        :return: None
        """
        cols = [col for col in sorted(self.headers, key=itemgetter('index')) if col['active']]
        active_column_names = [x['shortname'] for x in cols]
        out_format = " ".join([x['field'] for x in cols])
        col_headers = []

        # Add a '*' to the column header name currently being
        # sorted on
        for col in cols:
            title = col['column']
            if col['shortname'] == self._sort:
                title += "*"
            col_headers.append(title)
        formatted_col_headers = "\033[7m" + out_format.format(*col_headers) + "\033[0m"
        # output ATOMIC TOP title
        almost_center = len(formatted_col_headers)
        center_col = '{:^%WIDTH%}'.replace("%WIDTH%", str(almost_center))
        util.write_out(center_col.format("ATOMIC TOP\n"))
        # Output the headers
        util.write_out(formatted_col_headers)
        for ps in sorted_info:
            line_out = []
            for val in active_column_names:
                line_out.append(ps[val])
            # Output the ps information
            util.write_out(out_format.format(*line_out))

    def reformat_ps_info(self, proc_info):
        """
        Takes a structure of process information and re-organizes it into
        a list of dictionaries, where each dict is a process.
        :param proc_info:
        :return: a list of dicts
        """
        # Determine if the sort field needs to reverse the order of the sort
        _reverse = next((header['sort_order'] for header in self.headers if header['shortname'] == self._sort), False)
        if self.debug:
            util.write_out("sorting on {0} and reverse is {1}".format(self._sort, _reverse))
        return sorted(proc_info, key=itemgetter(self._sort), reverse=_reverse)




