"""Audio / video files: length, has a picture?, convert to a small audio file (Opus, ~0.25 MB per minute)."""

import av


def duration(path):
    """Length in seconds. Browser recordings (webm) often have no length in the header, so then we read
    the packet times (fast: nothing is decoded)."""
    with av.open(str(path)) as c:
        if not c.streams.audio:
            return 0.0
        if c.duration:
            return c.duration / 1_000_000
        stream = c.streams.audio[0]
        last = 0.0
        for pkt in c.demux(stream):
            if pkt.pts is not None and pkt.time_base is not None:
                last = max(last, float((pkt.pts + (pkt.duration or 0)) * pkt.time_base))
        return last


def has_video(path):
    with av.open(str(path)) as c:
        return any(s.type == "video" and (s.frames != 1) for s in c.streams)


def to_audio(src, dst, max_seconds):
    """Keep only the sound (mono Opus in .ogg, 32 kbit/s), cut at max_seconds. Videos become audio files
    like this right after analysis, which saves ~95% of the storage."""
    with av.open(str(src)) as inp, av.open(str(dst), "w", format="ogg") as out:
        ins = inp.streams.audio[0]
        ost = out.add_stream("libopus", rate=48000, layout="mono")
        ost.bit_rate = 32000
        resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)
        for frame in inp.decode(ins):
            if frame.time is not None and frame.time > max_seconds:
                break
            for f in resampler.resample(frame):
                for pkt in ost.encode(f):
                    out.mux(pkt)
        for f in resampler.resample(None):
            for pkt in ost.encode(f):
                out.mux(pkt)
        for pkt in ost.encode(None):
            out.mux(pkt)


def join_audio(srcs, dst, max_seconds):
    """Several recordings (the parts of a mock test) -> one mono Opus .ogg, in order, cut at max_seconds."""
    total = 0.0
    with av.open(str(dst), "w", format="ogg") as out:
        ost = out.add_stream("libopus", rate=48000, layout="mono")
        ost.bit_rate = 32000
        for src in srcs:
            resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)
            with av.open(str(src)) as inp:
                for frame in inp.decode(inp.streams.audio[0]):
                    for f in resampler.resample(frame):
                        if total > max_seconds:
                            break
                        total += f.samples / 48000
                        f.pts = None
                        for pkt in ost.encode(f):
                            out.mux(pkt)
                for f in resampler.resample(None):
                    f.pts = None
                    for pkt in ost.encode(f):
                        out.mux(pkt)
        for pkt in ost.encode(None):
            out.mux(pkt)
    return total
