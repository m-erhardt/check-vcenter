#!/usr/bin/env python3
"""
###############################################################################
# check_vcenter.py
# Icinga/Nagios plugin that checks a VMware vCenter
#
# Author        : Mauno Erhardt <mauno.erhardt@burkert.com>
# Copyright     : (c) 2022 Burkert Fluid Control Systems
# Source        : https://github.com/m-erhardt/check-vcenter
# License       : GPLv3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
###############################################################################
"""

import sys
import json
from argparse import ArgumentParser, Namespace as Arguments
from requests import request, ConnectTimeout
from urllib3.exceptions import NewConnectionError, MaxRetryError


class VCenterAPISession:
    """ class for storing properties of a vCenter API session """

    def __init__(self, args: Arguments):
        """ Get vCenter API session """

        self.baseurl: str = args.baseurl
        self.cacert: str = args.cacert
        self.timeout: int = args.timeout
        self.debug: bool = args.debug

        # Set request headers
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            # Query API
            req = request('POST',
                          f'{ self.baseurl }/api/session',
                          headers=headers,
                          timeout=self.timeout,
                          verify=self.cacert,
                          auth=(args.user, args.pw))
        except (ConnectionError, ConnectTimeout, NewConnectionError, MaxRetryError, OSError) as err:
            exit_plugin(3, f'Connection error: {err}', '')

        if req.status_code in [200, 201]:
            # If API call was sucessfull return session token
            self.__authtoken = req.text.strip('"')

        else:
            # Request unsuccessful
            exit_plugin(3,
                        (f'Error during API auth request: '
                         f'HTTP status {req.status_code} : {req.text}'),
                        '')

    def destroy(self):
        """ Destroy vCenter API session """

        # Set request headers
        headers = {"vmware-api-session-id": self.__authtoken,
                   "Content-Type": "application/x-www-form-urlencoded"}

        try:
            # Query API
            req = request('DELETE',
                          f'{ self.baseurl }/api/session',
                          headers=headers,
                          timeout=self.timeout,
                          verify=self.cacert)

        except (ConnectionError, ConnectTimeout, NewConnectionError, MaxRetryError, OSError) as err:
            exit_plugin(3, f'Connection error: {err}', '')

        if req.status_code not in [200, 201, 204]:
            exit_plugin(3,
                        (f'Error during token invalidation request: '
                         f'HTTP status {req.status_code} : {req.text}'),
                        '')

        del self

    def query_api_endpoint(self, method: str, endpoint: str, headers: dict = None):
        """ query API endpoint and return json result """

        if headers is None:
            # request headers not explicitely set, set default headers
            headers = {"Content-Type": "application/x-www-form-urlencoded"}

        # Add auth token header
        headers.update({"vmware-api-session-id": self.__authtoken})

        try:
            # Query API
            req = request(method,
                          f'{ self.baseurl }{ endpoint }',
                          headers=headers,
                          timeout=self.timeout,
                          verify=self.cacert)

        except (ConnectionError, ConnectTimeout, NewConnectionError, MaxRetryError, OSError) as err:
            exit_plugin(3, f'Connection error: {err}', '')

        if req.status_code in [400, 401, 403, 500, 503]:
            exit_plugin(3,
                        (f'Error during API request to /api/vcenter/vm : '
                         f'HTTP status {req.status_code} : {req.text}'),
                        '')

        return req.json()


def get_args():
    """ Parse Arguments """
    parser = ArgumentParser(
                 description="Icinga/Nagios that checks a VMware vCenter via the \
                              vSphere Automation API")
    parser.add_argument("-m", "--mode", required=True,
                        help="Query mode",
                        type=str, dest='mode',
                        choices=["vms", "hosts", "datastores"],
                        default="vms")
    parser.add_argument("-u", "--user", required=True,
                        help="Username for vCenter",
                        type=str, dest='user')
    parser.add_argument("-p", "--pass", required=True,
                        help="Password for vCenter",
                        type=str, dest='pw')
    parser.add_argument("--url", required=True,
                        help="Base URL of vCenter",
                        type=str, dest='baseurl')
    parser.add_argument("-t", "--timeout", required=False,
                        help="API timeout in seconds",
                        type=int, default=10, dest='timeout')
    parser.add_argument("--cacert", required=False,
                        help="Path to CA certificate file",
                        default="/etc/ssl/certs/ca-bundle.crt",
                        type=str, dest='cacert')
    parser.add_argument('--debug', dest='debug', action='store_true',
                        help="Print debug information",
                        default=False)
    args = parser.parse_args()
    return args


def exit_plugin(returncode, output, perfdata):
    """ Check status and exit accordingly """
    if returncode == 3:
        print("UNKNOWN - " + str(output))
        sys.exit(3)
    if returncode == 2:
        print("CRITICAL - " + str(output) + str(perfdata))
        sys.exit(2)
    if returncode == 1:
        print("WARNING - " + str(output) + str(perfdata))
        sys.exit(1)
    elif returncode == 0:
        print("OK - " + str(output) + str(perfdata))
        sys.exit(0)


def set_state(newstate: int, state: int):
    """ Set return state of plugin """

    if (newstate == 2) or (state == 2):
        returnstate = 2
    elif (newstate == 1) and (state not in [2]):
        returnstate = 1
    elif (newstate == 3) and (state not in [1, 2]):
        returnstate = 3
    else:
        returnstate = 0

    return returnstate


def check_vms(session: VCenterAPISession):
    """ Check state of virtual machines in vCenter """

    # Query API endpoint
    data = session.query_api_endpoint('GET', '/api/vcenter/vm')

    # Print full API response in debug mode
    if session.debug is True:
        print(json.dumps(data, indent=4))

    # Invalidate session token
    session.destroy()

    # Initiate cumulative state dict
    states = {'total': 0, 'on': 0, 'off': 0, 'suspended': 0}

    # Get total number of VMs
    states['total'] = len(data)

    for element in data:
        # Loop through vms
        if element["power_state"] == 'POWERED_ON':
            states['on'] += 1
        if element["power_state"] == 'POWERED_OFF':
            states['off'] += 1
        if element["power_state"] == 'SUSPENDED':
            states['suspended'] += 1

    # Construct perfdata string
    perfdata = (f" | \'vm_on\'={states['on']};;;0;{states['total']} "
                f"\'vm_off\'={states['off']};;;0;{states['total']} "
                f"\'vm_suspended\'={states['suspended']};;;0;{states['total']} "
                f"\'vm_total\'={states['total']};;;;")

    # Construct output string
    output = (f'Total VMs: {states["total"]}, On: {states["on"]}, '
              f'Off: {states["off"]}, Suspended: {states["suspended"]}')

    exit_plugin(0, output, perfdata)


def check_hosts(session: VCenterAPISession):
    """ Check state of host nodes in vCenter """

    # Query API endpoint
    data = session.query_api_endpoint('GET', '/api/vcenter/host')

    # Print full API response in debug mode
    if session.debug is True:
        print(json.dumps(data, indent=4))

    # Invalidate session token
    session.destroy()

    # Initialize summary dicts
    power_state = {'on': 0, 'off': 0, 'standby': 0,
                   'hosts_off_list': [], 'hosts_standby_list': [],
                   'hosts_off': '', 'hosts_standby': ''}
    connection_state = {'connected': 0, 'disconnected': 0, 'notresponding': 0,
                        'hosts_discon_list': [], 'hosts_notresp_list': [],
                        'hosts_discon': '', 'hosts_notresp': ''}
    total = len(data)

    # Initialize return state
    state = 0

    for element in data:
        if element['connection_state'] == 'CONNECTED':
            connection_state['connected'] += 1
        elif element['connection_state'] == 'DISCONNECTED':
            connection_state['disconnected'] += 1
            connection_state['hosts_discon_list'] += [element["name"]]
        elif element['connection_state'] == 'NOT_RESPONDING':
            connection_state['notresponding'] += 1
            connection_state['hosts_notresp_list'] += [element["name"]]
            state = set_state(1, state)
            continue

        if element['power_state'] == 'POWERED_ON':
            power_state['on'] += 1
        elif element['power_state'] == 'POWERED_OFF':
            power_state['off'] += 1
            power_state['hosts_off_list'] += [element["name"]]
        elif element['power_state'] == 'STANDBY':
            power_state['standby'] += 1
            power_state['hosts_standby_list'] += [element["name"]]

    # Construct strings with impacted hosts
    if len(power_state['hosts_off_list']) > 0:
        power_state['hosts_off'] = f' ({", ".join(power_state["hosts_off_list"])})'

    if len(power_state['hosts_standby_list']) > 0:
        power_state['hosts_standby'] = f' ({", ".join(power_state["hosts_standby_list"])})'

    if len(connection_state['hosts_discon_list']) > 0:
        connection_state['hosts_discon'] = f' ({", ".join(connection_state["hosts_discon_list"])})'

    if len(connection_state['hosts_notresp_list']) > 0:
        connection_state['hosts_notresp'] = f' ({", ".join(connection_state["hosts_notresp_list"])})'

    output = (f' { total } Hosts total - '
              f'Power On: { power_state["on"] }, '
              f'Off: { power_state["off"] }{ power_state["hosts_off"] }, '
              f'Standby: { power_state["standby"] }{ power_state["hosts_standby"] }'
              f' - Connected: { connection_state["connected"] }, '
              f'Disconnected: { connection_state["disconnected"] }'
              f'{ connection_state["hosts_discon"] }, '
              f'Not responding: { connection_state["notresponding"] }'
              f'{ connection_state["hosts_notresp"] }')

    perfdata = (f' | \'power_on\'={ power_state["on"] };;;0;{ total }'
                f' \'power_off\'={ power_state["off"] };;;0;{ total }'
                f' \'power_standby\'={ power_state["standby"] };;;0;{ total }'
                f' \'conn_connected\'={ connection_state["connected"] };;;0;{ total }'
                f' \'conn_disconnected\'={ connection_state["disconnected"] };;;0;{ total }'
                f' \'conn_notresp\'={ connection_state["notresponding"] };;;0;{ total }')

    exit_plugin(state, output, perfdata)


def check_datastores(session: VCenterAPISession):
    """ Check datastores in vCenter """

    # Query API endpoint
    data = session.query_api_endpoint('GET', '/api/vcenter/datastore')

    # Print full API response in debug mode
    if session.debug is True:
        print(json.dumps(data, indent=4))

    # Invalidate session token
    session.destroy()

    # Initialize return strings
    state = 0
    output = f"Total datastores: { len(data) }"
    perfdata = ' | '

    for element in data:
        # Loop through datastores

        # Calculate usage
        used_bytes = element['capacity'] - element['free_space']
        used_pct = round((used_bytes / element['capacity']) * 100, 2)

        if used_pct >= 97:
            # Datastore is used more than 97%, exit WARNING and add to output
            state = set_state(1, state)
            output += f', { element["name"] }: { used_pct }%'

        perfdata += f'\'{ element["name"] }\'={ used_pct }%;;;0;100 '

    # Exit plugin
    exit_plugin(state, output, perfdata)


def main():
    """ Main program code """

    # Get Arguments
    args = get_args()

    # Create vCenter API session
    session = VCenterAPISession(args)

    if args.mode == 'vms':
        # Check state of virtual machines
        check_vms(session)
    elif args.mode == 'hosts':
        # Check state of esx hosts in vCenter
        check_hosts(session)
    elif args.mode == 'datastores':
        # Check state of esx hosts in vCenter
        check_datastores(session)


if __name__ == "__main__":
    main()
