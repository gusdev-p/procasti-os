"""

POPI
      P         O  P       I
      |         |  |       |
    ( Procasti!_OS Package Installer )

made by: gusdev
version: v1

"""

#libs
import sys
import subprocess as sub
from pathlib import Path as p
import requests
import tarfile
from configparser import ConfigParser
import os
import datetime
from tqdm import tqdm
import json
import shutil
import gnupg
import tempfile
import hashlib

# ==============================
# GLOBAL VARIABLES AND CONFIGS
# ==============================
# TODO: edit paths to global paths to compile
config_file : str = "/home/gustavo/nada-naum/popi/etc/popi.d/settings.cfg"
date = datetime.date.today()

# NOTE: this is the default values from file.
# TODO: edit the 'logs_path' to the real default to compile
logs = True
verbose = True
exit_in_error = True
logs_path = "/home/gustavo/nada-naum/popi/var"
repo_link = ""
test_link = ""
# TODO: edit this for a global path
popi_public_key = "/home/gustavo/nada-naum/popi/etc/popi.d/key.asc"
original_key = "/home/gustavo/nada-naum/popi/etc/popi.d/key.asc"
temp_dir = "/tmp"
expected_fp = ""
installed_packages = ""
modules = ""

# open config file
config = ConfigParser()
config.read(config_file)

# define the configs
logs = config["Behavior"].getboolean("logs")
verbose = config["Behavior"].getboolean("verbose")
exit_in_error = config["Behavior"].getboolean("exit_in_error")
logs_path = config["Paths"]["logs_path"]
repo_link = config["Repository"]["main"]
test_link = config["Repository"]["test"]
popi_public_key = config["POPI"]["popi_public_key"]
temp_dir = config["Paths"]["temp_dir"]
expected_fp = config["POPI"]["expected_fp"]
installed_packages = config["Paths"]["installed_packages"]
modules = config["Paths"]["modules"]

# ========================
# PRINT DEFS
# ========================
def info(msg: str):
    to_print = f"=>\033[32m[INFO]\033[0m: {msg}"
    hour = datetime.datetime.now().strftime("%H:%M:%S")
    to_log = f"[INFO]: {msg}"
    if verbose == True:
        print(to_print)
    if logs == True:
        with open(f"{logs_path}/{date}", "a") as log:
            log.write(f"[{hour}] - {to_log}\n")

def warn(msg: str):
    to_print = f"==>\033[33m[WARNING]\033[0m: {msg}"
    hour = datetime.datetime.now().strftime("%H:%M:%S")
    to_log = f"[WARNING]: {msg}"
    if verbose == True:
        print(to_print)
    if logs == True:
        with open(f"{logs_path}/{date}", "a") as log:
            log.write(f"[{hour}] - {to_log}\n")

def error(msg: str, exit: int):
    to_print = f"->\033[31m[ERROR]\033[0m: {msg}"
    hour = datetime.datetime.now().strftime("%H:%M:%S")
    to_log = f"[ERROR]: {msg}"
    if verbose == True:
        print(to_print)
    if logs == True:
        with open(f"{logs_path}/{date}", "a") as log:
            log.write(f"[{hour}] - {to_log}\n")
    if exit_in_error == True:
        print(f"Closing with exitcode: {exit}")
        sys.exit(exit)

def usage():
    print("""POPI Usage:
popi [OPERATION(install, remove, update, help, version)] [PACKAGE(s)]
for more info use 'popi help me'
""")
    sys.exit(6)
    
def about():
    print("""\033[35m
POPI\033[33m
      P         O  P       I
      |         |  |       |
    ( Procasti!_OS Package Installer )\033[]0m
Version: v1
Made by: gusdev
""")

# TODO: make a better exit codes system before compile
def help():
    print("""POPI help.
Usage:
    popi [OPERATION(install, remote, update)] [PACKAGE(s)]
Exit codes:
    user:
        1: user aborted
        2: bad answer ( too much or too few arguments )
        3: invalid answer
    POPI:
        4: user is not root
    installing:
        5: Timeout while downloading
        6: Network error while downloading
        7: Unknown HTTP error
        extracting:
            8: Invalid or corrupted archive
            9: Unsupported or broken compression format
            10: Unknown tar error while extracting
        Checking GPG Key:
            11: The specified key does not exist
            12: The keys dont match
        Checking SHA256:
            13: The SHA256 dont match
            14: The specified archive does not exist
        Opening Manifest:
            15: Dont have a essential section
            16: Dont exist a manifest
            17: The manifest is corrupteds
    Removing:
        18: The package script directory is a file
        19: The package script directory dont exist
        20: Cant delete the package script directory
    Updating:
        21: The package script directory is a file
        22: The package script directory dont exist
        23: Cant delete the package script directory
    List:
        24: Invalid answer ( the specified list dont exist )
        25: The 'installed packages' directory is not a directory
""")

# ======================
# EXTRA AND CHECKS DEFS
# ======================
def normal(text: str):
    return text.replace(" ", "").lower()

def check_sha(path: str, sha_to_check: str):
    sha256 = hashlib.sha256()
    size = os.path.getsize(path)
    try:
        with open(path, "rb") as f, tqdm(
                total=size,
                unit="B",
                unit_scale=True,
                desc="Checking SHA256..."
            ) as bar:
            for block in iter(lambda: f.read(8192), b""):
                sha256.update(block)
                bar.update(len(block))
    except FileNotFoundError:
        error("The specified archive does not exist :(", 14)
    if isinstance(sha_to_check, bytes):
        sha_to_check = sha_to_check.decode("utf-8")
    sha_calculated = sha256.hexdigest()

    return sha_calculated == sha_to_check

# =========================
# CHECK ROOT
# =========================
if os.geteuid() == 0:
    pass
else:
    error("To execute POPI you must be root!", 4)

# define argc
argc = len(sys.argv)

# ======================
# CHECK ARGUMNETS
# ======================
if argc < 3:
    match sys.argv[1]:
        case "help":
            help()
        case "about"|"version":
            about()
        case _:
            usage()
elif argc > 3:
    error("You can operate only one package :(", 2)


operation = sys.argv[1]
package_to_operate = sys.argv[2]


# search operation
match operation:
    # =======================
    # INSTALL
    # =======================
    case "install":
        info("Creating cache...")
        with tempfile.TemporaryDirectory(dir=temp_dir) as cache:
            info(f"Cache created in '{cache}'.")
            info("Creating essential directories...")
            essential_dirs = [
                f"{cache}/source"
                f"{cache}/key"
                f"{cache}/extracted"
            ]
            for dir in essential_dirs:
                os.makedirs(dir, exist_ok=True)
            info("Created!")
            info("Setting up downloader...")
            downloaded_dir = f"{cache}/source/{package_to_operate}.tar.gz"
            extracted_key_dir = f"{cache}/key"
            extracted_dir = f"{cache}/extracted"
            key_path = f"{extracted_key_dir}/{package_to_operate}/{package_to_operate}.tar.gz.sig"
            file_path = f"{extracted_key_dir}/{package_to_operate}/{package_to_operate}.tar.gz"
            package_root = f"{extracted_dir}/{package_to_operate}"
            package_sha256 = f"{extracted_key_dir}/{package_to_operate}/sha256"
            try:
                r = requests.get(f"{repo_link}/{package_to_operate}.tar.gz/download", stream=True, timeout=50)
                total = int(r.headers.get("Content-length", 0))
                with open(downloaded_dir, "wb") as f, tqdm(                            total=total, unit="B", unit_scale=True, desc="Donwloading..."
                    ) as bar:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            bar.update(len(chunk))
            except requests.exceptions.Timeout:
                error("Timeout during download :(", 5)
            except requests.exceptions.ConnectionError:
                error("Network error during download :(", 6)
            except requests.exceptions.HTTPError as e:
                error(f"Unkown HTTP error: {e}", 7)
            info("Package downloaded!")
            info("Extracting key and package base...")
            try:
                with tarfile.open(downloaded_dir, "r:gz") as tar:
                    tar.extractall(extracted_key_dir, filter="fully_trusted")
            except tarfile.ReadError:
                error("Invalid or corrupted archive :(", 8)
            except tarfile.CompressionError:
                error("Unsupported or broken compression format :(", 9)
            except tarfile.TarError as e:
                error(f"Unknown tar error: {e}", 10)
            info("Key and package base extracted!")
            info("Creating GPG checker cache...")
            gpg = gnupg.GPG(gnupghome=tempfile.mkdtemp())
            try:
                with open(popi_public_key, "r") as f:
                    key_data = f.read()
            except FileNotFoundError:
                error("The specified key does not exist :(", 11)
            gpg.import_keys(key_data)
            info("Checking if the keys match...")
            with open(key_path, "rb") as sig:
                verified = gpg.verify_file(sig, file_path)
                if verified.valid and normal(verified.fingerprint) == normal(expected_fp):
                    info("The keys match!")
                else:
                    error("The keys dont match :(\nFor security reasons we will not install the package.", 12)
            info("Checking SHA256...")
            with open(package_sha256, "rb") as f:
                sha_to_check = f.read().strip().split()[0]
            if check_sha(file_path, sha_to_check):
                info("The SHA256 match!")
            else:
                error("The SHA256 dont match :(", 13)
            info("Extracting base package..")
            try:
                with tarfile.open(file_path, "r:gz") as tar:
                    tar.extractall(extracted_dir, filter="fully_trusted")
            except tarfile.ReadError:
                error("Invalid or corrupted archive :(", 8)
            except tarfile.CompressionError:
                error("Unsupported or broken compression format :(", 9)
            except tarfile.TarError as e:
                error(f"Unknown tar error: {e}", 10)
            info("base package extracted!")
            package_manifest = f"{package_root}/manifest.json"
            info("Opening manifest...")
            try:
                with open(package_manifest, "r") as f:
                    manifest_content = json.load(f)
            except json.decoder.JSONDecodeError:
                error("The manifest archive is corrupted :(", 17)
            except FileNotFoundError:
                error("Dont exist a manifest :(", 16)
            info("Manifest opened!")
            info("Checking manifest...")
            keys_to_check = ["name", "description", "version", "developer"]
            for key_check in keys_to_check:
                if key_check not in manifest_content:
                    error(f"Dont have '{key_check}' :(", 15)
            info("Done!")
            print(f"""{"-" * 30}
[::] Package detected!
{"[⚠] Third-party GPG key detected.\nInstalling it requires root, and you proceed at your own risk." if original_key != popi_public_key else "[✓] GPG Verified."}

{manifest_content["name"]}
├───Description: {manifest_content["description"]}
├───Version: {manifest_content["version"]}
╰───Made by: {manifest_content["developer"]}
{"-" * 30}
""")
            while True:
                user_resp = input("Want install?[y/N]: ").lower().strip()
                if user_resp == "":
                    warn("No answer get. Using default 'n'.")
                    sys.exit(1)
                else:
                    match user_resp:
                        case "y"|"yes":
                            user_resp = "y"
                            break
                        case "n"|"no":
                            user_resp = "n"
                            break
            
            match user_resp:
                case "y":
                    info("Installing package...")
                    install_script = f"{package_root}/pkgtools/install.sh"
                    pkg_tools = f"{package_root}/pkgtools"
                    if p(install_script).is_file():
                        pass
                    else:
                        error("Install script not found :(", 8)
                    sub.run(["sh", install_script])
                    info("Package installed!")
                    info("Adding to 'installed packages'...")
                    try:
                        os.makedirs(installed_packages, exist_ok=True)
                    except FileExistsError:
                        pass
                    except PermissionError:
                        error("Dont have permission to create 'installed packages' direcotry :(", 8)
                    try:
                        shutil.move(pkg_tools, f"{installed_packages}/{package_to_operate}")
                    except FileExistsError:
                        warn("The package scripts already exist in 'installed packages'. Ignoring...")
                    except PermissionError:
                        error("Dont have permision to move package scripts to 'installed packages' :(", 8)
                    info("Done!")
                    info("Looks like everything is done!")
                    sys.exit(0)
                case "n":
                    info("User canceled.")
                    info("Looks like everything is done!")
                    sys.exit(1)
    case "remove":
        info("Removing package...")
        package_root = f"{installed_packages}/{package_to_operate}"
        if p(package_root).is_dir():
            info("Package found. Executing remove script...")
        else:
            if p(package_root).exists():
                error("Tha package script directory is a file :(", 18)
            else:
                error("The package script directory dont exist :(", 19)
        sub.run(["sh", f"{package_root}/remove.sh"])
        info("Done!")
        info("Removing package from 'installed packages'...")
        try:
            shutil.rmtree(f"{installed_packages}/{package_to_operate}")
        except PermissionError:
            error("Cant delete package script directory :(", 20)
        info("Looks like everything is done!")
        sys.exit(0)
    case "update":
        info("Updating package...")
        package_root = f"{installed_packages}/{package_to_operate}"
        if p(package_root).is_dir():
            info("Package found. Executing update script...")
        else:
            if p(package_root).exists():
                error("Tha package script directory is a file :(", 21)
            else:
                error("The package script direcotry dont exist :(", 22)
        sub.run(["sh", f"{package_root}/remove.sh"])
        info("Done!")
        info("Removing package from 'installed packages'...")
        try:
            shutil.rmtree(f"{installed_packages}/{package_to_operate}")
        except PermissionError:
            error("Cant delete package script directory :(", 23)
        info("Looks like everything is done!")
        sys.exit(0)
    case "list":
        match package_to_operate:
            case "packages":
                info("Getting all installed packages...")
                if p(installed_packages).is_dir():
                    pass
                else:
                    error("The 'installed packages' is not a directory", 25)
                packages_installed = []
                for package in p(installed_packages).iterdir():
                    if package.is_dir():
                        packages_installed.append(package)
                    else:
                        warn(f"The package '{package}' is not a directory")
                print("-" * 30)
                print("[::] Packages found:")
                print(installed_packages)
                for i, package in enumerate(packages_installed):
                    prefix = "├───" if i < len(packages_installed) -1 else "╰───"
                    print(prefix + package.name)
                print("-" * 30)
                info("Looks like everything is done!")
                sys.exit(0)
            case "modules":
                pass
            case _:
                pass