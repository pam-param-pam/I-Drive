from .ZipBase import ZipBase

class ZipFly(ZipBase):

    def calculate_archive_size(self):
        LOCAL_FILE_HEADER_SIZE = 30
        DATA_DESCRIPTOR_SIZE = 16
        CENTRAL_DIR_HEADER_SIZE = 46
        ZIP64_EXTRA_FIELD_SIZE = 32
        ZIP64_END_OF_CENTRAL_DIR_RECORD_SIZE = 56
        ZIP64_END_OF_CENTRAL_DIR_LOCATOR_SIZE = 20
        EOCD_RECORD_SIZE = 22

        total_size = 0
        central_directory_size = 0

        for file in self.files:
            local_file_header_size = LOCAL_FILE_HEADER_SIZE + len(file.file_path_bytes)

            central_directory_header_size = CENTRAL_DIR_HEADER_SIZE + len(file.file_path_bytes) + ZIP64_EXTRA_FIELD_SIZE

            total_size += local_file_header_size
            total_size += file.size
            total_size += DATA_DESCRIPTOR_SIZE

            central_directory_size += central_directory_header_size

            # todo somewhere im adding 8 bytes too little per file.
            total_size += 8

        total_size += central_directory_size

        total_size += ZIP64_END_OF_CENTRAL_DIR_RECORD_SIZE
        total_size += ZIP64_END_OF_CENTRAL_DIR_LOCATOR_SIZE
        total_size += EOCD_RECORD_SIZE

        return total_size

