#!/usr/bin/python3

# Installs pip packages and copies over common packages for each Lambda function in /lambdas
# - Performs a pip install of all packages listed in /lambdas/<function>/lib/pip.txt
# - Copies common package for all packages listed in /lambdas/<function>/lib/common.txt
# - Common packages are stored in /lambdas/_common

# Mac user:
# vim ~/.pydistutils.cfg
#   [install]
#   prefix=

from os.path import dirname, join, abspath, isdir, exists
from os import listdir
import shutil
import sys
import subprocess


# Install python package to destination directory
def __pip_install(package_name, destination_dir):
    print("> Installing package '{}'".format(package_name))
    subprocess.check_call(['pip3', 'install', package_name, '-t', destination_dir])


# Copy module from source to destination directory
def __copy_package(package_name, source_dir, destination_dir):
    print("> Copying package '{}'".format(package_name))
    destination_dir = join(destination_dir, package_name)
    source_dir = join(source_dir, package_name)

    # Delete the directory if it already exists
    if exists(destination_dir):
        shutil.rmtree(destination_dir)

    # Copy the directory tree
    shutil.copytree(source_dir, destination_dir + "/")


# Read lines from a file, stripping whitespace and ignoring empty lines
def __read_lines(file_path):
    # Open specified file and read all lines
    try:
        with open(file_path) as file:
            file_lines = file.readlines()
    except Exception:
        file_lines = []

    # Strip whitespace from each line
    file_lines = [x.strip() for x in file_lines]

    # Ignore empty lines
    file_lines = list(filter(lambda x: x != "", file_lines))

    return file_lines


BASE_DIR = dirname(dirname(abspath(__file__)))
lambdas_dir = join(BASE_DIR, "lambdas")
common_packages_dir = join(BASE_DIR, "lambdas", "_common")

mode = "all"
if len(sys.argv) >= 2:
    mode = sys.argv[1]

for function_name in listdir(lambdas_dir):
    if function_name == "_common":
        continue

    function_lib_path = join(lambdas_dir, function_name, "lib")
    if not isdir(function_lib_path):
        continue

    print("=== Installing dependencies for Lambda function {} ===".format(function_name))

    # Install pip packages
    if mode in ["all", "pip"]:
        for package_name in __read_lines(join(function_lib_path, "pip.txt")):
            __pip_install(package_name, function_lib_path)

    # Copy common packages
    if mode in ["all", "common"]:
        for package_name in __read_lines(join(function_lib_path, "common.txt")):
            __copy_package(package_name, common_packages_dir, function_lib_path)

    print()
