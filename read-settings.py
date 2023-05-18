#!/usr/bin/env python3

from binascii import crc_hqx
from itertools import cycle
from sys import argv
from time import time

from serial import Serial

KEY = bytes.fromhex('166c14e62e910d402135d5401303e980')
BLOCK_SIZE = 0x80

PREAMBLE = b'\xab\xcd'
POSTAMBLE = b'\xdc\xba'

CMD_VERSION_REQ = 0x0514
CMD_VERSION_RES = 0x0515

CMD_SETTINGS_REQ = 0x051B
CMD_SETTINGS_RES = 0x051C

TIMESTAMP = int(time()).to_bytes(4, 'little')


def xor(var):
    return bytes(a ^ b for a, b in zip(var, cycle(KEY)))
    

def i2b16(cmd_id):
    return cmd_id.to_bytes(2,'little')


def b2i(data):
    return int.from_bytes(data, 'little')


def len16(data):
    return i2b16(len(data))


def crc16(data):
    return i2b16(crc_hqx(data, 0))

def chunk(data, n):
    for i in range(0,len(data), n):
        yield data[i:i+n]


def cmd_make_req(cmd_id, body=b''):
    data = body + TIMESTAMP
    payload = i2b16(cmd_id) + len16(data) + data
    encoded_payload = xor(payload + crc16(payload))

    return PREAMBLE + len16(payload) + encoded_payload + POSTAMBLE


class UVK5(Serial):
    def __init__(self, port: str | None = None) -> None:
        super().__init__(port, 38400, timeout=5)

    def read_mem(self, offset, size):
        return self.cmd(CMD_SETTINGS_REQ, i2b16(offset) + i2b16(size))

    def cmd(self, id, body = b''):
        self.write(cmd_make_req(id, body))
        preamble = self.read(2)

        if preamble != PREAMBLE:
            raise ValueError('Bad response (PRE)')

        payload_len = b2i(self.read(2)) + 2 # CRC len
        payload = xor(self.read(payload_len))

        # crc = payload[-2:]
        postamble = self.read(2)
        
        if postamble != POSTAMBLE:
            raise ValueError('Bad response (POST)')
            
        # print(data.hex())
        cmd_id = b2i(payload[:2])
        data_len = b2i(payload[2:4])
        data = payload[4:4+data_len]

        return (cmd_id, data)


def read_channels_settings(s):
    names = []
    settings = []

    data_size = 16 * 200
    names_offset = 0x0F50
    settings_offset = 0x0000

    passes = data_size//BLOCK_SIZE

    for block in range(passes):
        offset = names_offset + block*BLOCK_SIZE
        names_set = s.read_mem(offset, BLOCK_SIZE)[1][4:]
        names += [name.decode(errors='ignore').rstrip('\x00') for name in chunk(names_set, 16)]

    for block in range(passes):
        offset = settings_offset + block*BLOCK_SIZE
        settings_set = s.read_mem(offset, BLOCK_SIZE)[1][4:]
        settings += [(b2i(setting[:4])/100000.0, ) for setting in chunk(settings_set, 16)]
    
    for i, name in enumerate(names):
        if name:
            print(f'{i+1:0>3}. {name: <16} {settings[i][0]:0<8} M')
        else:
            print(f'{i+1:0>3}. -')
        

def main(port):
    with UVK5(port) as s:
        ver = s.cmd(CMD_VERSION_REQ)[1][:10].decode().rstrip('\x00')
        print('FW version:', ver)
        read_channels_settings(s)
        

if __name__ == '__main__':
    main(argv[1])