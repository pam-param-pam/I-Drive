from collections import defaultdict
from typing import List

from zipFly import consts
from zipFly.BaseFile import BaseFile

"""
Since the Official ZIP docs are terrible, here's a detailed structure of the zip this library builds. (pretty sure mine's just as bad lol)

  [local file header 1]            |
  [file data 1]                    |
  [data descriptor 1]              |
  .                                |
  .                                } - This part of the of zip holds the file data. Local file headers are lowkey useless(nevertheless needed for zip to work).
  .                                |        Data descriptors allow to stream the file(and create file headers) without knowing the size of file data. Instead of putting
  [local file header n]            |        things like: CRC, uncompressed_size, compressed_size etc in file headers, you only put placeholder values there (0xFFFFFFFF),                                    
  [file data n]                    |        and fill them later in data descriptor.
  [data descriptor n]              |
  
  
  =================This part is called Central Directory Structure==============                               <------------ TO HERE -------------------------------------------<
                                                                                                                                                                                |
  [central directory header 1]     |                                                                                                                                            |
  [extra field 1]                  |                                                                                                                                            |
  .                                } - I have no idea why it's called 'central directory header'. It should be called central directory file headers.                           |
  .                                |        From now on, i will call central directory as just 'cdir'. Cdir headers are structures that again hold the file information         |   
  .                                |        Cdir headers are retarded, and their compressed_size, uncompressed_size, offset values are in 4 bytes, meaning you can't put        |
  [central directory header n]     |        values > 4GB. Hence the ZIP64 uses a special structure called 'extra field'. Just like before, in cdir headers we put               |
  [extra field n]                  |        placeholder values, and fill them later in extra field.                                                                             |
                                                                                                                                                                                |
                                            An important thing to pay attention in cdir header, is **offset**. This offset is the amount of bytes from the                      |
                                            beginning of the file, to the start of local file header. So for 1st file the offset is 0, for the 2nd it's length of               |
                                            '[local file header 1]' + '[file data 1]' + '[data descriptor 1]'.                                                                  |
                                                                                                                                                                                |
  =================This part I call End of Central Directory Structure (It's still a part of cdir structure(I think))===============            <----- TO HERE -----------------|-----------<
                                                                                                                                                                                |           |
  [zip64 end of central directory record]    |                                                                                                                                  |           |
  [zip64 end of central directory locator]   } - This is the actual end of the file. End of cdir directory record is a legacy(and kinda useless, nevertheless required).        |           |
  [end of central directory record]          |      Size we work with files >4GB, the end of cdir directory record, again can't hold values like: compressed_size,              |           |
                                                    uncompressed_size, offset. We again use placeholder values, and put the actual ones in                                      |           |
                                                    'zip64 end of central directory record'. 'zip64 end of cdir locator' is used to locate the 'zip64 end of cdir record'.      |           |
                                                                                                                                                                                |           |
                                                    An important thing to pay attention to are **offsets*. There are two district ones here.                                    |           |
                                                    1st offset is in 'zip64 end of cdir record'. It's the amount of bytes from the start of the file to start of   ------------->           |
                                                    *Central Directory Structure*.                                                                                                          |
                                                    2nd offset is in 'zip64 end of cdir locator'. It's the amount of bytes from the start of the file to start of -------------------------->
                                                    'zip64 end of cdir record'.
                                                    
                                                    
    Other goofy things are:
        'extra_field_len' in 'central directory header' is 32, even tho in the 'extra field' it self, the 'extra_field_size' is 28. That's because the first
        is the full length of the 'extra field' structure, while the second doesn't not include 'extra_field_size' and
        'signature' which are each 2 bytes, so together they are the 'missing' 4 bytes.
        
        'size_of_zip64_end_of_cdir_record' in zip64 end of cdir record is 44 bytes. Cuz: 'signature' - 4 bytes, 'size_of_zip64_end_of_central_dir_record' - 8 bytes,
        'version_made_by' - 2 bytes, 'version_to_extract' - 2 bytes, 'number_of_this_disk' - 4 bytes, 'cd_start' - 4 bytes, 'cd_entries_this_disk' - 8 bytes, 
        'cd_entries_total' - 8 bytes, 'cd_size' - 8 bytes, 'cd_offset' - 8 bytes.
        So, 4 + 8 + 2 + 2 + 4 + 4 + 8 + 8 + 8 + 8 = 56, but we again don't include signature, and 'size_of_zip64_end_of_central_dir_record' so 56 - 4 - 8 = 44
        
I hope, that i made it a bit more clear to anyone reading, including future me.        
"""


def process_file_names(files):
    name_counts = defaultdict(int)
    for file in files:
        # Split the name into base and extension
        base, ext = file.name.rsplit('.', 1) if '.' in file.name else (file.name, '')

        # Increment the count for this base name
        name_counts[base] += 1

        # Append the count to the base name if it's not the first occurrence
        if name_counts[base] > 1:
            new_base = f"{base} ({name_counts[base] - 1})"
        else:
            new_base = base

        # Reassemble the filename
        file.set_file_name(f"{new_base}.{ext}" if ext else new_base)

    return files


class ZipBase:

    def __init__(self, files: List[BaseFile]):
        self.__version_to_extract = 45

        # process file names to make sure there are no duplicates
        processed_files = process_file_names(files)
        self.files = processed_files

        self.__offset = 0  # Tracks the current offset within the ZIP archive
        self.__cdir_size = 0
        self.__offset_to_start_of_central_dir = 0
        self.__version_made_by = 0x0345  # UNIX and ZIP version 45

    def _make_local_file_header(self, file: BaseFile) -> bytes:
        """
        Create local file header for a ZIP64 archive   (4.3.7)
        """

        fields = {
            "signature": consts.LOCAL_FILE_HEADER_SIGNATURE,
            "version_to_extract": self.__version_to_extract,
            "flags": file.flags,
            "compression": file.compression_method,
            "mod_time": file.get_mod_time(),
            "mod_date": file.get_mod_date(),
            "crc": 0xFFFFFFFF,  # Placeholder (will be updated in data descriptor)
            "uncompressed_size": 0xFFFFFFFF,  # Placeholder (will be updated in data descriptor)
            "compressed_size": 0xFFFFFFFF,  # Placeholder (will be updated in data descriptor)
            "file_name_len": len(file.file_path_bytes),
            "extra_field_len": 0  # 0 cuz no extra field is used with local file header
        }

        # Pack the local file header structure
        header = consts.LOCAL_FILE_HEADER_TUPLE(**fields)
        header = consts.LOCAL_FILE_HEADER_STRUCT.pack(*header)
        header += file.file_path_bytes

        return header

    def _make_data_descriptor(self, file: BaseFile) -> bytes:
        """
        Create data descriptor.  (4.3.9)
        """

        fields = {
            "signature": consts.ZIP64_DATA_DESCRIPTOR_SIGNATURE,
            "crc": file.crc & 0xffffffff,  # hack for making CRC unsigned long
            "uncompressed_size": file.original_size,
            "compressed_size": file.compressed_size,
        }

        descriptor = consts.ZIP64_DATA_DESCRIPTOR_TUPLE(**fields)
        descriptor = consts.ZIP64_DATA_DESCRIPTOR_STRUCT.pack(*descriptor)

        return descriptor

    def _make_cdir_file_header(self, file: BaseFile) -> bytes:
        """
        Create central directory file header for ZIP64 archive.  (4.3.12)
        """
        fields = {
            "signature": consts.CENTRAL_DIR_FILE_HEADER_SIGNATURE,
            "version_made_by": self.__version_made_by,
            "version_to_extract": self.__version_to_extract,
            "flags": file.flags,
            "compression": file.compression_method,
            "mod_time": file.get_mod_time(),
            "mod_date": file.get_mod_date(),
            "crc": file.crc,
            "compressed_size": 0xFFFFFFFF,  # Placeholder (will be updated in zip64 extra field)
            "uncompressed_size": 0xFFFFFFFF,  # Placeholder (will be updated in zip64 extra field)
            "file_name_len": len(file.file_path_bytes),
            "extra_field_len": 32,
            "file_comment_len": 0,
            "disk_start": 0,
            "internal_file_attr": 0,
            "external_file_attr": 0,
            "offset": 0xFFFFFFFF  # Placeholder (will be updated in zip64 extra field)
        }

        cdfh = consts.CENTRAL_DIR_FILE_HEADER_TUPLE(**fields)
        cdfh = consts.CENTRAL_DIR_FILE_HEADER_STRUCT.pack(*cdfh)
        cdfh += file.file_path_bytes

        return cdfh

    def _make_zip64_extra_field(self, file: BaseFile) -> bytes:
        """
        Create the ZIP64 extra field.  (4.5.3)
        """
        fields = {
            "signature": consts.ZIP64_EXTRA_FIELD_SIGNATURE,
            "extra_field_size": 28,
            "size": file.original_size,
            "compressed_size": file.compressed_size,
            "offset": file.offset,
            "disk_start": 0
        }

        extra = consts.ZIP64_EXTRA_FIELD_TUPLE(**fields)
        extra = consts.ZIP64_EXTRA_FIELD_STRUCT.pack(*extra)

        return extra

    def _make_zip64_end_of_cdir_record(self) -> bytes:
        """
        Create the ZIP64 end of central directory record.  (4.3.14)
        """
        fields = {
            "signature": consts.ZIP64_END_OF_CENTRAL_DIR_RECORD_SIGNATURE,
            "size_of_zip64_end_of_cdir_record": 44,  # 44 bytes for the ZIP64 end of central directory record itself
            "version_made_by": self.__version_made_by,
            "version_to_extract": self.__version_to_extract,
            "number_of_this_disk": 0,
            "cd_start": 0,
            "cd_entries_this_disk": len(self.files),
            "cd_entries_total": len(self.files),
            "cd_size": self.__cdir_size,
            "cd_offset": self.__offset_to_start_of_central_dir
        }

        cdend = consts.ZIP64_END_OF_CENTRAL_DIR_RECORD_TUPLE(**fields)
        cdend = consts.ZIP64_END_OF_CENTRAL_DIR_RECORD_STRUCT.pack(*cdend)

        return cdend

    def _make_zip64_end_of_cdir_locator(self) -> bytes:
        """
        Create the ZIP64 end of central directory locator.  (4.3.15)
        """
        fields = {
            "signature": consts.ZIP64_END_OF_CENTRAL_DIR_LOCATOR_SIGNATURE,
            "disk_with_zip64_end": 0,
            "zip64_end_offset": self.__offset,
            "total_disks": 1
        }

        locator = consts.ZIP64_END_OF_CENTRAL_DIR_LOCATOR_TUPLE(**fields)

        locator = consts.ZIP64_END_OF_CENTRAL_DIR_LOCATOR_STRUCT.pack(*locator)

        return locator

    def _make_end_of_cdir_record(self) -> bytes:
        """
        Create the end of central directory record.  (4.3.16)
        """
        fields = {
            "signature": consts.END_OF_CENTRAL_DIR_RECORD_SIGNATURE,
            "number_of_this_disk": 0,
            "number_of_disk_with_start_central_dir": 0,
            "total_entries_on_this_disk": len(self.files),
            "total_entries_total": len(self.files),
            "central_directory_size": 0xFFFFFFFF,
            "offset_of_central_directory": 0xFFFFFFFF,
            "comment_length": 0  # No comment
        }

        eocd = consts.END_OF_CENTRAL_DIR_RECORD_TUPLE(**fields)
        eocd = consts.END_OF_CENTRAL_DIR_RECORD_STRUCT.pack(*eocd)

        return eocd

    def _add_offset(self, value: int) -> None:
        self.__offset += value

    def _stream_single_file(self, file: BaseFile) -> bytes:
        """
        stream single zip file with header and descriptor at the end.
        """
        yield self._make_local_file_header(file)

        yield from file.generate_processed_file_data()

        yield self._make_data_descriptor(file)

    def _make_end_structures(self) -> bytes:
        """
        Make zip64 end structures, which include:
            central directory file header for every file,
            zip64 extra field for every file,
            zip64 end of central dir record,
            zip64 end of central dir locator
            end of central dir record
        """
        # Save offset to start of central dir for zip64 end of cdir record
        self.__offset_to_start_of_central_dir = self.__offset

        # Stream central directory entries
        for file in self.files:
            chunk = self._make_cdir_file_header(file)
            chunk += self._make_zip64_extra_field(file)
            self.__cdir_size += len(chunk)
            self._add_offset(len(chunk))

            yield chunk

        yield self._make_zip64_end_of_cdir_record()

        yield self._make_zip64_end_of_cdir_locator()

        yield self._make_end_of_cdir_record()

    def stream(self):
        for file in self.files:
            file.offset = self.__offset
            for chunk in self._stream_single_file(file):
                self._add_offset(len(chunk))
                yield chunk

        # stream zip structures
        for chunk in self._make_end_structures():
            yield chunk
