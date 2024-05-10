from argparse import ArgumentError, ArgumentParser, ArgumentTypeError, Namespace
import cmd
import re
import sys
from pyModbusTCP.client import ModbusClient
from pyModbusTCP.constants import MB_EXCEPT_ERR
from pyModbusTCP.utils import get_2comp
from . import __version__ as VERSION


# some const
NAME = 'mbt-cli'


# some functions
def replace_hex(line: str) -> str:
    """ Convert hexadecimal string "0x10" to its decimal value "16". """
    return re.sub(r'0[xX][0-9a-fA-F]+', lambda match: str(int(match.group(0), 16)), line)


def preprocess_args(args: list | str) -> list:
    """ Convert args (as str or list) to a new preprocessed list. """
    # ensure args is a list
    if isinstance(args, str):
        args = args.split()
    # init preprocessed argument list
    pp_args = []
    # apply preprocess filter
    for arg in args:
        # convert hex -> decimal
        arg = replace_hex(arg)
        pp_args.append(arg)
    return pp_args


def valid_int(min: int, max: int):
    def _valid_int(x: str):
        try:
            x = int(x)
        except ValueError:
            raise ArgumentTypeError('not an int')
        if not min <= x <= max:
            raise ArgumentTypeError(f'not in valid range [{min}-{max}]')
        return x
    return _valid_int


# some class
class CmdArgParser(ArgumentParser):
    def parse_cmd_args(self, line: str):
        return self.parse_args(preprocess_args(line))

    def error(self, message: str):
        raise ArgumentError(argument=None, message=message)


class MbtCmd(cmd.Cmd):
    """ CLI tool to deal with a modbus/TCP server. """

    intro = 'CLI tool to deal with a modbus/TCP server (type help or ?).'
    mb_client = ModbusClient()

    @property
    def prompt(self):
        """Set cli prompt (like "127.0.0.1:502> ")"""
        return f'{self.mb_client.host}:{self.mb_client.port}> '

    def emptyline(self) -> bool:
        """Avoid empty line execute again the last command"""
        return False

    def _dump_bool_results(self, ret_list: list, cmd_args: Namespace):
        print(f"{'#':<4} {'address':<17} {'bool'}")
        for reg_idx in range(0, cmd_args.number):
            try:
                bool_as_str = str(ret_list[reg_idx]).lower()
            except IndexError:
                bool_as_str = 'n/a'
            reg_addr = cmd_args.address + reg_idx
            print(f'{reg_idx:04} @{reg_addr:>5} [0x{reg_addr:04x}] = {bool_as_str}')

    def _dump_word_results(self, ret_list: list, cmd_args: Namespace):
        print(f"{'#':<4} {'address':<17} {'u16':<6} {'i16':<6}")
        for reg_idx in range(0, cmd_args.number):
            try:
                u16_as_str = str(ret_list[reg_idx])
                i16_as_str = str(get_2comp(ret_list[reg_idx]))
            except IndexError:
                u16_as_str = 'n/a'
                i16_as_str = 'n/a'
            reg_addr = cmd_args.address + reg_idx
            print(f'{reg_idx:04} @{reg_addr:>5} [0x{reg_addr:04x}] = {u16_as_str:<6} {i16_as_str:<6}')

    def _dump_results(self, ret_list: list, cmd_args: Namespace, as_bool: bool = False):
        if ret_list:
            if as_bool:
                self._dump_bool_results(ret_list, cmd_args)
            else:
                self._dump_word_results(ret_list, cmd_args)
        elif not self.mb_client.debug:
            except_str = f' ({self.mb_client.last_except_as_txt})' if self.mb_client.last_error == MB_EXCEPT_ERR else ''
            print(self.mb_client.last_error_as_txt + except_str)

    def do_debug(self, arg: str = ''):
        """Check or set debug status\n\ndebug [on/off]"""
        # try to set
        debug_set = arg.strip().lower()
        if debug_set:
            if debug_set == 'on':
                self.mb_client.debug = True
            elif debug_set == 'off':
                self.mb_client.debug = False
            else:
                print('unable to set debug flag')
        # show status
        debug_str = 'on' if self.mb_client.debug else 'off'
        print(f'debug is {debug_str}')

    def do_host(self, arg: str = ''):
        """Check or set host\n\nhost [hostname/ip address/fqdn]"""
        # try to set
        host_set = arg.strip().lower()
        if host_set:
            try:
                self.mb_client.host = str(host_set)
            except ValueError:
                print('unable to set host')
        # show status
        print(f'current host is "{self.mb_client.host}"')

    def do_port(self, arg: str = ''):
        """Check or set port\n\nport [tcp port]"""
        # try to set
        port_set = arg.strip().lower()
        if port_set:
            try:
                self.mb_client.port = int(port_set)
            except ValueError:
                print('unable to set port')
        # show status
        print(f'current port value is {self.mb_client.port}')

    def do_timeout(self, arg: str = ''):
        """Check or set timeout\n\ntimeout [timeout value in s]"""
        # try to set
        timeout_set = arg.strip().lower()
        if timeout_set:
            try:
                self.mb_client.timeout = float(timeout_set)
            except ValueError:
                print('unable to set timeout')
        # show status
        print(f'timeout is {self.mb_client.timeout} s')

    def do_unit_id(self, arg: str = ''):
        """Check or set unit-id\n\nunit_id [unit_id]"""
        # try to set
        unit_id_set = arg.strip().lower()
        if unit_id_set:
            try:
                self.mb_client.unit_id = int(unit_id_set)
            except ValueError:
                print('unable to set unit-id')
        # show status
        print(f'unit-id is set to {self.mb_clientt.unit_id}')

    def do_read_coils(self, arg: str = ''):
        """Modbus function 1 (read coils)\n\nread_coils [address] [number of coils]"""
        try:
            # parse args
            cmd_parser = CmdArgParser(add_help=False, exit_on_error=False)
            cmd_parser.add_argument('address', nargs='?', type=valid_int(min=0, max=0xffff), default=0)
            cmd_parser.add_argument('number', nargs='?', type=valid_int(min=1, max=2000), default=1)
            cmd_args = cmd_parser.parse_cmd_args(arg)
            # do modbus job
            ret_list = self.mb_client.read_coils(cmd_args.address, cmd_args.number)
            # show result
            self._dump_results(ret_list, cmd_args, as_bool=True)
        except (ArgumentError, ValueError) as e:
            print(e)

    def do_read_discrete_inputs(self, arg: str = ''):
        """Modbus function 2 (read discrete inputs)\n\nread_discrete_inputs [address] [number of inputs]"""
        try:
            # parse args
            cmd_parser = CmdArgParser(add_help=False, exit_on_error=False)
            cmd_parser.add_argument('address', nargs='?', type=valid_int(min=0, max=0xffff), default=0)
            cmd_parser.add_argument('number', nargs='?', type=valid_int(min=1, max=2000), default=1)
            cmd_args = cmd_parser.parse_cmd_args(arg)
            # do modbus job
            ret_list = self.mb_client.read_discrete_inputs(cmd_args.address, cmd_args.number)
            # show result
            self._dump_results(ret_list, cmd_args, as_bool=True)
        except (ArgumentError, ValueError) as e:
            print(e)

    def do_read_holding_registers(self, arg: str = ''):
        """Modbus function 3 (read holding registers)\n\nread_holding_registers [address] [number of registers]"""
        try:
            # parse args
            cmd_parser = CmdArgParser(add_help=False, exit_on_error=False)
            cmd_parser.add_argument('address', nargs='?', type=valid_int(min=0, max=0xffff), default=0)
            cmd_parser.add_argument('number', nargs='?', type=valid_int(min=1, max=125), default=1)
            cmd_args = cmd_parser.parse_cmd_args(arg)
            # do modbus job
            ret_list = self.mb_client.read_holding_registers(cmd_args.address, cmd_args.number)
            # show result
            self._dump_results(ret_list, cmd_args)
        except (ArgumentError, ValueError) as e:
            print(e)

    def do_read_input_registers(self, arg: str = ''):
        """Modbus function 4 (read input registers)\n\nread_input_registers [address] [number of registers]"""
        try:
            # parse args
            cmd_parser = CmdArgParser(add_help=False, exit_on_error=False)
            cmd_parser.add_argument('address', nargs='?', type=valid_int(min=0, max=0xffff), default=0)
            cmd_parser.add_argument('number', nargs='?', type=valid_int(min=1, max=125), default=1)
            cmd_args = cmd_parser.parse_cmd_args(arg)
            # do modbus job
            ret_list = self.mb_client.read_input_registers(cmd_args.address, cmd_args.number)
            # show result
            self._dump_results(ret_list, cmd_args)
        except (ArgumentError, ValueError) as e:
            print(e)

    def do_write_single_coil(self, arg: str = ''):
        """Modbus function 5 (write single coil)\n\nwrite_single_coil [address] [coil value]"""
        try:
            # parse args
            cmd_parser = CmdArgParser(add_help=False, exit_on_error=False)
            cmd_parser.add_argument('address', type=valid_int(min=0, max=0xffff))
            cmd_parser.add_argument('value', type=valid_int(min=0, max=1))
            cmd_args = cmd_parser.parse_cmd_args(arg)
            # do modbus job
            write_ok = self.mb_client.write_single_coil(cmd_args.address, cmd_args.value)
            # show result
            if write_ok:
                print('coil write ok')
            else:
                print('unable to set coil')
        except (ArgumentError, ValueError) as e:
            print(e)

    def do_write_single_register(self, arg: str = ''):
        """Modbus function 6 (write single register)\n\nwrite_single_register [address] [register value]"""
        try:
            # parse args
            cmd_parser = CmdArgParser(add_help=False, exit_on_error=False)
            cmd_parser.add_argument('address', type=valid_int(min=0, max=0xffff))
            cmd_parser.add_argument('value', type=valid_int(min=0, max=0xffff))
            cmd_args = cmd_parser.parse_cmd_args(arg)
            # do modbus job
            write_ok = self.mb_client.write_single_register(cmd_args.address, cmd_args.value)
            # show result
            if write_ok:
                print('register write ok')
            else:
                print('unable to set register')
        except (ArgumentError, ValueError) as e:
            print(e)

    def do_version(self, _arg):
        """Print version"""
        print(f'{NAME} {VERSION}')

    def do_exit(self, _arg):
        """Exit from cli"""
        return True


def main():
    # parse command line args
    parser = ArgumentParser(add_help=False)
    parser.add_argument('--help', action='help', help='show this help message and exit')
    parser.add_argument('-d', '--debug', action='store_true', help='debug mode')
    parser.add_argument('-h', '--host', type=str, default='localhost', help='server host (default: localhost)')
    parser.add_argument('-p', '--port', type=int, default=502, help='server TCP port (default: 502)')
    parser.add_argument('-t', '--timeout', type=float, default=5.0, help='server timeout delay in s (default: 5.0)')
    parser.add_argument('-u', '--unit-id', type=int, default=1, help='unit-id (default is 1)')
    parser.add_argument('command', nargs='*', default='', help='command to execute')
    args = parser.parse_args(preprocess_args(sys.argv[1:]))

    # run tool
    try:
        # init
        mbt_cmd = MbtCmd()
        # apply args to modbus client
        mbt_cmd.mb_client.host = args.host
        mbt_cmd.mb_client.port = args.port
        mbt_cmd.mb_client.unit_id = args.unit_id
        mbt_cmd.mb_client.timeout = args.timeout
        mbt_cmd.mb_client.debug = args.debug
        # start cli loop or just a one shot run (command set at cmd line)
        if not args.command:
            mbt_cmd.cmdloop()
        else:
            # convert list of args -> command line
            cmd_line = ' '.join(args.command)
            mbt_cmd.onecmd(cmd_line)
    except ValueError as e:
        print(f'error occur: {e}')
    except KeyboardInterrupt:
        exit(0)
