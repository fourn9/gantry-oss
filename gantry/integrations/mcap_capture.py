"""Bounded inspection of MCAP index records; message chunks remain opaque."""
import hashlib
import struct
import zlib
from pathlib import Path

from ..model import canonical, require
from .bundle import make_bundle, read_file

MAGIC = b'\x89MCAP0\r\n'
FRAME = struct.Struct('<BQ')
STATS = struct.Struct('<QHIIIIQQI')


def valid(condition):
    require(condition, 'invalid_input', 'Malformed MCAP record or inconsistent index')


def frame(data, pos, limit):
    valid(pos + FRAME.size <= limit)
    opcode, length = FRAME.unpack_from(data, pos)
    start = pos + FRAME.size
    end = start + length
    valid(end <= limit)
    return opcode, data[start:end], end


def string(data, pos):
    valid(pos + 4 <= len(data))
    size, = struct.unpack_from('<I', data, pos)
    end = pos + 4 + size
    valid(end <= len(data))
    require(size <= 4096, 'acquisition_limit', 'Oversized MCAP label')
    try:
        value = bytes(data[pos+4:end]).decode('utf-8')
    except UnicodeDecodeError:
        valid(False)
    return value, end


def summary(raw):
    valid(raw.startswith(MAGIC) and raw.endswith(MAGIC))
    data = memoryview(raw)
    footer = len(data) - len(MAGIC) - FRAME.size - 20
    op, header, header_end = frame(data, len(MAGIC), footer)
    valid(op == 1)
    profile, pos = string(header, 0)
    library, pos = string(header, pos)
    op, tail, end = frame(data, footer, len(data)-len(MAGIC))
    valid(op == 2 and len(tail) == 20 and end == len(data)-len(MAGIC))
    start, offsets, checksum = struct.unpack('<QQI', tail)
    valid((not start or header_end <= start < footer) and (not offsets or start and start <= offsets < footer))
    boundary = start or footer
    # DataEnd is the final framed data record. Skip message contents and compressed chunks.
    pos = header_end
    count = 0
    while pos < boundary:
        op, body, next_pos = frame(data, pos, boundary)
        valid((op == 15) == (next_pos == boundary))
        if op == 15:
            valid(len(body) >= 4)
            crc, = struct.unpack_from('<I', body)
            valid(not crc or crc == zlib.crc32(data[:pos]))
        pos = next_pos
        count += 1
        require(count <= 250000, 'acquisition_limit', 'Too many MCAP data records')
    valid(count > 0)
    valid(not checksum or checksum == zlib.crc32(data[boundary:footer+FRAME.size+16]))
    channels, stats, counts = {}, None, {}
    pos = boundary
    limit = offsets or footer
    while pos < limit:
        op, body, pos = frame(data, pos, limit)
        count += 1
        require(count <= 260000, 'acquisition_limit', 'Too many MCAP index records')
        if op == 4:
            valid(len(body) >= 4)
            ident, schema = struct.unpack_from('<HH', body)
            topic, field = string(body, 4)
            encoding, field = string(body, field)
            valid(field + 4 <= len(body) and field + 4 + struct.unpack_from('<I', body, field)[0] <= len(body))
            valid(ident not in channels)
            require(len(channels) < 1024, 'acquisition_limit', 'Too many indexed MCAP channels')
            channels[ident] = {'channel_id': ident, 'schema_id': schema, 'topic': topic, 'encoding': encoding}
        elif op == 11:
            valid(stats is None and len(body) >= STATS.size)
            n, _, n_channels, _, _, _, t0, t1, length = STATS.unpack_from(body)
            valid(t0 <= t1 and length % 10 == 0 and STATS.size + length <= len(body))
            valid(length <= 10*1024)
            for ident, value in struct.iter_unpack('<HQ', body[STATS.size:STATS.size+length]):
                valid(ident not in counts and ident in channels)
                counts[ident] = value
            valid(not counts or sum(counts.values()) == n)
            stats = {'message_count': n, 'channel_count': n_channels, 'start_ns': t0, 'end_ns': t1}
    while pos < footer:
        op, body, pos = frame(data, pos, footer)
        valid(op == 14 and len(body) >= 17)
        count += 1
        require(count <= 260000, 'acquisition_limit', 'Too many MCAP index records')
    for ident, channel in channels.items():
        channel['message_count'] = counts.get(ident)
    return {'profile': profile, 'writer': library, 'has_summary': bool(start),
            'statistics': stats, 'channels': list(channels.values())}


def capture_mcap(root, path, source_id, refs):
    require(Path(path).suffix.lower() == '.mcap', 'invalid_input', 'Select an MCAP recording')
    raw = read_file(root, path)
    view = summary(raw)
    missing = ['decoded message payloads', 'live ROS graph']
    if view['statistics'] is None:
        missing.append('recorder statistics')
    if not view['channels']:
        missing.append('indexed channels')
    return make_bundle('mcap', source_id, {'recording/'+path: raw, 'summary.json': canonical(view).encode()},
                       refs, {'summary.json': ['/profile', '/statistics']},
                       source={'kind':'saved_mcap_recording', 'recording':path, 'profile':view['profile']},
                       source_revision=hashlib.sha256(raw).hexdigest(), missing=missing)
