import random
import socket
import struct
import json
import base64
import time
import sys
from enum import IntEnum

import items # helper formatted from item_data_ids.h

HOST = "127.0.0.1"
PORT = 5555
TEST = False

test_packets = {
    "CMD_ID": "0000", #u16 Header byte for command ID
    "CMD_Len": "0000", #u16 Header bytes for command length   
}

def recv_exact(sock, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise RuntimeError("Socket closed while receiving data")
        data += chunk
    return data

class Cmd(IntEnum):
    CMD_ITEM = 1
    CMD_IDX = 2
    CMD_rIDX = 3

def test(cmd: str, var1: int = 0, var2: int = 0):
    if cmd == "item":
        item_id = var1
        idx = var2
        payload = struct.pack(">IH", idx & 0xFFFFFFFF, item_id & 0xFFFF)
        #idxcheck = (read_test_packet("idx"))
        write_to_test_packet(Cmd.CMD_ITEM, payload)
    elif cmd == "idx":
        idx = var1
        payload = struct.pack(">I", idx & 0xFFFFFFFF)
        write_to_test_packet(Cmd.CMD_IDX, payload)
    elif cmd == "loop":
        item_id = var1
        idx = var2
        payload = struct.pack(">IH", idx & 0xFFFFFFFF, item_id & 0xFFFF)
        write_to_test_packet(Cmd.CMD_ITEM, payload)
    elif cmd == "ridx":
        write_to_test_packet(Cmd.CMD_rIDX, b"\x00")
        read_test_packet("ridx")

    resp = read_test_packet(cmd)
    print(resp)

def write_to_test_packet(cmd_id: int, payload: bytes = b"") -> bytes:
    # Simulate a server response for testing purposes
    if cmd_id == Cmd.CMD_rIDX:
        with open("testpackets.json", "r") as f:
            data = json.load(f)
            readPayload = data.get("PAYLOAD", None)[:8]

    with open("testpackets.json", "w") as f:
        if cmd_id == Cmd.CMD_rIDX:
            test_packets["CMD_ID"] = f"{cmd_id:04X}"
            test_packets["CMD_Len"] = f"{8:04X}"
            test_packets["response"] = readPayload
            json.dump(test_packets, f, indent=4)
            return

        payload_len = len(payload)
        test_packets["CMD_ID"] = f"{cmd_id:04X}"
        test_packets["CMD_Len"] = f"{4 + payload_len:04X}"
        test_packets["PAYLOAD"] = payload[:payload_len].hex()
        test_packets["WHOLE_PACKET"] = f"{cmd_id:04X}{4 + payload_len:04X}{payload.hex()}"
        json.dump(test_packets, f, indent=4)

def read_test_packet(cmd: str) -> bytes:
    # Read the simulated server response from the test packet file
    with open("testpackets.json", "r") as f:
        data = json.load(f)

        if cmd == "ridx":
            command_id = bytes.fromhex(data.get("CMD_ID", "0000")) #Skip length for ridx; always definitive
            idx = bytes.fromhex(data.get("PAYLOAD", "00000000")[:8])  # First 4 bytes of payload for idx
            cmd_id_int = int.from_bytes(command_id, byteorder="big")
            cmd_idx = int.from_bytes(idx, byteorder="big")
            assert cmd_id_int == Cmd.CMD_rIDX, "CMD_ID does not match CMD_rIDX"
            return f"\nCommand ID: {Cmd(cmd_id_int)}\nidx: {cmd_idx}"

        command_id = bytes.fromhex(data.get("CMD_ID", "0000"))
        command_len = bytes.fromhex(data.get("CMD_Len", "0000"))
        cmd_idx = bytes.fromhex(data.get("PAYLOAD", "00000000")[:8])  # First 4 bytes of payload for idx

        cmd_id_int = int.from_bytes(command_id, byteorder="big")
        cmd_len_int = int.from_bytes(command_len, byteorder="big")
        cmd_idx = int.from_bytes(cmd_idx, byteorder="big")

        if cmd == "item" or cmd == "loop":
            assert cmd_id_int == Cmd.CMD_ITEM, "CMD_ID does not match CMD_ITEM"
            item_id = bytes.fromhex(data.get("PAYLOAD", "00000000")[8:12])  # Next 2 bytes for itemId
            item_id_int = int.from_bytes(item_id, byteorder="big")
            return f"\nCommand ID: {Cmd(cmd_id_int)}\nCommand Length: {cmd_len_int}\nidx: {cmd_idx}\nitem_id: {item_id_int}"
        elif cmd == "idx":
            assert cmd_id_int == Cmd.CMD_IDX, "CMD_ID does not match CMD_IDX"
            return f"\nCommand ID: {Cmd(cmd_id_int)}\nCommand Length: {cmd_len_int}\nidx: {cmd_idx}"
        else:
            return "Unknown command"

def send_packet(cmd_id: int, payload: bytes = b"") -> bytes:
    packet_len = 4 + len(payload)
    header = struct.pack(">HH", cmd_id, packet_len)
    packet = header + payload

    print(packet.hex(" "))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.sendall(packet)

        if cmd_id == Cmd.CMD_rIDX:
            return recv_exact(s, 4)   # read raw u32

        # 1) read string length
        raw_len = recv_exact(s, 4)
        msg_len = struct.unpack(">I", raw_len)[0]

        # 2) read string bytes
        if msg_len == 0:
            return b""

        return recv_exact(s, msg_len)
    
def item(item_id: int, idx: int = 0) -> bytes:
    # payload for CMD_ITEM: u16 idx, u16 itemId
    payload = struct.pack(">IH", idx & 0xFFFFFFFF, item_id & 0xFFFF)
    print(payload.hex(" "))
    return send_packet(Cmd.CMD_ITEM, payload)

def idxcmd(idx: int) -> bytes:
    payload = struct.pack(">I", idx & 0xFFFFFFFF)
    print(payload.hex(" "))
    return send_packet(Cmd.CMD_IDX, payload)

def ridxcmd() -> bytes:
    return send_packet(Cmd.CMD_rIDX, b"")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        if TEST:
            with open("testpackets.json", "w") as f:
                json.dump(test_packets, f, indent=4)
            print("Wrote testpackets.json")
        else:
            print("Usage: <item|loop|idx> [args...] -- TEST mode is off")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "test":
        if len(sys.argv) < 3:
            print("Usage: test <item|loop|idx>")
            sys.exit(1)

        command_id = int(sys.argv[2], 10)
        test_packets["CMD_ID"] = f"{command_id:04X}"
        
        with open("testpackets.json", "w") as f:
            json.dump(test_packets, f, indent=4)
        print("Wrote testpackets.json with CMD_ID:", test_packets["CMD_ID"])
        sys.exit(0)

    elif cmd == "item":
        if len(sys.argv) < 3:
            print("Usage: item <itemid> [idx]")
            sys.exit(1)

        item_id = int(sys.argv[2], 10)
        idx = int(sys.argv[3], 10) if len(sys.argv) >= 4 else 1

        if TEST:
            test(cmd, item_id, idx)
        else:
            resp = item(item_id, idx)
            print("response:", resp.decode("utf-8", errors="replace"))

    elif cmd == "loop":
        idx = 1

        if TEST:
            test("idx", 0)
        else:
            idxcmd(0)  # reset idx on server

        while idx < 10:
            item_id = random.randint(0, len(items.ITEM_ID_TO_NAME) - 1)
            if TEST:
                test(cmd, item_id, idx)
            else:    
                resp = item(item_id, idx)
                print(f"item_str: {items.item_name(item_id)}, idx: {idx}")
                print("response:", resp.decode("utf-8", errors="replace"))
            time.sleep(2)
            idx += 1

    elif cmd == "idx":
        if len(sys.argv) < 3:
            print("Usage: idx <idx>")
            sys.exit(1)
        idx = int(sys.argv[2], 10)

        if TEST:
            test(cmd, idx)
        else:
            resp = idxcmd(idx)
            print("response:", resp.decode("utf-8", errors="replace"))

    elif cmd == "ridx":
        if TEST:
            test(cmd)
        else:
            resp = ridxcmd()
            idx = struct.unpack(">I", resp)[0]
            print("Server idx:", idx)

    else:
        print("Unknown command")
        sys.exit(1)