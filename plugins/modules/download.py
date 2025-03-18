#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = r"""
---
module: download
short_description: Download files with permission setting and checksum verification
description:
    - Downloads a file to a specified location
    - Sets file permissions
    - Verifies file checksum if provided
    - Supports decompression of various archive formats
options:
    src:
        description:
            - URL of the file to download
        type: str
        required: true
    dest:
        description:
            - Path where the file should be stored after download/decompression
        type: path
        required: true
    mode:
        description:
            - File permissions (as octal)
        type: str 
        default: '0644'
    owner:
        description:
            - Owner of the file
        type: str
    group:
        description:
            - Group of the file
        type: str
    checksum:
        description:
            - Expected checksum of the file
            - The checksum will be verified using the algorithm specified in checksum_algorithm
        type: str
    checksum_algorithm:
        description:
            - Algorithm to use for checksum verification
            - Uses the same algorithm as ansible.builtin.stat 
        type: str
        default: sha1
        choices: ['md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512']
    decompress:
        description:
            - Whether to decompress the file after download
        type: bool
        default: false
    decompress_format:
        description:
            - Force a specific decompression format
            - If not specified, the format is guessed from the file extension
            - Supported formats: zip, gz, bz2, xz, tar
        type: str
        choices: ['zip', 'gz', 'bz2', 'xz', 'tar', 'auto']
        default: 'auto'
    force:
        description:
            - Force download even if the file already exists
        type: bool
        default: false
author:
    - Your Name
"""

EXAMPLES = r"""
# Download a file and set permissions
- name: Download example file
  download:
    src: https://example.com/file.txt
    dest: /tmp/file.txt
    mode: '0644'
    owner: user
    group: group

# Download with checksum verification
- name: Download with checksum verification
  download:
    src: https://example.com/file.zip
    dest: /tmp/file.txt
    checksum: 123456789abcdef
    checksum_algorithm: sha256
    
# Download and decompress
- name: Download and extract archive
  download:
    src: https://example.com/archive.tar.gz
    dest: /opt/extracted/
    decompress: true
"""

RETURN = r"""
src:
    description: Source URL
    type: str
    returned: always
dest:
    description: Destination path
    type: str
    returned: always
checksum:
    description: Checksum of the file
    type: str
    returned: when checksum is specified
checksum_algorithm:
    description: Algorithm used for checksum verification
    type: str
    returned: when checksum is specified
decompressed:
    description: Whether the file was decompressed
    type: bool
    returned: when decompress is true
size:
    description: Size of the downloaded file
    type: int
    returned: always
"""

import os
import tempfile
import hashlib
import shutil
import tarfile
import zipfile
import gzip
import bz2
import lzma
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url


def calculate_checksum(filename, algorithm):
    """Calculate checksum for file using specified algorithm"""
    hash_map = {
        "md5": hashlib.md5(),
        "sha1": hashlib.sha1(),
        "sha224": hashlib.sha224(),
        "sha256": hashlib.sha256(),
        "sha384": hashlib.sha384(),
        "sha512": hashlib.sha512(),
    }

    if algorithm not in hash_map:
        return None

    hash_obj = hash_map[algorithm]

    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def decompress_file(src, dest, decompress_format="auto"):
    """Decompress file based on format"""
    dest_dir = os.path.dirname(dest)

    # Create destination directory if it doesn't exist
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    # Determine format if auto
    if decompress_format == "auto":
        if src.endswith(".zip"):
            decompress_format = "zip"
        elif src.endswith(".tar.gz") or src.endswith(".tgz"):
            decompress_format = "tar"
        elif src.endswith(".gz"):
            decompress_format = "gz"
        elif src.endswith(".bz2"):
            decompress_format = "bz2"
        elif src.endswith(".xz"):
            decompress_format = "xz"
        elif src.endswith(".tar"):
            decompress_format = "tar"
        else:
            return False, f"Could not determine compression format for {src}"

    try:
        # Handle different compression formats
        if decompress_format == "zip":
            with zipfile.ZipFile(src, "r") as zip_ref:
                # If dest is a directory, extract all files there
                if os.path.isdir(dest):
                    zip_ref.extractall(dest)
                # Else, extract the first file to dest
                else:
                    with open(dest, "wb") as f_out:
                        with zip_ref.open(zip_ref.namelist()[0]) as f_in:
                            shutil.copyfileobj(f_in, f_out)

        elif decompress_format == "tar":
            with tarfile.open(src) as tar_ref:
                if os.path.isdir(dest):
                    tar_ref.extractall(dest)
                else:
                    member = tar_ref.getmembers()[0]
                    with open(dest, "wb") as f_out:
                        with tar_ref.extractfile(member) as f_in:
                            shutil.copyfileobj(f_in, f_out)

        elif decompress_format == "gz":
            with gzip.open(src, "rb") as f_in:
                with open(dest, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

        elif decompress_format == "bz2":
            with bz2.open(src, "rb") as f_in:
                with open(dest, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

        elif decompress_format == "xz":
            with lzma.open(src, "rb") as f_in:
                with open(dest, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

        return True, None

    except Exception as e:
        return False, str(e)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            src=dict(type="str", required=True),
            dest=dict(type="path", required=True),
            mode=dict(type="str", default="0644"),
            owner=dict(type="str"),
            group=dict(type="str"),
            checksum=dict(type="str"),
            checksum_algorithm=dict(
                type="str",
                default="sha1",
                choices=["md5", "sha1", "sha224", "sha256", "sha384", "sha512"],
            ),
            decompress=dict(type="bool", default=False),
            decompress_format=dict(
                type="str",
                default="auto",
                choices=["zip", "gz", "bz2", "xz", "tar", "auto"],
            ),
            force=dict(type="bool", default=False),
        ),
        supports_check_mode=False,
    )

    src = module.params["src"]
    dest = module.params["dest"]
    mode = module.params["mode"]
    owner = module.params["owner"]
    group = module.params["group"]
    checksum_value = module.params["checksum"]
    checksum_algorithm = module.params["checksum_algorithm"]
    decompress = module.params["decompress"]
    decompress_format = module.params["decompress_format"]
    force = module.params["force"]

    result = dict(changed=False, src=src, dest=dest)

    # Handle checksum related values in result
    if checksum_value:
        result["checksum"] = checksum_value
        result["checksum_algorithm"] = checksum_algorithm

    # Check if file exists and if we need to download it
    needs_download = True
    if os.path.exists(dest) and not force:
        # If checksum is provided, verify it
        if checksum_value:
            actual_checksum = calculate_checksum(dest, checksum_algorithm)
            needs_download = actual_checksum != checksum_value
        else:
            needs_download = False

    # Download file if needed
    if needs_download:
        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(prefix="ansible_download_")
        os.close(temp_fd)

        try:
            # Download file
            response, info = fetch_url(module, src)
            if info["status"] != 200:
                module.fail_json(
                    msg=f"Failed to download file: {info['msg']}", **result
                )

            with open(temp_path, "wb") as f:
                f.write(response.read())

            # Verify checksum if provided
            if checksum_value:
                actual_checksum = calculate_checksum(temp_path, checksum_algorithm)
                if actual_checksum != checksum_value:
                    module.fail_json(
                        msg=f"Checksum verification failed. Expected: {checksum_value}, Got: {actual_checksum}",
                        **result,
                    )

            # Handle decompression if requested
            if decompress:
                # Create another temp file/dir for decompression
                if os.path.isdir(dest):
                    temp_extract_dir = tempfile.mkdtemp(
                        prefix="ansible_download_extract_"
                    )
                    success, error_msg = decompress_file(
                        temp_path, temp_extract_dir, decompress_format
                    )
                    if not success:
                        module.fail_json(
                            msg=f"Decompression failed: {error_msg}", **result
                        )

                    # Ensure destination directory exists
                    if not os.path.exists(dest):
                        os.makedirs(dest)

                    # Move extracted contents to destination
                    for item in os.listdir(temp_extract_dir):
                        src_path = os.path.join(temp_extract_dir, item)
                        dst_path = os.path.join(dest, item)
                        if os.path.exists(dst_path):
                            if os.path.isdir(dst_path):
                                shutil.rmtree(dst_path)
                            else:
                                os.unlink(dst_path)
                        if os.path.isdir(src_path):
                            shutil.copytree(src_path, dst_path)
                        else:
                            shutil.copy2(src_path, dst_path)

                    # Cleanup temp extraction dir
                    shutil.rmtree(temp_extract_dir)
                else:
                    temp_extract_path = tempfile.mktemp(
                        prefix="ansible_download_extract_"
                    )
                    success, error_msg = decompress_file(
                        temp_path, temp_extract_path, decompress_format
                    )
                    if not success:
                        module.fail_json(
                            msg=f"Decompression failed: {error_msg}", **result
                        )

                    # Ensure destination directory exists
                    dest_dir = os.path.dirname(dest)
                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir)

                    # Move decompressed file to destination
                    if os.path.exists(dest):
                        os.unlink(dest)
                    shutil.move(temp_extract_path, dest)

                result["decompressed"] = True
            else:
                # Ensure destination directory exists
                dest_dir = os.path.dirname(dest)
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)

                # Move downloaded file to destination
                if os.path.exists(dest):
                    os.unlink(dest)
                shutil.move(temp_path, dest)

            result["size"] = os.path.getsize(dest)
            result["changed"] = True

        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    # Set file permissions
    file_args = module.load_file_common_arguments(module.params)
    if module.set_fs_attributes_if_different(file_args, False):
        result["changed"] = True

    module.exit_json(**result)


if __name__ == "__main__":
    main()
