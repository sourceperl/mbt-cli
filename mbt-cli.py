#!/usr/bin/env python3

"""
A modbus/TCP command-line cli.

"""

import argparse
from dataclasses import dataclass
import cmd
from pyModbusTCP.client import ModbusClient


# some const
NAME = 'mbt-cli'
VERSION = '0.0.1'


@dataclass
class RequestData:
    address: int = 0
    number: int = 0
    read_list: list = None


class MbtCli(cmd.Cmd):
    """ CLI tool to deal with a modbus/TCP server. """

    intro = 'CLI tool to deal with a modbus/TCP server (type help or ?).'
    request = RequestData()

    @property
    def prompt(self):
        """Set cli prompt (like "127.0.0.1:8428> ")"""
        return f'{mbus_cli.host}:{mbus_cli.port}> '

    def emptyline(self) -> bool:
        """Avoid empty line execute again the last command"""
        return False

    def do_debug(self, arg: str = ''):
        """Check or set debug status"""
        # try to set
        debug_set = arg.strip().lower()
        if debug_set:
            if debug_set == 'on':
                mbus_cli.debug = True
            elif debug_set == 'off':
                mbus_cli.debug = False
            else:
                print('unable to set debug flag')
        # show status
        debug_str = 'on' if mbus_cli.debug else 'off'
        print(f'debug is {debug_str}')

    def do_host(self, arg: str = ''):
        """Check or set host"""
        # try to set
        host_set = arg.strip().lower()
        if host_set:
            try:
                mbus_cli.host = str(host_set)
            except ValueError:
                print('unable to set host')
        # show status
        print(f'current host is "{mbus_cli.host}"')

    def do_port(self, arg: str = ''):
        """Check or set port"""
        # try to set
        port_set = arg.strip().lower()
        if port_set:
            try:
                mbus_cli.port = int(port_set)
            except ValueError:
                print('unable to set port')
        # show status
        print(f'current port value is {mbus_cli.port}')

    def do_timeout(self, arg: str = ''):
        """Check or set timeout"""
        # try to set
        timeout_set = arg.strip().lower()
        if timeout_set:
            try:
                mbus_cli.timeout = float(timeout_set)
            except ValueError:
                print('unable to set timeout')
        # show status
        print(f'timeout is {mbus_cli.timeout} s')

    def do_read_coils(self, arg: str = ''):
        """Read coils (function 1)"""
        # process command args: "read coils [address] [number]"
        try:
            self._parse_read_args(arg)
            self.request.read_list = mbus_cli.read_coils(self.request.address, self.request.number)
            self._dump_results()
        except ValueError as e:
            print(e)

    def do_version(self, _arg):
        """Print version"""
        print(f'{NAME} {VERSION}')

    def do_exit(self, _arg):
        """Exit from cli"""
        return True

    def _parse_read_args(self, arg: str):
        args_l = arg.split()
        try:
            self.request.address = int(args_l[0])
        except IndexError:
            self.request.address = 0
        try:
            self.request.number = int(args_l[1])
        except IndexError:
            self.request.number = 1

    def _dump_results(self):
        if self.request.read_list:
            for idx in range(0, len(self.request.read_list)):
                print(f'{idx} 0x{self.request.address + idx:04x} ({self.request.address + idx:d}) {self.request.read_list[idx]}')


if __name__ == '__main__':
    # init
    mbt_cli = MbtCli()
    # parse command line args
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true', help='debug mode')
    parser.add_argument('-H', '--host', type=str, default='localhost', help='server host (default: localhost)')
    parser.add_argument('-p', '--port', type=int, default=502, help='server TCP port (default: 502)')
    parser.add_argument('-t', '--timeout', type=float, default=5.0, help='server timeout delay in s (default: 5.0)')
    parser.add_argument('-u', '--unit-id', type=int, default=1, help='unit-id (default is 1)')
    parser.add_argument('command', nargs='*', default='', help='command to execute')
    args = parser.parse_args()

    # run tool
    try:
        # init modbus client
        mbus_cli = ModbusClient(host=args.host, port=args.port, unit_id=args.unit_id,
                                timeout=args.timeout, debug=args.debug)
        # start cli loop or just a one shot run (command set at cmd line)
        if not args.command:
            mbt_cli.cmdloop()
        else:
            # convert list of args -> command line
            cmd_line = ' '.join(args.command)
            mbt_cli.onecmd(cmd_line)
    except ValueError as e:
        print(f'error occur: {e}')
    except KeyboardInterrupt:
        exit(0)