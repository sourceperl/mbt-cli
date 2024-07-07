from argparse import ArgumentError, ArgumentParser, ArgumentTypeError, Namespace
import cmd
import re
import time
from typing import Union
from pyModbusTCP.client import ModbusClient
from pyModbusTCP.constants import MB_EXCEPT_ERR
from pyModbusTCP.utils import decode_ieee, get_2comp
from . import __version__ as VERSION


# some const
NAME = 'mbt-cli'


# some functions
def swap_bytes(x: int) -> int:
    return int.from_bytes(x.to_bytes(2, byteorder='little'), byteorder='big')


def replace_hex(line: str) -> str:
    """ Convert hexadecimal string "0x10" to its decimal value "16". """
    return re.sub(r'^\-?0[xX][0-9a-fA-F]+$', lambda match: str(int(match.group(0), 16)), line)


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
    def _preprocess_args(self, args: Union[list, str]) -> list:
        """ Convert args (as str or list) to a new preprocessed list. """
        # ensure args is a list
        if isinstance(args, str):
            args = args.split()
        # init preprocessed argument list
        pp_args = []
        # apply filters to args
        for arg in args:
            # convert hex -> decimal
            # this avoid error on neg hex parse "unrecognized arguments: -0x[...]")
            arg = replace_hex(arg)
            pp_args.append(arg)
        return pp_args

    def parse_cmd_args(self, line: str):
        return self.parse_args(self._preprocess_args(line))

    def error(self, message: str):
        raise ArgumentError(argument=None, message=message)


class MbtCmd(cmd.Cmd):
    """ CLI tool to deal with a modbus/TCP server. """

    intro = 'CLI tool to deal with a modbus/TCP server (type help or ?).'
    mb_client = ModbusClient()
    dump_hex = False
    swap_bytes = False
    swap_words = False
    dump_32b = False

    @property
    def prompt(self):
        """Set cli prompt (like "127.0.0.1:502> ")"""
        return f'{self.mb_client.host}:{self.mb_client.port}> '

    def emptyline(self) -> bool:
        """Avoid empty line execute again the last command"""
        return False

    def _dump_bool_results(self, ret_list: list, cmd_args: Namespace) -> None:
        print(f"{'#':<4} {'address':<17} {'bool'}")
        for reg_idx in range(0, cmd_args.number):
            try:
                bool_as_str = str(ret_list[reg_idx]).lower()
            except IndexError:
                bool_as_str = 'n/a'
            reg_addr = cmd_args.address + reg_idx
            print(f'{reg_idx:04} @{reg_addr:>5} [0x{reg_addr:04x}] = {bool_as_str}')

    def _dump_word_results(self, ret_list: list, cmd_args: Namespace) -> None:
        # head
        head = f"{'#':<4} {'address':<17} {'raw':<8} "
        if self.dump_32b:
            head += f"{'u32':<11} {'i32':<11} {'f32':<11}"
        else:
            head += f"{'u16':<8} {'i16':<8} {'ascii':<12}"
        print(head)
        # lines
        for reg_idx in range(0, cmd_args.number):
            # current address
            reg_addr = cmd_args.address + reg_idx
            # 16 bits values
            try:
                raw_register = ret_list[reg_idx]
                u16 = raw_register
                if self.swap_bytes:
                    u16 = swap_bytes(u16)
                i16 = get_2comp(u16)
                byte_1 = (u16 >> 8) & 0xff
                byte_2 = u16 & 0xff
                u16_bytes = bytes([byte_1, byte_2])
            except IndexError:
                raw_register = None
                u16 = None
                i16 = None
                u16_bytes = None
            # 32 bits values
            try:
                if self.swap_bytes:
                    word_0 = swap_bytes(ret_list[reg_idx])
                    word_1 = swap_bytes(ret_list[reg_idx + 1])
                else:
                    word_0 = ret_list[reg_idx]
                    word_1 = ret_list[reg_idx + 1]
                if self.swap_words:
                    u32 = (word_1 << 16) + word_0
                else:
                    u32 = (word_0 << 16) + word_1
                i32 = get_2comp(u32, val_size=32)
                f32 = decode_ieee(u32)
            except IndexError:
                u32 = None
                i32 = None
                f32 = None
            # set format vars
            if self.dump_hex:
                pfix, fmt16, fmt32 = '0x', '04x', '08x'
            else:
                pfix, fmt16, fmt32 = '', '', ''
            # format values as str
            # mandatory
            raw_as_str = f'0x{raw_register:04x}' if raw_register is not None else 'n/a'
            # on 32 or 16 bits mode
            if self.dump_32b:
                u32_as_str = f'{pfix}{u32:{fmt32}}' if u32 is not None else 'n/a'
                i32_sign = '-' if i32 and i32 < 0 else ''
                i32_as_str = f'{i32_sign}{pfix}{abs(i32):{fmt32}}' if i32 is not None else 'n/a'
                f32_as_str = f'{f32}' if f32 is not None else 'n/a'
            else:
                u16_as_str = f'{pfix}{u16:{fmt16}}' if u16 is not None else 'n/a'
                i16_sign = '-' if i16 and i16 < 0 else ''
                i16_as_str = f'{i16_sign}{pfix}{abs(i16):{fmt16}}' if i16 is not None else 'n/a'
                ascii_as_str = f'{u16_bytes}'
            # dump
            line = f'{reg_idx:04} @{reg_addr:>5} [0x{reg_addr:04x}] = {raw_as_str:<8} '
            if self.dump_32b:
                line += f'{u32_as_str:<11} {i32_as_str:<11} {f32_as_str:<11}'
            else:
                line += f'{u16_as_str:<8} {i16_as_str:<8} {ascii_as_str:<12}'
            print(line)

    def _dump_results(self, ret_list: list, cmd_args: Namespace, as_bool: bool = False) -> None:
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

    def do_wait(self, arg: str = ''):
        """Wait a few seconds\n\nwait [seconds]"""
        try:
            # parse args
            cmd_parser = CmdArgParser(add_help=False, exit_on_error=False)
            cmd_parser.add_argument('value', nargs='?', type=float, default=1.0)
            cmd_args = cmd_parser.parse_cmd_args(arg)
            # wait n seconds
            time.sleep(cmd_args.value)
        except (ArgumentError, ValueError) as e:
            print(e)

    def do_dump_hex(self, arg: str = ''):
        """Check or set dump as hexadecimal\n\ndump_hex [on/off]"""
        # try to set
        hex_set = arg.strip().lower()
        if hex_set:
            if hex_set == 'on':
                self.dump_hex = True
            elif hex_set == 'off':
                self.dump_hex = False
            else:
                print('unable to set hex flag')
        # show status
        hex_str = 'on' if self.dump_hex else 'off'
        print(f'dump hex is {hex_str}')

    def do_dump_32b(self, arg: str = ''):
        """Check or set dump in 32 bits mode\n\ndump_32b [on/off]"""
        # try to set
        d32b_set = arg.strip().lower()
        if d32b_set:
            if d32b_set == 'on':
                self.dump_32b = True
            elif d32b_set == 'off':
                self.dump_32b = False
            else:
                print('unable to set dump 32 bits flag')
        # show status
        d32b_str = 'on' if self.dump_32b else 'off'
        print(f'dump 32 bits is {d32b_str}')

    def do_swap_bytes(self, arg: str = ''):
        """Check or set swap bytes mode\n\nswap_bytes [on/off]"""
        # try to set
        swap_set = arg.strip().lower()
        if swap_set:
            if swap_set == 'on':
                self.swap_bytes = True
            elif swap_set == 'off':
                self.swap_bytes = False
            else:
                print('unable to set swap bytes flag')
        # show status
        swap_str = 'on' if self.swap_bytes else 'off'
        print(f'swap bytes is {swap_str}')

    def do_swap_words(self, arg: str = ''):
        """Check or set swap words mode\n\nswap_words [on/off]"""
        # try to set
        swap_set = arg.strip().lower()
        if swap_set:
            if swap_set == 'on':
                self.swap_words = True
            elif swap_set == 'off':
                self.swap_words = False
            else:
                print('unable to set swap words flag')
        # show status
        swap_str = 'on' if self.swap_words else 'off'
        print(f'swap words is {swap_str}')

    def do_host(self, arg: str = ''):
        """Check or set host\n\nhost [hostname/ip address/fqdn]"""
        try:
            # parse args
            cmd_parser = CmdArgParser(add_help=False, exit_on_error=False)
            cmd_parser.add_argument('value', nargs='?', type=str,
                                    default=self.mb_client.host)
            cmd_args = cmd_parser.parse_cmd_args(arg)
            # set
            self.mb_client.host = cmd_args.value
            # show status
            print(f'host set to {self.mb_client.host}')
        except (ArgumentError, ValueError) as e:
            print(e)

    def do_port(self, arg: str = ''):
        """Check or set port\n\nport [tcp port]"""
        try:
            # parse args
            cmd_parser = CmdArgParser(add_help=False, exit_on_error=False)
            cmd_parser.add_argument('value', nargs='?', type=valid_int(min=1, max=0xffff),
                                    default=self.mb_client.port)
            cmd_args = cmd_parser.parse_cmd_args(arg)
            # set
            self.mb_client.port = cmd_args.value
            # show status
            print(f'port set to {self.mb_client.port}')
        except (ArgumentError, ValueError) as e:
            print(e)

    def do_timeout(self, arg: str = ''):
        """Check or set timeout\n\ntimeout [timeout value in s]"""
        try:
            # parse args
            cmd_parser = CmdArgParser(add_help=False, exit_on_error=False)
            cmd_parser.add_argument('value', nargs='?', type=float, default=self.mb_client.timeout)
            cmd_args = cmd_parser.parse_cmd_args(arg)
            # set
            self.mb_client.timeout = cmd_args.value
            # show status
            print(f'timeout set to {self.mb_client.timeout} s')
        except (ArgumentError, ValueError) as e:
            print(e)

    def do_unit_id(self, arg: str = ''):
        """Check or set unit-id\n\nunit_id [unit_id]"""
        try:
            # parse args
            cmd_parser = CmdArgParser(add_help=False, exit_on_error=False)
            cmd_parser.add_argument('value', nargs='?', type=valid_int(min=1, max=0xff),
                                    default=self.mb_client.unit_id)
            cmd_args = cmd_parser.parse_cmd_args(arg)
            # set
            self.mb_client.unit_id = cmd_args.value
            # show status
            print(f'unit_id set to {self.mb_client.unit_id}')
        except (ArgumentError, ValueError) as e:
            print(e)

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
            # modbus i/o
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
            # modbus i/o
            raw_value = cmd_args.value
            if self.swap_bytes:
                raw_value = swap_bytes(raw_value)
            write_ok = self.mb_client.write_single_register(cmd_args.address, raw_value)
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
    parser.add_argument('-d', '--debug', action='store_true', help='turn on debug mode')
    parser.add_argument('-v', '--version', action='store_true', help='print version and exit')
    parser.add_argument('-h', '--host', type=str, default='localhost', help='server host (default: localhost)')
    parser.add_argument('-p', '--port', type=int, default=502, help='server TCP port (default: 502)')
    parser.add_argument('-t', '--timeout', type=float, default=5.0, help='server timeout delay in s (default: 5.0)')
    parser.add_argument('-u', '--unit-id', type=int, default=1, help='unit-id (default is 1)')
    parser.add_argument('-c', '--cmd', type=str, default='', help='command(s) (with args) to execute')
    parser.add_argument('--dump-hex', action='store_true', help='display results in hexadecimal')
    parser.add_argument('--dump-32b', action='store_true', help='display results as 32 bits data')
    parser.add_argument('--swap-bytes', action='store_true', help='swap bytes in 16 bits elements')
    parser.add_argument('--swap-words', action='store_true', help='swap words in 32 bits elements')
    args = parser.parse_args()

    # show version
    if args.version:
        print(f'{NAME} {VERSION}')
        exit()

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
        mbt_cmd.dump_hex = args.dump_hex
        mbt_cmd.dump_32b = args.dump_32b
        mbt_cmd.swap_bytes = args.swap_bytes
        mbt_cmd.swap_words = args.swap_words
        # start cli loop or just a one shot run (command set at cmd line)
        if not args.cmd:
            mbt_cmd.cmdloop()
        else:
            # execute cli commands pass on command line (--cmd "cmd1; cmd2...")
            for cmd in args.cmd.split(';'):
                mbt_cmd.onecmd(cmd)
    except ValueError as e:
        print(f'error occur: {e}')
    except KeyboardInterrupt:
        exit(0)
