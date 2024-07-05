from collections import namedtuple
import struct

# ZIP CONSTANTS
ZIP32_VERSION = 20
ZIP64_VERSION = 45
ZIP32_LIMIT = (1 << 31) - 1
UTF8_FLAG = 0x800  # utf-8 filename encoding flag

# ZIP COMPRESSION METHODS
COMPRESSION_STORE = 0
COMPRESSION_DEFLATE = 8
COMPRESSION_BZIP2 = 12
COMPRESSION_LZMA = 14

# FILE HEADER
# READ MORE AT 4.3.12  Central directory structure
LOCAL_FILE_STRUCT = struct.Struct(b"<4sHHHHHLLLHH")
LOCAL_FILE_TUPLE = namedtuple("fileheader",
                              ("signature", "version", "flags",
                               "compression", "mod_time", "mod_date",
                               "crc", "comp_size", "uncomp_size",
                               "fname_len", "extra_len"))
LOCAL_FILE_SIGNATURE = b'\x50\x4b\x03\x04'

# EXTRA FIELDS
EXTRA_STRUCT = struct.Struct(b"<HH")
EXTRA_TUPLE = namedtuple("extra", ("signature", "size"))
EXTRA_64_STRUCT = struct.Struct(b"<HH")
EXTRA_64_TUPLE = namedtuple("extra64local", ("uncomp_size", "comp_size"))
CENTRAL_DIR_EXTRA_64_STRUCT = struct.Struct(b"<HHH")
CENTRAL_DIR_EXTRA_64_TUPLE = namedtuple(
    "extra64cdir", ("uncomp_size", "comp_size", "offset"))

# FILE DESCRIPTOR
DATA_DESCRIPTOR_STRUCT = struct.Struct(b"<LLL")
DATA_DESCRIPTOR_STRUCT64 = struct.Struct(b"<LQQ")
DATA_DESCRIPTOR_TUPLE = namedtuple("filecrc", ("crc", "comp_size", "uncomp_size"))
DATA_DESCRIPTOR_SIGNATURE = b'\x50\x4b\x07\x08'

# CENTRAL DIRECTORY FILE HEADER
CENTRAL_DIR_LOCAL_FILE_STRUCT = struct.Struct(b"<4sBBHHHHHLLLHHHHHLL")
CENTRAL_DIR_LOCAL_FILE_TUPLE = namedtuple("cdfileheader",
                                          ("signature", "system", "version", "version_ndd", "flags",
                                           "compression", "mod_time", "mod_date", "crc",
                                           "comp_size", "uncomp_size", "fname_len", "extra_len",
                                           "fcomm_len", "disk_start", "attrs_int", "attrs_ext", "offset"))
CENTRAL_DIR_FILE_HEADER_SIGNATURE = b'\x50\x4b\x01\x02'

# END OF CENTRAL DIRECTORY RECORD
# CENTRAL_DIR_END_STRUCT = struct.Struct(b"<4sHHHHLLH")
# CENTRAL_DIR_END_TUPLE = namedtuple("cdend",
#                                    ("signature", "disk_num", "disk_cdstart", "disk_entries",
#                                     "total_entries", "cd_size", "cd_offset", "comment_len"))
# CENTRAL_DIR_END_SIGNATURE = b'\x50\x4b\x05\x06'

ZIP64_END_STRUCT = struct.Struct(b"<4sQHHIIQQQQQ")
ZIP64_END_TUPLE = namedtuple("zip64end",
                             ("signature", "size_of_zip64_end_of_central_dir_record", "version_made_by", "version_needed_to_extract",
                              "number_of_this_disk", "cd_start", "cd_entries_this_disk", "cd_entries_total",
                              "cd_size", "cd_offset"))
ZIP64_END_SIGNATURE = b'\x50\x4b\x06\x06'
