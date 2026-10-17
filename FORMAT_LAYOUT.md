# VAGGAME2 fixed header

Python struct format:

```python
struct.Struct("<8sHHIIII32sI")
```

Fields, in order:

| Field | Type | Meaning |
|---|---|---|
| magic | 8 bytes | `VAGGAME2` |
| version | uint16 | `2` |
| header_size | uint16 | size of fixed header |
| flags | uint32 | simulator state + encoding flags |
| meta_len | uint32 | JSON metadata bytes |
| packed_len | uint32 | compressed payload bytes |
| raw_len | uint32 | original model bytes |
| raw_sha256 | 32 bytes | SHA-256 of recovered model payload |
| packed_crc32 | uint32 | CRC32 of compressed payload |

The JSON metadata immediately follows the fixed header. The compressed payload follows the metadata.
