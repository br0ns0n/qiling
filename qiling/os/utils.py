#!/usr/bin/env python3
# 
# Cross Platform and Multi Architecture Advanced Binary Emulation Framework
# Built on top of Unicorn emulator (www.unicorn-engine.org) 

"""
This module is intended for general purpose functions that are only used in qiling.os
"""

from unicorn import *
from unicorn.arm_const import *
from unicorn.x86_const import *
from unicorn.arm64_const import *
from unicorn.mips_const import *

from capstone import *
from capstone.arm_const import *
from capstone.x86_const import *
from capstone.arm64_const import *
from capstone.mips_const import *

from keystone import *

from qiling.const import *
from qiling.exception import *
from qiling.utils import *
from qiling.const import *

from binascii import unhexlify
import ipaddress, struct, os, ctypes
import configparser


def ql_lsbmsb_convert(ql, sc, size=4):
    split_bytes = []
    n = size
    for index in range(0, len(sc), n):
        split_bytes.append((sc[index: index + n])[::-1])

    ebsc = b""
    for i in split_bytes:
        ebsc += i

    return ebsc    


def ql_bin_to_ipv4(ip):
    return "%d.%d.%d.%d" % (
        (ip & 0xff000000) >> 24,
        (ip & 0xff0000) >> 16,
        (ip & 0xff00) >> 8,
        (ip & 0xff))


def ql_init_configuration(self):
    config = configparser.ConfigParser()
    config.read(self.profile)
    self.ql.dprint(D_RPRT, "[+] Added configuration file")
    for section in config.sections():
        self.ql.dprint(D_RPRT, "[+] Section: %s" % section)
        for key in config[section]:
            self.ql.dprint(D_RPRT, "[-] %s %s" % (key, config[section][key]) )
    return config


def ql_bin_to_ip(ip):
    return ipaddress.ip_address(ip).compressed


def ql_read_string(ql, address):
    ret = ""
    c = ql.mem.read(address, 1)[0]
    read_bytes = 1

    while c != 0x0:
        ret += chr(c)
        c = ql.mem.read(address + read_bytes, 1)[0]
        read_bytes += 1
    return ret


def ql_parse_sock_address(sock_addr):
    sin_family, = struct.unpack("<h", sock_addr[:2])

    if sin_family == 2:  # AF_INET
        port, host = struct.unpack(">HI", sock_addr[2:8])
        return "%s:%d" % (ql_bin_to_ip(host), port)
    elif sin_family == 6:  # AF_INET6
        return ""


def ql_compile_asm(ql, archtype, runcode, arm_thumb= None):
    def ks_convert(arch):
        if ql.archendian == QL_ENDIAN.EB:
            adapter = {
                QL_ARCH.X86: (KS_ARCH_X86, KS_MODE_32),
                QL_ARCH.X8664: (KS_ARCH_X86, KS_MODE_64),
                QL_ARCH.MIPS32: (KS_ARCH_MIPS, KS_MODE_MIPS32 + KS_MODE_BIG_ENDIAN),
                QL_ARCH.ARM: (KS_ARCH_ARM, KS_MODE_ARM + KS_MODE_BIG_ENDIAN),
                QL_ARCH.ARM_THUMB: (KS_ARCH_ARM, KS_MODE_THUMB),
                QL_ARCH.ARM64: (KS_ARCH_ARM64, KS_MODE_ARM),
            }
        else:
            adapter = {
                QL_ARCH.X86: (KS_ARCH_X86, KS_MODE_32),
                QL_ARCH.X8664: (KS_ARCH_X86, KS_MODE_64),
                QL_ARCH.MIPS32: (KS_ARCH_MIPS, KS_MODE_MIPS32 + KS_MODE_LITTLE_ENDIAN),
                QL_ARCH.ARM: (KS_ARCH_ARM, KS_MODE_ARM),
                QL_ARCH.ARM_THUMB: (KS_ARCH_ARM, KS_MODE_THUMB),
                QL_ARCH.ARM64: (KS_ARCH_ARM64, KS_MODE_ARM),
            }

        if arch in adapter:
            return adapter[arch]
        # invalid
        return None, None

    def compile_instructions(fname, archtype, archmode):
        f = open(fname, 'rb')
        assembly = f.read()
        f.close()

        ks = Ks(archtype, archmode)

        shellcode = ''
        try:
            # Initialize engine in X86-32bit mode
            encoding, count = ks.asm(assembly)
            shellcode = ''.join('%02x' % i for i in encoding)
            shellcode = unhexlify(shellcode)

        except KsError as e:
            raise

        return shellcode

    if arm_thumb == True and archtype == QL_ARCH.ARM:
        archtype = QL_ARCH.ARM_THUMB

    archtype, archmode = ks_convert(archtype)
    return compile_instructions(runcode, archtype, archmode)


def ql_transform_to_link_path(ql, path):
    if ql.multithread == True:
        cur_path = ql.os.thread_management.cur_thread.get_current_path()
    else:
        cur_path = ql.os.current_path

    rootfs = ql.rootfs

    if path[0] == '/':
        relative_path = os.path.abspath(path)
    else:
        relative_path = os.path.abspath(cur_path + '/' + path)

    from_path = None
    to_path = None
    for fm, to in ql.fs_mapper:
        fm_l = len(fm)
        if len(relative_path) >= fm_l and relative_path[: fm_l] == fm:
            from_path = fm
            to_path = to
            break

    if from_path != None:
        real_path = os.path.abspath(to_path + relative_path[fm_l:])
    else:
        real_path = os.path.abspath(rootfs + '/' + relative_path)

    return real_path


def ql_transform_to_real_path(ql, path):
    if ql.multithread == True:
        cur_path = ql.os.thread_management.cur_thread.get_current_path()
    else:
        cur_path = ql.os.current_path

    rootfs = ql.rootfs

    if path[0] == '/':
        relative_path = os.path.abspath(path)
    else:
        relative_path = os.path.abspath(cur_path + '/' + path)

    from_path = None
    to_path = None
    for fm, to in ql.fs_mapper:
        fm_l = len(fm)
        if len(relative_path) >= fm_l and relative_path[: fm_l] == fm:
            from_path = fm
            to_path = to
            break

    if from_path != None:
        real_path = os.path.abspath(to_path + relative_path[fm_l:])
    else:
        if rootfs == None:
            rootfs = ""
        real_path = os.path.abspath(rootfs + '/' + relative_path)

        if os.path.islink(real_path):
            link_path = os.readlink(real_path)
            if link_path[0] == '/':
                real_path = ql_transform_to_real_path(ql, link_path)
            else:
                real_path = ql_transform_to_real_path(ql, os.path.dirname(relative_path) + '/' + link_path)

    return real_path


def ql_transform_to_relative_path(ql, path):
    if ql.multithread == True:
        cur_path = ql.os.thread_management.cur_thread.get_current_path()
    else:
        cur_path = ql.os.current_path

    if path[0] == '/':
        relative_path = os.path.abspath(path)
    else:
        relative_path = os.path.abspath(cur_path + '/' + path)

    return relative_path


def ql_vm_to_vm_abspath(ql, relative_path):
    if relative_path[0] == '/':
        # abspath input
        abspath = relative_path
        return os.path.abspath(abspath)
    else:
        # relative path input
        cur_path = ql_get_vm_current_path(ql)
        return os.path.abspath(cur_path + '/' + relative_path)


def ql_vm_to_real_abspath(ql, path):
    # TODO:// check Directory traversal, we have the vul
    if path[0] != '/':
        # relative path input
        cur_path = ql_get_vm_current_path(ql)
        path = cur_path + '/' + path
    return os.path.abspath(ql.rootfs + path)


def ql_real_to_vm_abspath(ql, path):
    # rm ".." in path
    abs_path = os.path.abspath(path)
    abs_rootfs = os.path.abspath(ql.rootfs)

    return '/' + abs_path.lstrip(abs_rootfs)


def ql_get_vm_current_path(ql):
    if ql.multithread == True:
        return ql.os.thread_management.cur_thread.get_current_path()
    else:
        return ql.os.current_path


def flag_mapping(flags, mapping_name, mapping_from, mapping_to):
    ret = 0
    for n in mapping_name:
        if mapping_from[n] & flags == mapping_from[n]:
            ret = ret | mapping_to[n]
    return ret


def ql_open_flag_mapping(flags, ql):
    open_flags_name = [
        "O_RDONLY",
        "O_WRONLY",
        "O_RDWR",
        "O_NONBLOCK",
        "O_APPEND",
        "O_ASYNC",
        "O_SYNC",
        "O_NOFOLLOW",
        "O_CREAT",
        "O_TRUNC",
        "O_EXCL",
        "O_NOCTTY",
        "O_DIRECTORY",
    ]

    mac_open_flags = {
        "O_RDONLY": 0x0000,
        "O_WRONLY": 0x0001,
        "O_RDWR": 0x0002,
        "O_NONBLOCK": 0x0004,
        "O_APPEND": 0x0008,
        "O_ASYNC": 0x0040,
        "O_SYNC": 0x0080,
        "O_NOFOLLOW": 0x0100,
        "O_CREAT": 0x0200,
        "O_TRUNC": 0x0400,
        "O_EXCL": 0x0800,
        "O_NOCTTY": 0x20000,
        "O_DIRECTORY": 0x100000
    }

    linux_open_flags = {
        'O_RDONLY': 0,
        'O_WRONLY': 1,
        'O_RDWR': 2,
        'O_NONBLOCK': 2048,
        'O_APPEND': 1024,
        'O_ASYNC': 8192,
        'O_SYNC': 1052672,
        'O_NOFOLLOW': 131072,
        'O_CREAT': 64,
        'O_TRUNC': 512,
        'O_EXCL': 128,
        'O_NOCTTY': 256,
        'O_DIRECTORY': 65536
    }

    mips32el_open_flags = {
        'O_RDONLY': 0x0,
        'O_WRONLY': 0x1,
        'O_RDWR': 0x2,
        'O_NONBLOCK': 0x80,
        'O_APPEND': 0x8,
        'O_ASYNC': 0x1000,
        'O_SYNC': 0x4000,
        'O_NOFOLLOW': 0x20000,
        'O_CREAT': 0x100,
        'O_TRUNC': 0x200,
        'O_EXCL': 0x400,
        'O_NOCTTY': 0x800,
        'O_DIRECTORY': 0x100000,
    }

    if ql.archtype!= QL_ARCH.MIPS32:
        if ql.platform == None or ql.platform == ql.ostype:
            return flags

        if ql.platform == QL_OS.MACOS and ql.ostype == QL_OS.LINUX:
            f = linux_open_flags
            t = mac_open_flags

        elif ql.platform == QL_OS.LINUX and ql.ostype == QL_OS.MACOS:
            f = mac_open_flags
            t = linux_open_flags

    elif ql.archtype== QL_ARCH.MIPS32 and ql.platform == QL_OS.LINUX:
        f = mips32el_open_flags
        t = linux_open_flags

    elif ql.archtype== QL_ARCH.MIPS32 and ql.platform == QL_OS.MACOS:
        f = mips32el_open_flags
        t = mac_open_flags

    return flag_mapping(flags, open_flags_name, f, t)


def print_function(self, address, function_name, params, ret):
    function_name = function_name.replace('hook_', '')
    if function_name in ("__stdio_common_vfprintf", "printf", "wsprintfW", "sprintf"):
        return
    log = '0x%0.2x: %s(' % (address, function_name)
    for each in params:
        value = params[each]
        if type(value) == str or type(value) == bytearray:
            log += '%s = "%s", ' % (each, value)
        else:
            log += '%s = 0x%x, ' % (each, value)
    log = log.strip(", ")
    log += ')'
    if ret is not None:
        log += ' = 0x%x' % ret

    if self.ql.output == QL_OUTPUT.DEFAULT:
        log = log.partition(" ")[-1]
        self.ql.nprint(log)

    elif self.ql.output == QL_OUTPUT.DEBUG:
        self.ql.dprint(D_INFO, log)


def read_cstring(self, address):
    result = ""
    char = self.ql.mem.read(address, 1)
    while char.decode(errors="ignore") != "\x00":
        address += 1
        result += char.decode(errors="ignore")
        char = self.ql.mem.read(address, 1)
    return result

def post_report(self):
    self.ql.dprint(D_INFO, "[+] Syscalls and number of invocations")
    self.ql.dprint(D_INFO, "[-] " + str(list(self.syscall_count.items())))
