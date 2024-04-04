import base64
import codecs
import glob
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile

import easygui
import requests
from rich.console import Console
from tqdm import tqdm

import datetime
import devdex
import extract_payload
import imgextractor
import miui
import sdat2img
import seekfd

if os.name == 'nt':
    import ctypes

    ctypes.windll.kernel32.SetConsoleTitleW("DNA-3")
else:
    sys.stdout.write("\x1b]2;DNA-3\x07")
    sys.stdout.flush()
os.system("cls" if os.name == "nt" else "clear")
if os.name != 'nt':
    import pwd

    USER = pwd.getpwuid(os.getuid()).pw_name
else:
    USER = "mio"
ASK = False
IS_ARM64 = False
IS_FIRST = 0
PWD_DIR = os.getcwd() + os.sep
MOD_DIR = PWD_DIR + "local/sub/"
ROM_DIR = PWD_DIR
SETUP_JSON = PWD_DIR + "local/set/setup.json"
MAGISK_JSON = PWD_DIR + "local/set/magisk.json"
BIN_PATH = PWD_DIR + f"local/bin/{platform.system()}/{platform.machine()}/"
INTSU = "sudo apt install "
if platform.machine() in ('aarch64', 'armv8l', 'arm64'):
    INTSU = "apt install "
    if os.path.isdir("/sdcard/Download"):
        IS_ARM64 = True
        ROM_DIR = "/sdcard/Download/"
print("固件放置路径: " + ROM_DIR)
time.sleep(1)
PASSWORD_DICT = {
    '1': "FC", '2': "0A", '3': "EF", '4': "0D", '5': "C9", '6': "8A", '7': "B3", '8': "AD", '9': "04", '0': "00"}
PASSWORD_DICT_REVERSE = {v: k for k, v in PASSWORD_DICT.items()}
SUPPORT_FSS = ('ext4', 'erofs', 'ufs', 'emmc')
BLUE, RED, WHITE, CYAN, YELLOW, MAGENTA, GREEN, BOLD, CLOSE = ('\x1b[94m', '\x1b[91m',
                                                               '\x1b[97m', '\x1b[36m',
                                                               '\x1b[93m', '\x1b[1;35m',
                                                               '\x1b[1;32m',
                                                               '\x1b[1m', '\x1b[0m')
programs = ["mv", "cp", "rm", "cat", "cpio", "brotli", "img2simg", "e2fsck", "resize2fs",
            "mke2fs", "e2fsdroid", "mkfs.erofs", "lpmake", "lpunpack", "extract.erofs", "magiskboot"]
if os.name == 'nt':
    programs = []


def change_permissions_recursive(path, mode):
    for root, dirs, files in os.walk(path):
        for d in dirs:
            os.chmod(os.path.join(root, d), mode)
        for f in files:
            os.chmod(os.path.join(root, f), mode)
    os.chmod(path, mode)


if os.path.isdir(BIN_PATH):
    os.environ["PATH"] += os.pathsep + BIN_PATH
    if os.name == 'posix':
        change_permissions_recursive(BIN_PATH, 0o777)

    for prog in programs:
        locate = shutil.which(prog)
        if not locate:
            sys.exit("[x] Not found: {0}\n[i] Please run <{1}{0}> to install \n   Or add <{0}> to {2}".format(prog,
                                                                                                              INTSU,
                                                                                                              BIN_PATH))

else:
    print("Run err on: " + platform.machine())
    sys.exit()


def call(exe, kz='Y', out=0, shstate=False, sp=0):
    cmd = f'{BIN_PATH}{exe}' if kz == "Y" else exe
    if os.name != 'posix':
        conf = subprocess.CREATE_NO_WINDOW
    else:
        if sp == 0:
            cmd = cmd.split()
        conf = 0
    try:
        ret = subprocess.Popen(cmd, shell=shstate, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, creationflags=conf)
        for i in iter(ret.stdout.readline, b""):
            if out == 0:
                print(i.decode("utf-8", "ignore").strip())
    except subprocess.CalledProcessError as e:
        ret = None
        ret.wait = print
        ret.returncode = 1
        for i in iter(e.stdout.readline, b""):
            if out == 0:
                print(i.decode("utf-8", "ignore").strip())
    ret.wait()
    return ret.returncode


class CoastTime(object):

    def __init__(self):
        self.t = 0

    def __enter__(self):
        self.t = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print(f"> Coast Time:{time.perf_counter() - self.t:.8f} s")


def PAUSE(info='> 任意键继续'):
    input(info)


def DISPLAY(message, flag=1):
    time_now = time.strftime("%H:%M:%S", time.localtime())
    message = "[ {} ]\t {}".format(time_now, message)
    if flag == 1:
        print("\x1b[1;33m" + message + "\x1b[0m")
    elif flag == 4:
        print(("\x1b[1;36m" + message), end="\x1b[0m", flush=True)
    elif flag == 3:
        print(("\x1b[1;34m" + message), end="\x1b[0m", flush=True)
    else:
        print(("\x1b[1;31m" + message), end="\x1b[0m", flush=True)


def CHAR2NUM(chars):
    result = re.sub("(?<=\\w)(?=(?:\\w\\w)+$)", " ", chars)
    chars = result.split(" ")
    res = [PASSWORD_DICT_REVERSE[r] for r in chars]
    return "".join(res)


def GETDIRSIZE(ddir, max_=1.06, flag=1):
    size = 0
    for (root, dirs, files) in os.walk(ddir):
        for name in files:
            if not os.path.islink(name):
                try:
                    size += os.path.getsize(os.path.join(root, name))
                except:
                    pass

    if flag == 1:
        return int(size * max_)
    return int(size)


def LOAD_IMAGE_JSON(dumpinfo, source_dir):
    f = open(dumpinfo, "a+", encoding="utf-8")
    f.seek(0)
    info = eval(f.read())
    f.close()
    inodes = CHAR2NUM(info["a"])
    block_size = CHAR2NUM(info["b"])
    per_group = CHAR2NUM(info["c"])
    mount_point = info["d"]
    if mount_point != "/":
        mount_point = "/" + mount_point
    fsize = info["s"]
    blocks = math.ceil(int(fsize) / int(block_size))
    dsize = GETDIRSIZE(source_dir)
    dsize = str(dsize).strip()
    if int(dsize) > int(fsize):
        minsize = int(dsize) - int(fsize)
        if int(minsize) < int(20971520):
            isize = int(int(dsize) * 1.08)
            dsize = str(isize)
    else:
        dsize = fsize
    return (
        fsize, dsize, inodes, block_size, blocks, per_group, mount_point)


def LOAD_SETUP_JSON():
    global SETUP_MANIFEST
    with codecs.open(SETUP_JSON, "r", "utf-8") as manifest_file:
        SETUP_MANIFEST = json.load(manifest_file)
    set_default_env_setup(SETUP_MANIFEST)
    validate_default_env_setup(SETUP_MANIFEST)
    with codecs.open(SETUP_JSON, "w", "utf-8") as f:
        json.dump(SETUP_MANIFEST, f, indent=4)
    if not os.path.isdir("{}local/etc/devices/{}/{}/addons".format(PWD_DIR, SETUP_MANIFEST["DEVICE_CODE"],
                                                                   SETUP_MANIFEST["ANDROID_SDK"])):
        os.makedirs("{}local/etc/devices/{}/{}/addons".format(PWD_DIR, SETUP_MANIFEST["DEVICE_CODE"],
                                                              SETUP_MANIFEST["ANDROID_SDK"]))
    if not os.path.isfile("{}local/etc/devices/{}/{}/ramdisk.cpio".format(PWD_DIR, SETUP_MANIFEST["DEVICE_CODE"],
                                                                          SETUP_MANIFEST["ANDROID_SDK"])):
        if os.name != "nt":
            os.system("touch {}local/etc/devices/{}/{}/ramdisk.cpio.txt".format(PWD_DIR, SETUP_MANIFEST["DEVICE_CODE"],
                                                                                SETUP_MANIFEST["ANDROID_SDK"]))
    if not os.path.isfile("{}local/etc/devices/{}/{}/reduce.txt".format(PWD_DIR, SETUP_MANIFEST["DEVICE_CODE"],
                                                                        SETUP_MANIFEST["ANDROID_SDK"])):
        with open("{}local/etc/devices/{}/{}/reduce.txt".format(
                PWD_DIR, SETUP_MANIFEST["DEVICE_CODE"], SETUP_MANIFEST["ANDROID_SDK"]), "w", encoding='utf-8',
                newline='\n') as f:
            f.write(
                "product/app/PhotoTable\nsystem/system/app/BasicDreams\nsystem/system/data-app/Youpin\nsystem_ext/priv-app/EmergencyInfo\nvendor/app/MiGameService\n")

    if not os.path.isfile("{}local/set/{}.json".format(PWD_DIR, SETUP_MANIFEST["DEVICE_CODE"])):
        default_device = {'name': "Xiaomi/Redmi",
                          'region': "CN",
                          'mode': "recovery",
                          'type': "develop",
                          'version': ""}
        with codecs.open("{}local/set/{}.json".format(PWD_DIR, SETUP_MANIFEST["DEVICE_CODE"]), "w", "utf-8") as f:
            json.dump(default_device, f, indent=4)
    if not os.path.isfile(MAGISK_JSON):
        default_magisk = {'CLASS': "alpha",
                          'KEEPVERITY': "true",
                          'KEEPFORCEENCRYPT': "true",
                          'PATCHVBMETAFLAG': "false",
                          'TARGET': "arm",
                          'IS_64BIT': "true"}
        with codecs.open(MAGISK_JSON, "w", "utf-8") as g:
            json.dump(default_magisk, g, indent=4)


def set_default_env_setup(SETUP_MANIFEST):
    properties = {
        'IS_VAB': "1",
        'IS_DYNAMIC': "1",
        'ANDROID_SDK': "12",
        'DEVICE_CODE': "alioth",
        'AUTHOR_INFO': "DNA",
        'REPACK_EROFS_IMG': "0",
        'REPACK_TO_RW': "0",
        'RESIZE_IMG': "0",
        'RESIZE_EROFSIMG': "0",
        'REPACK_SPARSE_IMG': "0",
        'REPACK_BR_LEVEL': "3",
        'SUPER_SIZE': "9126805504",
        'GROUP_SIZE_A': "9122611200",
        'GROUP_SIZE_B': "9122611200",
        'GROUP_NAME': "qti_dynamic_partitions",
        'SUPER_SECTOR': "2048",
        'SUPER_SPARSE': "1",
        'UTC': "LIVE",
        'UNPACK_SPLIT_DAT': "15"}
    for (property, value) in properties.items():
        if property not in SETUP_MANIFEST:
            SETUP_MANIFEST[property] = value


def validate_default_env_setup(SETUP_MANIFEST):
    for k in ('IS_VAB', 'IS_DYNAMIC', 'REPACK_EROFS_IMG', 'REPACK_SPARSE_IMG', 'REPACK_TO_RW',
              'SUPER_SPARSE', 'RESIZE_IMG'):
        if SETUP_MANIFEST[k] not in ('1', '0'):
            sys.exit("Invalid [{}] - must be one of <1/0>".format(k))

    if SETUP_MANIFEST["RESIZE_EROFSIMG"] not in ('1', '2', '0'):
        sys.exit("Invalid [RESIZE_EROFSIMG] - must be one of <1/2/0>")
    if not re.match("[\\d]{1,2}", SETUP_MANIFEST["ANDROID_SDK"]) or int(SETUP_MANIFEST["ANDROID_SDK"]) < 5:
        sys.exit("Invalid [ANDROID_SDK : {}] - must be one of <5+>".format(SETUP_MANIFEST["ANDROID_SDK"]))
    if not re.match("[0-9]", SETUP_MANIFEST["REPACK_BR_LEVEL"]):
        sys.exit("Invalid [{}] - must be one of <0-9>".format(SETUP_MANIFEST["REPACK_BR_LEVEL"]))
    if not re.match("\\d{1,3}", SETUP_MANIFEST["UNPACK_SPLIT_DAT"]):
        sys.exit(
            'Invalid ["UNPACK_SPLIT_DAT" : "{}"] - must be one of <1-999>'.format(SETUP_MANIFEST["UNPACK_SPLIT_DAT"]))


def env_setup():
    question_list = {
        '安卓版本[12]': "ANDROID_SDK",
        '机型代号[alioth]': "DEVICE_CODE",
        '作者信息[DNA]': "AUTHOR_INFO",
        '是否动态分区[1/0]': "IS_DYNAMIC",
        '是否虚拟AB分区[1/0]': "IS_VAB",
        '合成镜像类型[0:EXT4/1:EROFS]': "REPACK_EROFS_IMG",
        '合成镜像格式[0:RAW/1:SPARSE]': "REPACK_SPARSE_IMG",
        '合成SUPER镜像格式[1:SPARSE/0:RAW]': "SUPER_SPARSE",
        '合成EXT4动态分区状态[0:RO/1:RW]': "REPACK_TO_RW",
        '合成EXT4压缩分区空间[0/1]': "RESIZE_IMG",
        '合成EROFS压缩算法[0:NO/1:LZ4HC/2:LZ4]': "RESIZE_EROFSIMG",
        '压缩BROTLI等级[0-9|3]': "REPACK_BR_LEVEL",
        '动态分区簇名称[qti_dynamic_partitions]': "GROUP_NAME",
        '动态SUPER分区总大小[9126805504]': "SUPER_SIZE",
        '插槽A簇大小[9122611200]': "GROUP_SIZE_A",
        '插槽B簇大小[9122611200]': "GROUP_SIZE_B",
        '动态分区扇区大小[2048]': "SUPER_SECTOR",
        '自定义UTC时间戳[live]': "UTC",
        '分段DAT/IMG支持个数[15]': "UNPACK_SPLIT_DAT"}
    print("\n")
    print("> {0}设置文件{1}: {2}".format(GREEN, CLOSE, SETUP_JSON.replace(PWD_DIR, "")))
    SETUP_MANIFEST = {}
    for question in question_list:
        answer = input("> " + question + ": ")
        if answer:
            SETUP_MANIFEST[question_list[question]] = answer
        set_default_env_setup(SETUP_MANIFEST)
        validate_default_env_setup(SETUP_MANIFEST)

    with codecs.open(SETUP_JSON, "w", "utf-8") as f:
        json.dump(SETUP_MANIFEST, f, indent=4)


def check_permissions():
    if not os.path.isfile(SETUP_JSON):
        if not os.path.isdir(os.path.dirname(SETUP_JSON)):
            os.makedirs(os.path.dirname(SETUP_JSON))
        env_setup()
    menu_once()


def find_file(path, rule, flag=1):
    finds = []
    if flag == 1:
        for (root, lists, files) in os.walk(path):
            for file in files:
                if re.search(rule, os.path.basename(file)):
                    find = os.path.join(root, file)
                    finds.append(find)

    elif flag == 2:
        parent_depth = len(path.split(os.path.sep))
        for (parent, _, filenames) in os.walk(path, topdown=True):
            for filename in filenames:
                dirname_path = os.path.join(parent, filename)
                dirname_depth = len(dirname_path.split(os.path.sep))
                if dirname_depth == parent_depth:
                    if re.search(rule, os.path.basename(filename)):
                        finds.append(filename)

    elif flag == 3:
        for (cur_path, cur_dirs, cur_files) in os.walk(path):
            for name in cur_files:
                if name.endswith(rule):
                    finds.append(os.path.join(cur_path, name))

    elif flag == 4:
        for (parent, dirnames, filenames) in os.walk(path):
            for dirname in dirnames:
                finds.append(os.path.join(parent, dirname))

            for filename in filenames:
                finds.append(os.path.join(parent, filename))

    elif flag == 5:
        with open(path, "r") as f:
            for l in f:
                finds.append(l.split(" ")[0])

    return finds


def kill_avb(project):
    rule = "^fstab.*?"
    fstab = find_file(project, rule)
    if len(fstab) > 0:
        for tab in fstab:
            print("> 解除AVB加密: " + tab)
            with open(tab, "r") as sf:
                details = sf.read()
            details = re.sub("avb.*?,", "", details)
            details = re.sub(",avb,", ",", details)
            details = re.sub(",avb_keys=.*", "", details)
            with open(tab, "w") as tf:
                tf.write(details)


def kill_avbkey(project):
    rule = "^fstab.*?"
    fstab = find_file(project, rule)
    if len(fstab) > 0:
        for tab in fstab:
            print("> 解除AVB加密: " + tab)
            with open(tab, "r") as sf:
                details = sf.read()
            details = re.sub(",avb_keys=.*", "", details)
            with open(tab, "w") as tf:
                tf.write(details)


def kill_dm(project):
    rule = "^fstab.*?"
    fstab = find_file(project, rule)
    if len(fstab) > 0:
        for tab in fstab:
            print("> 解除DM加密: " + tab)
            with open(tab, "r") as sf:
                details = sf.read()
            details = re.sub("forceencrypt=", "encryptable=", details)
            details = re.sub(",fileencryption=.*metadata_encryption", "", details)
            with open(tab, "w") as tf:
                tf.write(details)


def patch_twrp(BOOTIMG):
    if os.path.isfile("{}local/etc/devices/{}/{}/ramdisk.cpio".format(PWD_DIR, SETUP_MANIFEST["DEVICE_CODE"],
                                                                      SETUP_MANIFEST[
                                                                          "ANDROID_SDK"])) and os.path.isfile(BOOTIMG):
        if os.path.isdir("{}bootimg".format(DNA_MAIN_DIR)):
            os.system("rm -rf {}bootimg".format(DNA_MAIN_DIR))
        os.makedirs(DNA_MAIN_DIR + "bootimg")
        print("- Unpacking boot image")
        os.chdir(DNA_MAIN_DIR + "bootimg")
        os.system("magiskboot unpack {}".format(BOOTIMG))
        if os.path.isfile("kernel"):
            if os.path.isfile("ramdisk.cpio"):
                print("- Replace ramdisk twrp@{}".format(SETUP_MANIFEST["ANDROID_SDK"]))
                os.system(
                    "cp -rf {}local/etc/devices/{}/{}/ramdisk.cpio ./".format(PWD_DIR, SETUP_MANIFEST["DEVICE_CODE"],
                                                                              SETUP_MANIFEST["ANDROID_SDK"]))
                for dt in ('dtb', 'kernel_dtb', 'extra'):
                    if os.path.isfile(dt):
                        print("- Patch fstab in {}".format(dt))
                        os.system("magiskboot dtb {} patch".format(dt))
                    os.system(
                        "magiskboot hexpatch kernel 736B69705F696E697472616D667300 77616E745F696E697472616D667300")
                    os.system("magiskboot hexpatch kernel 77616E745F696E697472616D6673 736B69705F696E697472616D6673")
                    os.system("magiskboot hexpatch kernel 747269705F696E697472616D6673 736B69705F696E697472616D6673")
                    print("- Repacking boot image")
                    os.system("magiskboot repack {}".format(BOOTIMG))

                if os.path.isfile("new-boot.img"):
                    print("+ Done")
                    if not os.path.isdir(DNA_DIST_DIR):
                        os.mkdir(DNA_DIST_DIR)
                    os.system("mv -f new-boot.img {}{}_twrp.img".format(DNA_DIST_DIR,
                                                                        os.path.basename(BOOTIMG).split(".")[0]))
                    os.chdir(PWD_DIR)
                    add_magisk = input("> 是否继续添加脸谱 [1/0]: ")
                    if add_magisk != "0":
                        patch_magisk("{}{}_twrp.img".format(DNA_DIST_DIR, os.path.basename(BOOTIMG).split(".")[0]))
        os.chdir(PWD_DIR)
        if os.path.isdir("{}bootimg".format(DNA_MAIN_DIR)):
            os.system("rm -rf {}bootimg".format(DNA_MAIN_DIR))
    else:
        PAUSE("> 未发现local/etc/devices/{}/{}/ramdisk.cpio文件".format(SETUP_MANIFEST["DEVICE_CODE"],
                                                                        SETUP_MANIFEST["ANDROID_SDK"]))


def patch_magisk(BOOTIMG):
    if os.path.isfile(MAGISK_JSON):
        with codecs.open(MAGISK_JSON, "r", "utf-8") as manifest_file:
            MAGISK_MANIFEST = json.load(manifest_file)
    else:
        MAGISK_MANIFEST = {}
    default_manifest = {
        'CLASS': "alpha",
        'KEEPVERITY': "true",
        'KEEPFORCEENCRYPT': "true",
        'PATCHVBMETAFLAG': "false",
        'TARGET': "arm",
        'IS_64BIT': "true"}
    for (property, value) in default_manifest.items():
        if property not in MAGISK_MANIFEST:
            MAGISK_MANIFEST[property] = value

    for k in ('KEEPVERITY', 'KEEPFORCEENCRYPT', 'PATCHVBMETAFLAG', 'IS_64BIT'):
        if MAGISK_MANIFEST[k] not in ('true', 'false'):
            sys.exit("Invalid [{}] - must be one of <true/false>".format(k))

    if MAGISK_MANIFEST["CLASS"].lower() not in ('stable', 'alpha', 'canary'):
        sys.exit("Invalid [CLASS] - must be one of <stable/alpha/canary>")
    if MAGISK_MANIFEST["TARGET"] not in ('arm', 'arm64', 'armeabi-v7a', 'arm64-v8a',
                                         'x86', 'x86_64'):
        sys.exit("Invalid [TARGET] - must be one of <arm/x86>")
    MAGISK_FILES = glob.glob("{}local/etc/magisk/{}/Magisk-*.apk".format(PWD_DIR, MAGISK_MANIFEST["CLASS"]))
    if len(MAGISK_FILES) <= 0:
        PAUSE("> 未发现local/etc/magisk/{}/Magisk-*.apk文件".format(MAGISK_MANIFEST["CLASS"]))
        return
    if os.path.isfile(BOOTIMG):
        if os.path.isdir("{}bootimg".format(DNA_MAIN_DIR)):
            os.system("rm -rf {}bootimg".format(DNA_MAIN_DIR))
        os.makedirs(DNA_MAIN_DIR + "bootimg")
        print("- Unpacking boot image")
        os.chdir(DNA_MAIN_DIR + "bootimg")
        os.system("magiskboot unpack {}".format(BOOTIMG))
        if os.path.isfile("kernel"):
            if os.path.isfile("ramdisk.cpio"):

                sha1 = hashlib.sha1()
                with open(BOOTIMG, "rb") as f:
                    while True:
                        fileData = f.read(2048)
                        if not fileData:
                            break
                        else:
                            sha1.update(fileData)

                fileHash = base64.b64encode(sha1.digest()).decode("utf-8 ")
                SHA1 = base64.b64decode(fileHash).hex()
                os.system("cat {} > stock_boot.img".format(BOOTIMG))
                os.system("cp -af ramdisk.cpio ramdisk.cpio.orig")
                print("- Patching ramdisk magisk@{}".format(MAGISK_MANIFEST["CLASS"]))
                CONFIGS = "KEEPVERITY={}\nKEEPFORCEENCRYPT={}\nPATCHVBMETAFLAG={}\n".format(
                    MAGISK_MANIFEST["KEEPVERITY"], MAGISK_MANIFEST["KEEPFORCEENCRYPT"],
                    MAGISK_MANIFEST["PATCHVBMETAFLAG"])
                if os.path.isfile("recovery_dtbo"):
                    CONFIGS += "RECOVERYMODE=true\n"
                else:
                    CONFIGS += "RECOVERYMODE=false\n"
                if SHA1:
                    CONFIGS += "SHA1={}".format(SHA1)
                with open("config", "w", newline="\n") as cn:
                    cn.write(CONFIGS)
                if MAGISK_MANIFEST["IS_64BIT"] == "true":
                    is_64bit = True
                target = MAGISK_MANIFEST["TARGET"]
                dict = {'magiskinit': "lib/armeabi-v7a/libmagiskinit.so",
                        'magisk32': "lib/armeabi-v7a/libmagisk32.so",
                        'magisk64': ""}
                if re.match("arm", target):
                    if is_64bit:
                        dict["magiskinit"] = "lib/arm64-v8a/libmagiskinit.so"
                        dict["magisk64"] = "lib/arm64-v8a/libmagisk64.so"
                elif re.match("x86", target):
                    dict["magiskinit"] = ('lib/x86/libmagiskinit.so',)
                    dict["magisk32"] = "lib/x86/libmagisk32.so"
                    if is_64bit:
                        dict["magiskinit"] = ('lib/x86_64/libmagiskinit.so',)
                        dict["magisk64"] = "lib/x86_64/libmagisk64.so"
                MAGISK_FILES = sorted(MAGISK_FILES, key=(lambda x: os.path.getmtime(x)), reverse=True)
                MAGISK_FILE = MAGISK_FILES[0]
                fantasy_zip = zipfile.ZipFile(MAGISK_FILE)
                zip_lists = fantasy_zip.namelist()
                for (k, v) in dict.items():
                    if v in zip_lists:
                        fantasy_zip.extract(v)
                        if os.path.isfile(v):
                            try:
                                os.renames(v, k)
                            except FileExistsError:
                                os.remove(k)
                                os.renames(v, k)

                        fantasy_zip.close()
                        os.system("magiskboot compress=xz magisk32 magisk32.xz")
                        os.system("magiskboot compress=xz magisk64 magisk64.xz")
                        patch_cmds = 'magiskboot cpio ramdisk.cpio "add 0750 init magiskinit" "mkdir 0750 overlay.d" "mkdir 0750 overlay.d/sbin" "add 0644 overlay.d/sbin/magisk32.xz magisk32.xz" '

                if is_64bit:
                    patch_cmds += '"add 0644 overlay.d/sbin/magisk64.xz magisk64.xz" '
                patch_cmds += '"patch" "backup ramdisk.cpio.orig" "mkdir 000 .backup" "add 000 .backup/.magisk config"'
                os.system(patch_cmds)
                os.system("rm -f ramdisk.cpio.orig config magisk*.xz magiskinit magisk*")
                for dt in ('dtb', 'kernel_dtb', 'extra'):
                    if os.path.isfile(dt):
                        print("- Patch fstab in {}".format(dt))
                        os.system("magiskboot dtb {} patch".format(dt))
                    os.system(
                        "magiskboot hexpatch kernel 736B69705F696E697472616D667300 77616E745F696E697472616D667300")
                    os.system("magiskboot hexpatch kernel 77616E745F696E697472616D6673 736B69705F696E697472616D6673")
                    os.system("magiskboot hexpatch kernel 747269705F696E697472616D6673 736B69705F696E697472616D6673")
                    print("- Repacking boot image")
                    os.system("magiskboot repack {}".format(BOOTIMG))

                if os.path.isfile("new-boot.img"):
                    print("+ Done")
                    if not os.path.isdir(DNA_DIST_DIR):
                        os.mkdir(DNA_DIST_DIR)
                    os.system("mv -f new-boot.img {}{}_magisk.img".format(DNA_DIST_DIR,
                                                                          os.path.basename(BOOTIMG).split(".")[0]))
                    if os.path.isdir(DNA_MAIN_DIR + "system" + os.sep + "system"):
                        try:
                            os.makedirs(
                                DNA_MAIN_DIR + "system" + os.sep + "system" + os.sep + "data-app" + os.sep + "Magisk")
                        except:
                            pass
                        else:
                            os.system("cp -rf '{}' {}system/system/data-app/Magisk/Magisk.apk".format(MAGISK_FILE,
                                                                                                      DNA_MAIN_DIR))
                    elif os.path.isdir(DNA_MAIN_DIR + "vendor"):
                        os.makedirs(DNA_MAIN_DIR + "vendor" + os.sep + "data-app" + os.sep + "Magisk")
                        os.system("cp -rf {} {}vendor/data-app/Magisk/Magisk.apk".format(MAGISK_FILE, DNA_MAIN_DIR))
            os.chdir(PWD_DIR)
            if os.path.isdir("{}bootimg".format(DNA_MAIN_DIR)):
                os.system("rm -rf {}bootimg".format(DNA_MAIN_DIR))


def patch_addons(project):
    if os.path.isdir("{}local/etc/devices/default/{}/addons".format(PWD_DIR, SETUP_MANIFEST["ANDROID_SDK"])):
        DISPLAY("复制 default/{}/* ...".format(SETUP_MANIFEST["ANDROID_SDK"]))
        os.system("cp -rf {}local/etc/devices/default/{}/addons/* {}".format(PWD_DIR, SETUP_MANIFEST[
            "ANDROID_SDK"], DNA_MAIN_DIR))
    if os.path.isdir("{}local/etc/devices/{}/{}/addons".format(PWD_DIR, SETUP_MANIFEST["DEVICE_CODE"],
                                                               SETUP_MANIFEST["ANDROID_SDK"])):
        DISPLAY("复制 {}/{}/* ...".format(SETUP_MANIFEST["DEVICE_CODE"], SETUP_MANIFEST["ANDROID_SDK"]))
        os.system("cp -rf {}local/etc/devices/{}/{}/addons/* {}".format(PWD_DIR,
                                                                        SETUP_MANIFEST["DEVICE_CODE"],
                                                                        SETUP_MANIFEST["ANDROID_SDK"],
                                                                        DNA_MAIN_DIR))


def repack_super():
    infile = glob.glob(DNA_CONF_DIR + '*_contexts.txt')
    if len(infile) <= 0:
        parts = [
            'system',
            'system_ext',
            'product',
            'vendor',
            'odm']
    else:
        parts = []
        for file in infile:
            parts.append(os.path.basename(file).rsplit('_', 1)[0])
    os.system('echo "{}" >> {}alivable_super_parts.txt'.format(parts, DNA_DIST_DIR))
    (group_size_a, group_size_b) = (0, 0)
    argvs = 'lpmake --metadata-size 65536 --super-name super --device super:{}:{} '.format(SETUP_MANIFEST['SUPER_SIZE'],
                                                                                           str(int(SETUP_MANIFEST[
                                                                                                       'SUPER_SECTOR']) * 512))
    if SETUP_MANIFEST['IS_VAB'] == '1':
        argvs += '--metadata-slots 3 --virtual-ab -F '
        for i in parts:
            if os.path.isfile(DNA_DIST_DIR + i + '.img'):
                img_a = DNA_DIST_DIR + i + '.img'
                file_type = seekfd.gettype(img_a)
                if file_type == 'sparse':
                    new_img_a = imgextractor.ULTRAMAN().APPLE(img_a)
                    if os.path.isfile(new_img_a):
                        os.remove(img_a)
                        img_a = new_img_a

            image_size = imgextractor.ULTRAMAN().LEMON(img_a)
            group_size_a += int(image_size)
            argvs += '--partition {0}_a:readonly:{1}:{2}_a --image {0}_a={3} --partition {0}_b:readonly:0:{2}_b '.format(
                i, image_size, SETUP_MANIFEST['GROUP_NAME'], img_a)
    else:
        argvs += '--metadata-slots 2 '
        for i in parts:
            if os.path.isfile(DNA_DIST_DIR + i + '_b.img'):
                img_b = DNA_DIST_DIR + i + '_b.img'
                img_a = DNA_DIST_DIR + i + '.img'
                if os.path.isfile(DNA_DIST_DIR + i + '_a.img'):
                    img_a = DNA_DIST_DIR + i + '_a.img'
            file_type_a = seekfd.gettype(img_a)
            file_type_b = seekfd.gettype(img_b)
            if file_type_a == 'sparse':
                new_img_a = imgextractor.ULTRAMAN().APPLE(img_a)
                if os.path.isfile(new_img_a):
                    os.remove(img_a)
                    img_a = new_img_a

            if file_type_b == 'sparse':
                new_img_b = imgextractor.ULTRAMAN().APPLE(img_b)
                if os.path.isfile(new_img_b):
                    os.remove(img_b)
                    img_b = new_img_b

            image_size_a = imgextractor.ULTRAMAN().LEMON(img_a)
            group_size_a += int(image_size_a)
            image_size_b = imgextractor.ULTRAMAN().LEMON(img_b)
            group_size_b += int(image_size_b)
            argvs += '--partition {0}_a:readonly:{1}:{2}_a --image {0}_a={3} --partition {0}_b:readonly:{4}:{2}_b --image {0}_b={5} '.format(
                i, image_size_a, SETUP_MANIFEST['GROUP_NAME'], img_a, image_size_b, img_b)
    if group_size_a == 0:
        PAUSE('> 未发现002_DNA文件夹下存在可用镜像文件')
        return None
    if SETUP_MANIFEST['SUPER_SPARSE'] == '1':
        argvs += '--sparse '
    if SETUP_MANIFEST['IS_VAB'] == '1':
        reserve_size = int(SETUP_MANIFEST['SUPER_SECTOR']) * 1024
        half_size = int(SETUP_MANIFEST['SUPER_SIZE']) - reserve_size
        if int(group_size_a) <= half_size:
            group_size_a = str(half_size)
            group_size_b = str(half_size)
        else:
            PAUSE('out of size !')
            return None
    half_size = int(SETUP_MANIFEST['SUPER_SIZE']) / 2
    if int(group_size_a) <= half_size:
        group_size_a = half_size
    else:
        PAUSE('out of size !')
        return None
    if int(group_size_b) <= half_size:
        group_size_b = half_size
    else:
        PAUSE('out of size !')
        return None
    argvs += '--group {0}_a:{1} --group {0}_b:{2} --output {3} 2> {4}lpmake_log.txt'.format(
        SETUP_MANIFEST['GROUP_NAME'],
        str(group_size_a),
        str(group_size_b),
        DNA_DIST_DIR + 'super.img',
        DNA_DIST_DIR)
    printinform2 = '重新合成: super.img <Size:{}|Vab:{}|Sparse:{}>'.format(SETUP_MANIFEST['SUPER_SIZE'],
                                                                           SETUP_MANIFEST['IS_VAB'],
                                                                           SETUP_MANIFEST['SUPER_SPARSE'])
    DISPLAY(printinform2)
    printinform2 = '重新合成: super.img <Size:{}|Vab:{}|Sparse:{}>'.format(
        SETUP_MANIFEST['SUPER_SIZE'],
        SETUP_MANIFEST['IS_VAB'],
        SETUP_MANIFEST['SUPER_SPARSE']
    )

    DISPLAY(printinform2)

    with CoastTime():
        call(argvs)

    try:
        if os.path.isfile(os.path.join(DNA_DIST_DIR, 'super.img')):
            for i in parts:
                for slot in ('_a', '_b', ''):
                    if os.path.isfile(os.path.join(DNA_DIST_DIR, i + slot + '.img')):
                        os.remove(os.path.join(DNA_DIST_DIR, i + slot + '.img'))
    except:
        pass


def walk_add_fsconfig(source, fsconfig):
    target_dir_lists = sorted(find_file(source, " ", 4))
    fs_configs_lists = sorted(find_file(fsconfig, " ", 5))
    for line in target_dir_lists:
        line2 = line.replace(DNA_MAIN_DIR, "").replace(os.sep, "/")
        if line2 not in fs_configs_lists:
            if os.path.isdir(line):
                target_addon = line2 + " 0 0 0755"
            elif os.path.isfile(line):
                if "system/xbin" in line2 or "system/bin" in line2 or "vendor/bin" in line2 or "system/bin" in line2 or "sbin" in line2:
                    target_addon = line2 + " 0 0 0755"
                else:
                    target_addon = line2 + " 0 0 0644"
            else:
                target_addon = line2 + " 0 0 0644"
            with open(fsconfig, "a") as new_fs_configs:
                new_fs_configs.write(str(target_addon + "\n"))


def walk_contexts(contexts):
    f3 = open(contexts, "r", encoding="utf-8")
    text_list = []
    s = set()
    document = f3.readlines()
    f3.close()
    content = [x.strip() for x in document]
    for x in range(0, len(content)):
        url = content[x]
        if url not in s:
            s.add(url)
            text_list.append(url)
        if os.path.isfile(contexts):
            os.remove(contexts)

    with open(contexts, "a+", encoding="utf-8") as f:
        for i in range(len(text_list)):
            s = str(text_list[i])
            s = s + "\n"
            f.write(s)


def recompress(source, fsconfig, contexts, dumpinfo, flag=8):
    label = os.path.basename(source)
    if not os.path.isdir(DNA_DIST_DIR):
        os.makedirs(DNA_DIST_DIR)
    distance = DNA_DIST_DIR + label + ".img"
    if os.path.isfile(distance):
        os.remove(distance)
    walk_add_fsconfig(source, fsconfig)
    walk_contexts(fsconfig)
    walk_contexts(contexts)
    source = source.replace("\\", '/')
    if SETUP_MANIFEST["UTC"].lower() == "live":
        t = time.time()
        timestamp = str(t).split(".")[0]
    else:
        timestamp = SETUP_MANIFEST["UTC"]
    read = "ro"
    RESIZE2RW = False
    SPARSE = False
    if SETUP_MANIFEST["REPACK_SPARSE_IMG"] == "1":
        SPARSE = True
    if dumpinfo:
        (fsize, dsize, inodes, block_size, blocks, per_group, mount_point) = LOAD_IMAGE_JSON(dumpinfo, source)
        size = dsize
    else:
        size = GETDIRSIZE(source, 1.2)
        if int(size) < 1048576:
            size = 1048576
        mount_point = "/" + label
        if os.path.isfile(source + os.sep + "system" + os.sep + "build.prop"):
            mount_point = "/"
    if SETUP_MANIFEST["REPACK_EROFS_IMG"] == "0":
        fs_variant = "ext4"
        if SETUP_MANIFEST["REPACK_TO_RW"] == "1" and SETUP_MANIFEST["IS_DYNAMIC"] == "1":
            RESIZE2RW = True
            read = "rw"
            block_size = 4096
            blocks = math.ceil(int(size) / int(block_size))
            mkimage_cmd = f"make_ext4fs -J -T {timestamp} -S {contexts} -l {size} -L {label} -a /{label} {distance} {source}"
            mke2fs_a_cmd = "mke2fs -O ^has_journal,^metadata_csum,extent,huge_file,^flex_bg,^64bit,uninit_bg,dir_nlink,extra_isize -t {} -b {} -L {} -I 256 -M {} -m 0 -q -F {} {}".format(
                fs_variant, block_size, label, mount_point, distance, blocks)
            e2fsdroid_a_cmd = "e2fsdroid -T {0} -C {1} -S {2} -f {3} -a /{4} -e {5} || rm -rf {5}".format(
                timestamp, fsconfig, contexts, source, label, distance)
        else:
            size = fsize
            if int(SETUP_MANIFEST["ANDROID_SDK"]) <= 9:
                read = "rw"
                mkimage_cmd = "make_ext4fs -J -T {0} -S {1} -l {2} -L {3} -a /{3} {4} {5}".format(
                    timestamp, contexts, size, label, distance, source)
            else:
                mkimage_cmd = "make_ext4fs -T {0} -S {1} -l {2} -L {3} -a /{3} {4} {5}".format(
                    timestamp, contexts, size, label, distance, source)
            mke2fs_a_cmd = "mke2fs -O ^has_journal,^metadata_csum,extent,huge_file,^flex_bg,^64bit,uninit_bg,dir_nlink,extra_isize -t {} -b {} -L {} -I 256 -N {} -M {} -m 0 -g {} -q -F {} {}".format(
                fs_variant, block_size, label, inodes, mount_point, per_group, distance, blocks)
            e2fsdroid_a_cmd = "e2fsdroid -T {0} -C {1} -S {2} -f {3} -a /{4} -e -s {5} || rm -rf {5}".format(
                timestamp, fsconfig, contexts, source, label, distance)
    else:
        fs_variant = "erofs"
        mkerofs_cmd = "mkfs.erofs "
        kernelversion = os.popen("uname -r").read()
        if not re.match("5.3", kernelversion):
            mkerofs_cmd += "-E legacy-compress "
        if SETUP_MANIFEST["RESIZE_EROFSIMG"] == "1":
            mkerofs_cmd += "-zlz4hc "
        elif SETUP_MANIFEST["RESIZE_EROFSIMG"] == "2":
            mkerofs_cmd += "-zlz4 "
        mkerofs_cmd += "-T{0} --mount-point=/{1} --fs-config-file={2} --file-contexts={3} {4} {5}  || rm -rf {4}".format(
            timestamp, label, fsconfig, contexts, distance, source)
    printinform = "Size:{}|FsT:{}|FsR:{}|Sparse:{}".format(size, fs_variant, read, SETUP_MANIFEST["REPACK_SPARSE_IMG"])
    if SETUP_MANIFEST["REPACK_EROFS_IMG"] == "0":
        if SETUP_MANIFEST["RESIZE_IMG"] == "1" and SETUP_MANIFEST["REPACK_TO_RW"] == "1":
            printinform += "|Resize:1"
        else:
            printinform += "|Resize:0"
    elif SETUP_MANIFEST["RESIZE_EROFSIMG"] == "1":
        printinform += "|lz4hc"
    elif SETUP_MANIFEST["RESIZE_EROFSIMG"] == "2":
        printinform += "|lz4"
    DISPLAY(printinform)
    DISPLAY("重新合成: {}.img ...".format(label), 4)

    if SETUP_MANIFEST["REPACK_EROFS_IMG"] == "1":
        call(mkerofs_cmd)
    elif int(SETUP_MANIFEST["ANDROID_SDK"]) <= 9:
        call(mkimage_cmd)
    else:
        call(mke2fs_a_cmd)
        if os.path.isfile(distance):
            call(e2fsdroid_a_cmd)
    if flag > 8:
        SPARSE = True
    if os.path.isfile(distance):
        print(" Done")
        if RESIZE2RW and os.name == 'posix':
            os.system("e2fsck -E unshare_blocks {}".format(distance))
            new_size = os.path.getsize(distance)
            if dumpinfo:
                if int(new_size) > int(fsize):
                    os.system("resize2fs -M {}".format(distance))
                if SETUP_MANIFEST["RESIZE_IMG"] == "1":
                    if SETUP_MANIFEST["REPACK_EROFS_IMG"] == "0":
                        if SETUP_MANIFEST["REPACK_TO_RW"] == "1":
                            os.system("resize2fs -M {}".format(distance))
        op_list = DNA_TEMP_DIR + "dynamic_partitions_op_list"
        new_op_list = DNA_DIST_DIR + "dynamic_partitions_op_list"
        if os.path.isfile(op_list) or os.path.isfile(new_op_list):
            if not os.path.isfile(new_op_list):
                shutil.copyfile(op_list, new_op_list)
        else:
            CONTENT = "remove_all_groups\n"
            for slot in ('_a', '_b'):
                CONTENT += "add_group qti_dynamic_partitions{} {}\n".format(slot,
                                                                            SETUP_MANIFEST["GROUP_SIZE" + slot.upper()])

            for partition in ('system', 'system_ext', 'product', 'vendor', 'odm'):
                for slot in ('_a', '_b'):
                    CONTENT += "add {0}{1} qti_dynamic_partitions{1}\n".format(partition, slot)

            if SETUP_MANIFEST["IS_VAB"] == "1":
                for partition in ('system_a', 'system_ext_a', 'product_a', 'vendor_a',
                                  'odm_a'):
                    CONTENT += "resize {} 4294967296\n".format(partition)

            else:
                for partition in ('system', 'system_ext', 'product', 'vendor', 'odm'):
                    for slot in ('_a', '_b'):
                        CONTENT += "resize {0}{1} 4294967296\n".format(partition, slot)

            with open(new_op_list, "w", encoding="UTF-8", newline="\n") as ST:
                ST.write(CONTENT)
        renew_size = os.path.getsize(distance)
        with open(new_op_list, "r", encoding="UTF-8") as f_r:
            lines = f_r.readlines()
        with open(new_op_list, "w", encoding="UTF-8") as f_w:
            for line in lines:
                if "resize " + label + " " in line:
                    line = "resize " + label + " " + str(renew_size) + "\n"
                elif "resize " + label + "_a " in line:
                    line = "resize " + label + "_a " + str(renew_size) + "\n"
                f_w.write(line)

        if SPARSE:
            DISPLAY("开始转换: sparse format ...")
            if os.name == "posix":
                os.system("img2simg {0} {1} && rm -rf {0}".format(distance, distance.rsplit(".", 1)[0] + "_sparse.img"))
            else:
                os.system("img2simg {0} {1} && del /s /q {0}".format(distance,
                                                                     distance.rsplit(".", 1)[0] + "_sparse.img"))
            if os.path.isfile(distance.rsplit(".", 1)[0] + "_sparse.img"):
                if os.name == "posix":
                    os.system("mv -f {0} {1}".format(distance.rsplit(".", 1)[0] + "_sparse.img", distance))
                else:
                    os.system("move /y {0} {1}".format(distance.rsplit(".", 1)[0] + "_sparse.img", distance))
                if flag > 8:
                    import img2sdat
                    DISPLAY("重新生成: {}.new.dat ...".format(label), 3)
                    img2sdat.main(distance, DNA_DIST_DIR, 4, label)
                    newdat = DNA_DIST_DIR + label + ".new.dat"
                    if os.path.isfile(newdat):
                        print(" Done")
                        os.remove(distance)
                        if flag == 10:
                            level = SETUP_MANIFEST["REPACK_BR_LEVEL"]
                            DISPLAY("重新生成: {}.new.dat.br {} ...".format(label, level), 3)
                            newdat_brotli = newdat + ".br"
                            call("brotli -{}jfo {} {}".format(level, newdat_brotli, newdat))
                            if os.path.isfile(newdat_brotli):
                                print(" Done")
                            else:
                                print(" Failed")
                    else:
                        print(" Failed")
    else:
        print(" Failed")


def rmdire(path):
    if os.path.exists(path):
        if os.name == 'nt':
            for r, d, f in os.walk(path):
                for i in d:
                    if i.endswith('.'):
                        call('mv {} {}'.format(os.path.join(r, i), os.path.join(r, i[:1])))
                for i in f:
                    if i.endswith('.'):
                        call('mv {} {}'.format(os.path.join(r, i), os.path.join(r, i[:1])))

        try:
            shutil.rmtree(path)
        except PermissionError:
            print("无法删除文件夹，权限不足")
        else:
            print("删除成功！")


def unpackboot(file, distance):
    or_dir = os.getcwd()
    rmdire(distance)
    os.makedirs(distance)
    os.chdir(distance)
    shutil.copy(file, os.path.join(distance, "boot_o.img"))
    if call("magiskboot unpack -h %s" % file) != 0:
        print("Unpack %s Fail..." % file)
        os.chdir(or_dir)
        shutil.rmtree(distance)
        return
    if os.path.isfile(distance + os.sep + "ramdisk.cpio"):
        comp = seekfd.gettype(distance + os.sep + "ramdisk.cpio")
        print("Ramdisk is %s" % comp)
        with open(distance + os.sep + "comp", "w") as f:
            f.write(comp)
        if comp != "unknow":
            os.rename(distance + os.sep + "ramdisk.cpio",
                      distance + os.sep + "ramdisk.cpio.comp")
            if call("magiskboot decompress %s %s" % (
                    distance + os.sep + "ramdisk.cpio.comp",
                    distance + os.sep + "ramdisk.cpio")) != 0:
                print("Decompress Ramdisk Fail...")
                return
        if not os.path.exists(distance + os.sep + "ramdisk"):
            os.mkdir(distance + os.sep + "ramdisk")
        os.chdir(distance)
        print("Unpacking Ramdisk...")
        call("cpio -i -d -F %s -D %s" % ("ramdisk.cpio", "ramdisk"))
        os.chdir(or_dir)
    else:
        print("Unpack Done!")
    os.chdir(or_dir)


def dboot(infile, dist):
    or_dir = os.getcwd()
    flag = ''
    if not os.path.exists(infile):
        print(f"Cannot Find {infile}...")
        return
    if os.path.isdir(infile + os.sep + "ramdisk"):
        try:
            os.chdir(infile + os.sep + "ramdisk")
        except Exception as e:
            print("Ramdisk Not Found.. %s" % e)
            return
        cpio = seekfd.findfile("cpio.exe" if os.name != 'posix' else 'cpio',
                               BIN_PATH).replace(
            '\\', "/")
        call(exe="busybox ash -c \"find | sed 1d | %s -H newc -R 0:0 -o -F ../ramdisk-new.cpio\"" % cpio, sp=1,
             shstate=True)
        os.chdir(infile)
        with open("comp", "r", encoding='utf-8') as compf:
            comp = compf.read()
        print("Compressing:%s" % comp)
        if comp != "unknow":
            if call("magiskboot compress=%s ramdisk-new.cpio" % comp) != 0:
                print("Pack Ramdisk Fail...")
                os.remove("ramdisk-new.cpio")
                return
            else:
                print("Pack Ramdisk Successful..")
                try:
                    os.remove("ramdisk.cpio")
                except (Exception, BaseException):
                    ...
                os.rename("ramdisk-new.cpio.%s" % comp.split('_')[0], "ramdisk.cpio")
        else:
            print("Pack Ramdisk Successful..")
            os.remove("ramdisk.cpio")
            os.rename("ramdisk-new.cpio", "ramdisk.cpio")
        if comp == "cpio":
            flag = "-n"
        ramdisk = True
    else:
        ramdisk = False
    if call("magiskboot repack %s %s" % (flag, os.path.join(infile, "boot_o.img"))) != 0:
        print("Pack boot Fail...")
        return
    else:
        if ramdisk:
            os.remove(os.path.join(infile, "boot_o.img"))
            if os.path.exists(os.path.join(dist, os.path.basename(infile) + ".img")):
                os.remove(os.path.join(dist, os.path.basename(infile) + ".img"))
            os.rename(infile + os.sep + "new-boot.img", os.path.join(dist, os.path.basename(infile) + ".img"))
        os.chdir(or_dir)
        try:
            rmdire(infile)
        except (Exception, BaseException):
            print("删除错误...")
        print("Pack Successful...")


def boot_utils(source, distance, flag=1):
    if not os.path.isdir(distance):
        os.makedirs(distance)
    if flag == 1:
        DISPLAY("正在分解: {}".format(os.path.basename(source)))
        unpackboot(source, distance)
    elif flag == 2:
        DISPLAY("重新合成: {}.img".format(os.path.basename(source)))
        dboot(source, distance)


def run_imgextractor(source, distance, PASSWORD_DICT):
    try:
        imgextractor.ULTRAMAN().MONSTER(source, distance, PASSWORD_DICT)
    except:
        shutil.rmtree(distance)
        os.unlink(source)


def decompress_img(source, distance, keep=1):
    SUPPORT_FST = [
        'ext', 'erofs', 'super']
    if os.path.basename(source) in ('dsp.img', 'exaid.img', 'cust.img'):
        return
    sTime = time.time()
    file_type = seekfd.gettype(source)
    if file_type == 'boot' or file_type == 'vendor_boot':
        if os.path.isdir(distance):
            shutil.rmtree(distance)
        os.makedirs(distance)
        boot_utils(source, distance)
        if not os.path.isdir(DNA_CONF_DIR):
            os.makedirs(DNA_CONF_DIR)
        boot_info = DNA_CONF_DIR + os.path.basename(distance) + '_kernel.txt'
        bootjson = {'name': '{}'.format(os.path.basename(source))}
        with codecs.open(boot_info, 'w', 'utf-8') as f:
            json.dump(bootjson, f, indent=4)

    elif file_type == 'sparse':
        DISPLAY('正在转换: Unsparse Format [{}] ...'.format(os.path.basename(source)))
        new_source = imgextractor.ULTRAMAN().APPLE(source)
        if os.path.isfile(new_source):
            if keep == 0:
                os.remove(source)
            decompress_img(new_source, distance)
    if file_type in SUPPORT_FST:
        if file_type != 'ext':
            DISPLAY('正在分解: {} <{}>'.format(os.path.basename(source), file_type), 3)
        if not os.path.isdir(DNA_CONF_DIR):
            os.makedirs(DNA_CONF_DIR)
        if file_type == 'ext':
            with Console().status(f"[yellow]正在提取{os.path.basename(source)}[/]"):
                run_imgextractor(source, distance, PASSWORD_DICT)
        else:
            while file_type == 'erofs':
                image_size = os.path.getsize(source)
                with open(DNA_CONF_DIR + os.path.basename(distance) + '_size.txt', 'w') as sf:
                    sf.write(str(image_size))
                if 'unsparse' in os.path.basename(source):
                    os.system('mv -f {} {}'.format(source, source.replace('.unsparse', '')))
                    source = source.replace('.unsparse', '')
                    dump_erofs_cmd = 'extract.erofs -i {} -o {} -x'.format(
                        source.replace(os.sep, '/'),
                        DNA_MAIN_DIR)
                    call(dump_erofs_cmd)

            distance = DNA_MAIN_DIR + os.path.basename(source).replace('.unsparse.img', '').replace('.img', '')
            if os.path.isdir(distance):
                if os.path.isdir(DNA_MAIN_DIR + 'config'):
                    contexts = DNA_MAIN_DIR + 'config' + os.sep + os.path.basename(source).replace('.unsparse.img',
                                                                                                   '').replace('.img',
                                                                                                               '') + '_file_contexts'
                    fsconfig = DNA_MAIN_DIR + 'config' + os.sep + os.path.basename(source).replace('.unsparse.img',
                                                                                                   '').replace('.img',
                                                                                                               '') + '_fs_config'
                    if os.path.isfile(contexts) and os.path.isfile(fsconfig):
                        new_contexts = DNA_CONF_DIR + os.path.basename(source).replace('.unsparse.img', '').replace(
                            '.img', '') + '_contexts.txt'
                        new_fsconfig = DNA_CONF_DIR + os.path.basename(source).replace('.unsparse.img', '').replace(
                            '.img', '') + '_fsconfig.txt'
                        shutil.copy(contexts, new_contexts)
                        shutil.copy(fsconfig, new_fsconfig)
                        shutil.rmtree(DNA_MAIN_DIR + 'config')
                    else:
                        if os.path.isdir(DNA_MAIN_DIR + 'config'):
                            shutil.rmtree(DNA_MAIN_DIR + 'config')
                        else:
                            while file_type == 'super':
                                lpunpack_cmd = 'lpunpack {} {}'.format(source, DNA_TEMP_DIR)
                                call(lpunpack_cmd)
                                for img in glob.glob(DNA_TEMP_DIR + '*_b.img'):
                                    if not SETUP_MANIFEST['IS_VAB'] == '1' or os.path.getsize(img) == 0:
                                        os.remove(img)
                                    else:
                                        new_distance = DNA_MAIN_DIR + os.path.basename(img).rsplit('.', 1)[0]
                                        decompress_img(img, new_distance, keep=0)
                                else:
                                    for img in glob.glob(DNA_TEMP_DIR + '*_a.img'):
                                        new_source = img.rsplit('_', 1)[0] + '.img'
                                        os.system('mv -f {} {}'.format(img, new_source))
                                        new_distance = DNA_MAIN_DIR + os.path.basename(new_source).rsplit('.', 1)[0]
                                        decompress_img(new_source, new_distance, keep=0)

                print('> Pass, not support fs_type [{}]'.format(file_type))
        if os.path.isdir(distance):
            if file_type != "ext":
                tTime = time.time() - sTime
                print('\x1b[1;32m %ds Done\x1b[0m' % tTime)
            else:
                print('\x1b[1;32m Done\x1b[0m')
            if keep == 0:
                if os.path.isfile(source):
                    os.remove(source)
                if os.path.isfile(source.rsplit('.', 1)[0] + '.unsparse.img'):
                    os.remove(source.rsplit('.', 1)[0] + '.unsparse.img')
        else:
            if file_type != 'super':
                print('\x1b[1;31m [Failed]\x1b[0m')


def decompress_dat(transfer, source, distance, keep=0):
    sTime = time.time()
    if os.path.isfile(source + ".1"):
        max = SETUP_MANIFEST["UNPACK_SPLIT_DAT"]
        DISPLAY("合并: {}.1~{} ...".format(os.path.basename(source), max))
        for i in range(1, int(max)):
            if os.path.exists("{}.{}".format(source, i)):
                os.system("cat {}.{} >> {}".format(source, i, source))
                os.remove("{}.{}".format(source, i))

    DISPLAY("正在分解: " + os.path.basename(source) + " ...", 3)
    sdat2img.main(transfer, source, distance)
    if os.path.isfile(distance):
        tTime = time.time() - sTime
        print("\x1b[1;32m [%ds]\x1b[0m" % tTime)
        if keep == 0:
            os.remove(source)
            os.remove(transfer)
            if os.path.isfile(source.rsplit(".", 2)[0] + ".patch.dat"):
                os.remove(source.rsplit(".", 2)[0] + ".patch.dat")
        elif keep == 2:
            os.remove(source)
            keep = 0
        else:
            keep = 0
        decompress_img(distance, DNA_MAIN_DIR + os.path.basename(distance).split(".")[0], keep)
    else:
        print("\x1b[1;31m [Failed]\x1b[0m")


def decompress_bro(transfer, source, distance, keep=0):
    sTime = time.time()
    DISPLAY("正在分解: " + os.path.basename(source) + " ...", 3)
    os.system("brotli -df {} -o {}".format(source, distance))
    if os.path.isfile(distance):
        tTime = time.time() - sTime
        print("\x1b[1;32m [%ds]\x1b[0m" % tTime)
        if keep == 0:
            os.remove(source)
        elif keep == 1:
            keep = 2
        if transfer:
            decompress_dat(transfer, distance, distance.rsplit(".", 2)[0] + ".img", keep)
    else:
        print("\x1b[1;31m [Failed]\x1b[0m")


def decompress_bin(infile, outdir, orzdir, flag='1', keep=1):
    os.system("cls" if os.name == "nt" else "clear")
    if flag == "1":
        payload_partitions = extract_payload.info(infile)
        print("> {0}包含的所有镜像文件: {1}{2}\n".format(YELLOW, len(payload_partitions), CLOSE))
        print(payload_partitions)
        print("\n")
        partitions = input(
            "> {0}根据以上信息输入一个或多个镜像，以空格分开{1}\n> {2}".format(RED, CLOSE, MAGENTA)).split()
        print("\n")
        for part in partitions:
            if not part.endswith(".img"):
                part = part + ".img"
            if part in payload_partitions:
                extract_payload.main(infile, outdir, part)

    else:
        print("> {0}提取【{1}】所有镜像文件:{2}\n".format(YELLOW, os.path.basename(infile), CLOSE))
        extract_payload.main(infile, outdir)
        os.system("cls" if os.name == "nt" else "clear")
        infile = glob.glob(outdir + "*.img")
        if len(infile) > 0:
            decompress(infile)


def decompress_win(infile_list):
    for fs in SUPPORT_FSS:
        if infile_list[fs]:
            for i in infile_list[fs]:
                if infile_list[fs][i]:
                    if fs != "ufs":
                        if fs != "emmc":
                            fsconfig_0 = []
                            contexts_0 = []
                            symlinks_0 = []
                            for s in infile_list[fs][i]:
                                if re.search("\\.win.*?[\\d]$", s):
                                    (fsconfig, contexts, symlinks) = untar_main(s)
                                else:
                                    if not os.path.isdir(i):
                                        os.makedirs(i)
                                    (fsconfig, contexts, symlinks) = untar_main(s, i)
                                fsconfig_0.extend(fsconfig)
                                contexts_0.extend(contexts)
                                if symlinks != -1:
                                    symlinks_0.extend(symlinks)

                            if fsconfig_0:
                                fsconfig_0.sort()
                                if "vendor" in i or "odm" in i:
                                    fsconfig_0.insert(0, "/ 0 2000 0755")
                                    fsconfig_0.insert(1, i + " 0 2000 0755")
                                else:
                                    fsconfig_0.insert(0, "/ 0 0 0755")
                                    fsconfig_0.insert(1, i + " 0 0 0755")
                                appendf("\n".join((str(k) for k in fsconfig_0)), "%s_fsconfig.txt" % i)
                            if contexts_0:
                                contexts_0.sort()
                                SAR = False
                                for c in contexts_0:
                                    if re.search("/{}/system/build\\.prop ".format(i), c):
                                        SAR = True
                                        break

                                if SAR:
                                    contexts_0.insert(0, "/ u:object_r:rootfs:s0")
                                    contexts_0.insert(1, "/{}(/.*)? u:object_r:rootfs:s0".format(i))
                                    contexts_0.insert(2, "/{} u:object_r:rootfs:s0".format(i))
                                    contexts_0.insert(3, "/{}/system(/.*)? u:object_r:system_file:s0".format(i))
                                else:
                                    contexts_0.insert(0, "/ u:object_r:system_file:s0")
                                    contexts_0.insert(1, "/{}(/.*)? u:object_r:system_file:s0".format(i))
                                    contexts_0.insert(2, "/{} u:object_r:system_file:s0".format(i))
                                appendf("\n".join((str(j) for j in contexts_0)), "%s_contexts.txt" % i)
                            if not symlinks_0 != -1:
                                symlinks_0.sort()
                                appendf("\n".join((str(h) for h in symlinks_0)), "%s_symlinks.txt" % i)
                            for s in infile_list[fs][i]:
                                decompress_img(s, DNA_MAIN_DIR + os.path.basename(s).rsplit(".", 1)[0])


def decompress(infile, flag=4):
    for part in infile:
        if os.path.isfile(part) and flag < 4:
            transfer = os.path.basename(part).split('.')[0] + '.transfer.list'
            transfer = os.path.join(os.path.dirname(part), transfer)
            if not os.path.isfile(transfer):
                if flag == 3:
                    continue
                else:
                    transfer = None
            if ASK:
                DISPLAY('是否分解: {} [1/0]: '.format(os.path.basename(part)), 2)
                if input() == '0':
                    continue
            if flag == 2:
                distance = part.rsplit('.', 1)[0]
                decompress_bro(transfer, part, distance)
            elif flag == 3:
                distance = part.rsplit('.', 2)[0] + '.img'
                decompress_dat(transfer, part, distance)
            continue
        if flag == 4 and os.path.basename(part) in ('dsp.img', 'cust.img'):
            continue
        if seekfd.gettype(part) not in ('ext', 'sparse', 'erofs', 'super', 'boot', 'vendor_boot'):
            continue
        if ASK:
            DISPLAY('是否分解: {} [1/0]: '.format(os.path.basename(part)), 2)
            if input() == '1':
                decompress_img(part, DNA_MAIN_DIR + os.path.basename(part).rsplit('.', 1)[0])


def envelop_project(project):
    global DNA_CONF_DIR
    global DNA_DIST_DIR
    global DNA_MAIN_DIR
    global DNA_TEMP_DIR
    DNA_MAIN_DIR = PWD_DIR + project + os.sep
    DNA_TEMP_DIR = DNA_MAIN_DIR + "001_DNA" + os.sep
    DNA_CONF_DIR = DNA_MAIN_DIR + "000_DNA" + os.sep
    DNA_DIST_DIR = DNA_MAIN_DIR + "002_DNA" + os.sep
    if IS_ARM64:
        DNA_TEMP_DIR = ROM_DIR + "D.N.A" + os.sep + project + os.sep + "001_DNA" + os.sep
        DNA_DIST_DIR = ROM_DIR + "D.N.A" + os.sep + project + os.sep + "002_DNA" + os.sep
    if not os.path.isdir(DNA_TEMP_DIR):
        os.makedirs(DNA_TEMP_DIR)
    if not os.path.isdir(DNA_TEMP_DIR):
        os.makedirs(DNA_MAIN_DIR)
    if not os.path.isdir(DNA_MAIN_DIR):
        os.makedirs(DNA_MAIN_DIR)
    if not os.path.isfile(DNA_CONF_DIR + "file_contexts"):
        if os.path.isdir(DNA_CONF_DIR):
            rule = "^[a-z].*?_file_contexts$"
            contexts_files = find_file(DNA_MAIN_DIR, rule)
            if len(contexts_files) > 0:
                with open(DNA_CONF_DIR + "file_contexts", "w", encoding='utf-8', newline="\n") as f:
                    for text in contexts_files:
                        with open(text, "r", encoding='utf-8') as f_r:
                            f.write(f_r.read())

                if os.path.isfile(DNA_CONF_DIR + "file_contexts"):
                    with open(DNA_CONF_DIR + "file_contexts", "w", encoding='utf-8', newline="\n") as f:
                        f.write("/firmware(/.*)?         u:object_r:firmware_file:s0\n")
                        f.write("/bt_firmware(/.*)?      u:object_r:bt_firmware_file:s0\n")
                        f.write("/persist(/.*)?          u:object_r:mnt_vendor_file:s0\n")
                        for i in ["dsp", "odm", "op1", "op2", "charger_log", "audit_filter_table", "keydata",
                                  "keyrefuge"
                                  "omr", "publiccert.pem", "sepolicy_version", "cust", "donuts_key", "v_key"
                            , "carrier", "dqmdbg", "ADF", "APD", "asdf", "batinfo", "voucher", "xrom", "custom",
                                  "cpefs", "modem", "module_hashes", "pds", "tombstones", "avb", "op_odm", "addon.d",
                                  "factory", "oneplus(/.*)?"]:
                            f.write(f"/{i}                    u:object_r:rootfs:s0\n")
    if os.path.isfile(DNA_CONF_DIR + "file_contexts"):
        walk_contexts(DNA_CONF_DIR + "file_contexts")


def extract_zrom(rom):
    if zipfile.is_zipfile(rom):
        project = 'DNA_' + os.path.basename(rom).rsplit('.', 1)[0]
        fantasy_zip = zipfile.ZipFile(rom)
        zip_lists = fantasy_zip.namelist()
    else:
        PAUSE('> 破损的zip或不支持的zip类型')
        sys.exit()
    if 'payload.bin' in zip_lists:
        print('> 解压缩: ' + os.path.basename(rom))
        envelop_project(project)
        infile = fantasy_zip.extract('payload.bin', DNA_TEMP_DIR)
        fantasy_zip.close()
        if os.path.isfile(DNA_TEMP_DIR + 'payload.bin'):
            outdir = DNA_TEMP_DIR
            orzdir = DNA_TEMP_DIR + 'orz' + os.sep
            choose = input('> {0}选择提取方式:  [0]全盘提取  [1]指定镜像{1} >> '.format(RED, CLOSE))
            decompress_bin(infile, outdir, orzdir, choose)
            menu_main(project)
    elif 'run.sh' in zip_lists:
        if not os.path.isdir(MOD_DIR):
            os.makedirs(MOD_DIR)
        ModName = os.path.basename(rom).rsplit('.', 1)[0]
        ModName = ModName.replace(' ', '_')
        SUB_DIR = MOD_DIR + 'DNA_' + ModName
        if not os.path.isdir(SUB_DIR):
            DISPLAY('是否安装插件: ' + ModName + ' ? [1/0]: ', 2)
            if input() != '0':
                fantasy_zip.extractall(SUB_DIR)
                fantasy_zip.close()
                if os.path.isfile(SUB_DIR + os.sep + 'run.sh') and os.name != "nt":
                    os.system('chown -hR ' + USER + ':' + USER + ' ' + SUB_DIR)
                    os.system('chmod -R a+rwX ' + SUB_DIR)
                    os.system('chmod -R 777 ' + SUB_DIR)
                    print('\x1b[1;31m\n 安装完成 !!!\x1b[0m')
                else:
                    os.system('rm -rf ' + SUB_DIR)
                    print('\x1b[1;31m\n 安装失败 !!!\x1b[0m')
            else:
                DISPLAY('已安装插件: ' + ModName + '，是否删除原插件后安装 ? [0/1]: ', 2)
                if input() == '1':
                    os.system('rm -rf ' + SUB_DIR)
                    fantasy_zip.extractall(SUB_DIR)
                    fantasy_zip.close()
                    if os.path.isfile(SUB_DIR + os.sep + 'run.sh') and os.name != "nt":
                        os.system('chown -hR ' + USER + ':' + USER + ' ' + SUB_DIR)
                        os.system('chmod -R a+rwX ' + SUB_DIR)
                        os.system('chmod -R 777 ' + SUB_DIR)
                        print('\x1b[1;31m\n 安装完成 !!!\x1b[0m')
                    else:
                        rmdire(SUB_DIR)
                        print('\x1b[1;31m\n 安装失败 !!!\x1b[0m')
    else:
        able = 5
        infile = []
        print('> 解压缩: ' + os.path.basename(rom))
        envelop_project(project)
        fantasy_zip.extractall(DNA_TEMP_DIR)
        fantasy_zip.close()
        if [part_name for part_name in sorted(zip_lists) if part_name.endswith(".new.dat.br")]:
            infile = glob.glob(DNA_TEMP_DIR + '*.br')
            able = 2
        elif [part_name for part_name in zip_lists if part_name.endswith(".new.dat")]:
            infile = glob.glob(DNA_TEMP_DIR + '*.dat')
            able = 3
        elif [part_name for part_name in zip_lists if part_name.endswith(".img")]:
            infile = glob.glob(DNA_TEMP_DIR + '*.img')
            able = 4
        if not infile:
            PAUSE('> 仅支持含有payload.bin/*.new.dat/*.new.dat.br/*.img的zip固件')
        else:
            global ASK
            ASK = True
            decompress(infile, able)
        menu_main(project)


def lists_project(dTitle, sPath, flag):
    global IS_FIRST
    global dict0
    i = 0
    dict0 = {i: dTitle}
    if flag == 0:
        for obj in glob.glob(sPath):
            if os.path.isdir(obj):
                i += 1
                dict0[i] = obj

    elif flag == 1:
        for obj in glob.glob(sPath):
            if os.path.isfile(obj):
                i += 1
                dict0[i] = obj

    elif flag == 2:
        for obj in glob.glob(sPath):
            if os.path.isdir(obj):
                if os.path.isfile(obj + os.sep + "run.sh"):
                    i += 1
                    dict0[i] = obj

    e = 1
    print("-------------------------------------------------------")
    print()
    for (key, value) in dict0.items():
        print("  \x1b[0;3{}m[{}]\x1b[0m - \x1b[0;3{}m{}\x1b[0m".format(e, key, e + 4, os.path.basename(value)))
        e = 2

    print()
    print("-------------------------------------------------------")
    if flag == 0:
        print("\x1b[0;35m  [33] - 解压      [44] - 删除\n  [77] - 设置      [66] - 下载\n  [88] - 退出  \x1b[0m\n")

    if flag == 2:
        print("\x1b[0;35m  [33] - 安装         [44] - 删除         [88] - 退出  \x1b[0m\n")


def choose_zrom(flag=0):
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')
    if flag == 1:
        print('\x1b[0;33m> 选择固件:\x1b[0m')
        sFilePath = easygui.fileopenbox(msg='选择一个固件', default='*.zip')

        if sFilePath is not None:
            extract_zrom(sFilePath)
    elif flag == 2:
        print('\x1b[0;33m> 插件列表\x1b[0m')
    else:
        print('\x1b[0;33m> 固件列表\x1b[0m')
        lists_project('返回上级', ROM_DIR + '*.zip', 1)
        choice = input('> 选择: ')
        if choice:
            if int(choice) == 66:
                download_zrom(input('> {0}选择下载方式:  [0]米柚在更系列  [1]输入下载直链{1} >> '.format(RED, CLOSE)))
            elif int(choice) == 0:
                return
            elif 0 < int(choice) < len(dict0):
                extract_zrom(dict0[int(choice)])
            else:
                PAUSE(f'> Number \x1b[0;33m{choice}\x1b[0m enter error !')


def download_rom(rom, url):
    os.system("cls" if os.name == "nt" else "clear")
    res = requests.get(url, stream=True)
    file_size = int(res.headers.get("Content-Length"))
    file_size_in_mb = int(file_size / 1048576)
    print("> {0}D.N.A DOWNLOADER:{1}\n".format(GREEN, CLOSE))
    print("Link: {}".format(url))
    print("Size: {}Mb".format(str(file_size_in_mb)))
    print("Path: {}".format(rom))
    if not os.path.isfile(rom):
        pbar = tqdm(total=file_size)
        with open(rom, "wb") as f:
            for chunk in res.iter_content(2097152):
                f.write(chunk)
                pbar.set_description("Downloading")
                pbar.update(2097152)

            pbar.close()
        if zipfile.is_zipfile(rom):
            print("{0}Successed !{1}".format(RED, CLOSE))
            choose_zrom()
        else:
            if os.path.exists(rom):
                os.remove(rom)
            PAUSE("> {0}Failed !{1}".format(GREEN, CLOSE))
    else:
        PAUSE("> 发现 " + os.path.basename(rom))


def download_zrom(flag=''):
    if flag == "1":
        url = input("> 输入zip直链: ")
        if url != "":
            rom = url.split("/")[-1]
            if rom.split(".")[-1] == "zip":
                sFilePath = str(ROM_DIR + rom)
                if not os.path.isfile(sFilePath):
                    download_rom(sFilePath, url)
    print("[?]: Verificando su conexion a internet in 5s ...")
    host = "https://xiaomirom.com/series/"
    try:
        req = requests.get(host, timeout=5)
        if req.status_code == 200:
            print("{}[!]: Pass ...{}".format(GREEN, CLOSE))
    except:
        PAUSE("{0}[x]:{1} Connect github.com err !!!{1}".format(RED, CLOSE))
        return None
    else:
        device_code = SETUP_MANIFEST["DEVICE_CODE"]
        DEVICE_JSON = "{}local/set/{}.json".format(PWD_DIR, device_code)
        if os.path.isfile(DEVICE_JSON):
            with codecs.open(DEVICE_JSON, "r", encoding="utf-8") as manifest_file:
                manifest = json.load(manifest_file)
            default_manifest = {'name': "D.N.A",
                                'region': "CN",
                                'mode': "recovery",
                                'type': "develop"}
            for (property, value) in default_manifest.items():
                if property not in manifest:
                    manifest[property] = value

            if manifest["region"].upper() not in ('CN', 'TW', 'EN', 'RU', 'EU', 'ID',
                                                  'IN', 'TR', 'SG', 'JP'):
                sys.exit("Invalid [region] - must be one of <CN/TW/EN/RU/EU/ID/IN/TR/SG/JP>")
            if manifest["mode"].lower() not in ('recovery', 'fastboot'):
                sys.exit("Invalid [mode] - must be one of <recovery/fastboot>")
            if manifest["type"].lower() not in ('develop', 'stable'):
                sys.exit("Invalid [type] - must be one of <develop/stable>")

            links_dict = miui.get_model_link_table()
            timenow = datetime.datetime.now().timetuple()
            today = str(timenow.tm_year)[2:] + "." + str(timenow.tm_mon) + "." + str(timenow.tm_mday)
            if 220000 > int(time.strftime("%H%M%S")):
                today = str(timenow.tm_year)[2:] + "." + str(timenow.tm_mon) + "." + str(timenow.tm_mday - 1)
            device_name = manifest["name"]
            if device_code in links_dict.keys():
                device_region = manifest["region"]
                device_mode = manifest["mode"]
                device_type = manifest["type"]
                version = manifest["version"]
                print("\n> {0}机型配置文件{1}: {2}".format(GREEN, CLOSE, DEVICE_JSON.replace(PWD_DIR, "")))
                if not version:
                    version = input("> 输入版本号 [{}]: ".format(today))
                    if not version or re.search("\\w", version) == False:
                        version = today
                echo_info = "{0} | {1} | {2} | {3} | {4}".format(device_name, device_region, device_mode, device_type,
                                                                 version)
                print(echo_info)
                xiaomirom_url = links_dict[device_code][device_region]
                miui_links_dict = miui.get_rom_link(xiaomirom_url, version)
                miui_links_list = miui_links_dict[device_mode][device_type]
                if len(miui_links_list) > 0:
                    print("{1}".format(version, miui_links_list[0]))
                    down = input("> 是否下载 [1/0]: ")
                    if down == "0":
                        return
                    rom = miui_links_list[0].split("/")[-1]
                    if rom.split(".")[-1] == "zip":
                        sFilePath = str(ROM_DIR + rom)
                        if not os.path.isfile(sFilePath):
                            download_rom(sFilePath, miui_links_list[0])
                        else:
                            PAUSE("{0}Rom Existed !{1}".format(RED, CLOSE))
                else:
                    PAUSE("{0}{1}{2}:  None".format(RED, CLOSE, version))


def creat_project():
    global project
    os.system("cls" if os.name == "nt" else "clear")
    print("\x1b[1;31m> 新建工程:\x1b[0m\n")
    CREAT_NAME = input("  输入名称【不能有空格、特殊符号】: DNA_")
    if CREAT_NAME != "":
        path = CREAT_NAME.strip()
        path = path.rstrip("\\")
        CC_NAME = path.replace(" ", "_")
        project = "DNA_" + CC_NAME
        if not os.path.isdir(project):
            os.mkdir(project)
            menu_main(project)
        else:
            print("\x1b[0;31m\n 工程目录< \x1b[0;32m{} \x1b[0;31m>已存在, 1秒后自动返回重新输入 ...\x1b[0m\n".format(
                str(project)))
            del project
            time.sleep(0.3)
            creat_project()
    else:
        menu_once()


def menu_once():
    global IS_FIRST
    global project
    LOAD_SETUP_JSON()
    while IS_FIRST >= 3:
        IS_FIRST = 0

    IS_FIRST += 1
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("\x1b[0;33m> 工程列表\x1b[0m")
        lists_project("新建工程", "DNA_*", 0)
        choice = input("> 选择: ")
        if not choice or not choice.isdigit():
            continue
        if int(choice) == 88:
            sys.exit()
        elif int(choice) == 33:
            if os.name == "nt":
                choose_zrom(1)
            else:
                choose_zrom()
        elif int(choice) == 44:
            if len(dict0) > 1:
                which = input("> 输入序号进行删除: ")
                if which and not int(which) == 0 and not which.isdigit():
                    menu_once()
                elif int(which) > 0:
                    if int(which) < len(dict0):
                        print((
                            "\x1b[0;31m> 是否删除 \x1b[0;34mNo.{} \x1b[0;31m工程: \x1b[0;32m{}\x1b[0;31m [0/1]:\x1b[0m ".format(
                                which, os.path.basename(dict0[int(which)]))), end="")
                        if input() == "1":
                            if os.path.isdir(dict0[int(which)]):
                                rmdire(dict0[int(which)])
                                if IS_ARM64:
                                    if os.path.isdir(ROM_DIR + "D.N.A" + os.sep + dict0[int(which)]):
                                        PAUSE("> 请自主判断删除内置存储 {}".format(
                                            ROM_DIR + "D.N.A" + os.sep + dict0[int(which)]))
                                menu_once()
                    PAUSE("> Number {} Error !".format(which))
        elif int(choice) == 66:
            choose = input(
                "> {0}选择下载方式: [0]在线更新(xiaomirom.com)\n\t\t[1]输入下载直链{1} >> ".format(RED, CLOSE))
            download_zrom(choose)
        elif int(choice) == 77:
            env_setup()
            LOAD_SETUP_JSON()
        elif int(choice) == 0:
            creat_project()
            break
        else:
            if 0 < int(choice) < len(dict0):
                project = dict0[int(choice)]
                menu_main(project)
                break
            else:
                PAUSE("> Number \x1b[0;33m{}\x1b[0m enter error !".format(choice))


def menu_more(project):
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("\x1b[1;36m> 当前工程: \x1b[0m{}".format(project))
        print("-------------------------------------------------------\n")
        print("\x1b[0;31m  00> 返回上级    \x1b[0m")
        print("\x1b[0;32m  01> [Test]去除AVB    \x1b[0m")
        print("\x1b[0;34m  02> [Test]去除DM     \x1b[0m")
        print("\x1b[0;31m  05> [Test|A11+]全局合并    \x1b[0m")
        print("\x1b[0;35m  06> 标准精简    \x1b[0m")
        print("\x1b[0;32m  07> 添加文件    \x1b[0m")
        print("\x1b[0;34m  08> [Test]修补boot.img @twrp    \x1b[0m")
        print("\x1b[0;36m  09> [Test]修补boot.img @magisk    \x1b[0m")
        print("\x1b[0;33m  11> [Test]合成super.img    \x1b[0m\n")
        print("-------------------------------------------------------")
        option = input("> {0}输入序号{1} >> ".format(RED, CLOSE))
        if not option.isdigit():
            PAUSE("> 输入序号数字")
            continue
        if not int(option) == 88:
            sys.exit()
        if int(option) == 0:
            break
        elif int(option) == 1:
            with CoastTime():
                kill_avb(project)
            PAUSE()
        elif int(option) == 2:
            with CoastTime():
                kill_dm(project)
            PAUSE()
        elif int(option) == 5:
            with CoastTime():
                devdex.deodex(project)
        else:
            if not int(option) == 6:
                if os.path.isfile(
                        "{}local/etc/devices/{}/{}/reduce.txt".format(PWD_DIR, SETUP_MANIFEST["DEVICE_CODE"],
                                                                      SETUP_MANIFEST["ANDROID_SDK"])):
                    REDUCE_CONF = "{}local/etc/devices/{}/{}/reduce.txt".format(PWD_DIR,
                                                                                SETUP_MANIFEST["DEVICE_CODE"],
                                                                                SETUP_MANIFEST["ANDROID_SDK"])
                elif os.path.isfile(
                        "{}local/etc/devices/default/{}/reduce.txt".format(PWD_DIR, SETUP_MANIFEST["ANDROID_SDK"])):
                    REDUCE_CONF = "{}local/etc/devices/default/{}/reduce.txt".format(PWD_DIR,
                                                                                     SETUP_MANIFEST["ANDROID_SDK"])
                else:
                    PAUSE("精简列表<reduce.txt>丢失！")
            with CoastTime():
                for line in open(REDUCE_CONF):
                    line = line.replace("/", os.sep).strip("\n")
                    if line:
                        if not line.startswith("#"):
                            if os.path.exists(DNA_MAIN_DIR + line):
                                print(line)
                                try:
                                    shutil.rmtree(DNA_MAIN_DIR + line)
                                except NotADirectoryError:
                                    os.remove(DNA_MAIN_DIR + line)

            PAUSE()

        if int(option) == 7:
            with CoastTime():
                patch_addons(project)
            PAUSE()
        else:
            if not int(option) == 8 or int(option) == 9:
                if os.path.isfile(DNA_DIST_DIR + "boot.img"):
                    currentbootimg = DNA_DIST_DIR + "boot.img"
                elif os.path.isfile(DNA_TEMP_DIR + "boot.img"):
                    currentbootimg = DNA_TEMP_DIR + "boot.img"
                if not os.path.isfile(currentbootimg):
                    with CoastTime():
                        if int(option) == 8:
                            patch_twrp(currentbootimg)
                        else:
                            patch_magisk(currentbootimg)
                    PAUSE()
                if int(option) == 11:
                    repack_super()
                    PAUSE()
                else:
                    PAUSE("> Number \x1b[0;33m{}\x1b[0m enter error !".format(option))


def menu_modules():
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("\x1b[0;33m> 插件列表\x1b[0m")
        lists_project("返回上级", MOD_DIR + "DNA_*", 2)
        choice = input("> 选择: ")
        if choice:
            if not choice.isdigit():
                continue
            if int(choice) == 88:
                sys.exit()
            elif int(choice) == 33:
                choose_zrom(2)
            elif int(choice) == 44:
                if not len(dict0) > 1:
                    which = input("> 输入序号进行删除: ")
                    if which:
                        if not int(which) == 0:
                            if not which.isdigit():
                                continue
                            if int(which) > 0:
                                if int(which) < len(dict0):
                                    print((
                                        "\x1b[0;31m> 是否删除 \x1b[0;34mNo.{} \x1b[0;31m插件: \x1b[0;32m{}\x1b[0;31m [0/1]:\x1b[0m ".format(
                                            which, os.path.basename(dict0[int(which)]))), end="")
                                    if input() == "1":
                                        if os.path.isdir(dict0[int(which)]):
                                            rmdire(dict0[int(which)])
                                            continue
                                        PAUSE("> Number {} Error !".format(which))
            elif int(choice) == 0:
                return
            if 0 < int(choice) < len(dict0):
                RunModules(dict0[int(choice)])
            else:
                print("> Number \x1b[0;33m{}\x1b[0m enter error !".format(choice))


def RunModules(sub):
    os.system("cls" if os.name == "nt" else "clear")
    print("\x1b[1;31m> 执行插件:\x1b[0m " + os.path.basename(sub) + "\n")
    Shell_Sub = sub + os.sep + "run.sh"
    if os.path.isfile(Shell_Sub):
        call(f"busybox bash {Shell_Sub} {DNA_MAIN_DIR}")
    time.sleep(0.5)


def menu_main(project):
    global ASK, ASK, ASK, ASK, ASK, ASK
    envelop_project(project)
    ASK = True
    pause = False
    os.system('cls' if os.name == 'nt' else 'clear')
    print('\x1b[1;36m> 当前工程: \x1b[0m{}'.format(project))
    print('-------------------------------------------------------\n')
    print('\x1b[0;31m\t  00> 选择[etc]          01> 分解[bin]\x1b[0m')
    print('\x1b[0;32m\t  02> 分解[bro]          03> 分解[dat]\x1b[0m')
    print('\x1b[0;36m\t  04> 分解[img]          05> 分解[win]\x1b[0m')
    print('\x1b[0;33m\t  06> 更多[dev]          07> 插件[sub]\x1b[0m')
    print('\x1b[0;35m\t  08> 合成[img]          09> 合成[dat]\x1b[0m')
    print('\x1b[0;34m\t  10> 合成[bro]          88> 退出[bye]\x1b[0m\n')
    print('-------------------------------------------------------')
    option = input('> {0}输入序号{1} >> '.format(RED, CLOSE))

    if option:
        if not option.isdigit():
            input('> 输入序号数字')
        else:
            if int(option) == 88:
                sys.exit()
            elif int(option) == 0:
                menu_once()
            elif int(option) == 1:
                infile = DNA_TEMP_DIR + 'payload.bin'
                outdir = DNA_TEMP_DIR
                orzdir = DNA_TEMP_DIR + 'orz' + os.sep
                choose = input('> {0}选择提取方式:  [0]全盘提取  [1]指定镜像{1} >> '.format(RED, CLOSE))
                decompress_bin(infile, outdir, orzdir, choose)
            elif int(option) == 2:
                infile = glob.glob(DNA_TEMP_DIR + '*.br')

                BECOME_SILENT = input('> 是否开启静默 [0/1]: ')
                if BECOME_SILENT == '1':
                    ASK = False
                decompress(infile, int(option))
            elif int(option) == 3:
                infile = glob.glob(DNA_TEMP_DIR + '*.dat')

                BECOME_SILENT = input('> 是否开启静默 [0/1]: ')
                if BECOME_SILENT == '1':
                    ASK = False
                decompress(infile, int(option))
                infile = glob.glob(DNA_TEMP_DIR + '*.img')
                BECOME_SILENT = input('> 是否开启静默 [0/1]: ')
                if BECOME_SILENT == '1':
                    ASK = False
                decompress(infile, int(option))
            elif int(option) == 4:
                infile = glob.glob(DNA_TEMP_DIR + '*.img')
                BECOME_SILENT = input('> 是否开启静默 [0/1]: ')
                if BECOME_SILENT == '1':
                    ASK = False
                decompress(infile, int(option))
            elif int(option) == 5:
                infile = glob.glob(DNA_TEMP_DIR + '*.win*')
                BECOME_SILENT = input('> 是否开启静默 [0/1]: ')
                if BECOME_SILENT == '1':
                    ASK = False
                all_name = {'system': [], "system": [], 'system': [], "system": [],
                            }
                all_name = dict(zip(('ext4', 'erofs', 'ufs', 'emmc'), all_name.values()))
                for a in sorted(infile):
                    a_basename = a.split('.')[0]
                    for fs in SUPPORT_FSS:
                        if fs in a:
                            if a_basename not in all_name[fs]:
                                all_name[fs].append(a)
                            else:
                                all_name[fs][a_basename].append(a)
                decompress_win(all_name)
            elif int(option) == 6:
                menu_more(project)
            elif int(option) == 7:
                menu_modules()
            elif int(option) == 8:
                infile = glob.glob(DNA_CONF_DIR + '*_contexts.txt')
                infile_kernel = glob.glob(DNA_CONF_DIR + '*_kernel.txt')
                BECOME_SILENT = input('> 是否开启静默 [0/1]: ')
                if BECOME_SILENT == '1':
                    ASK = False
                for file in infile_kernel:
                    f_basename = os.path.basename(file).rsplit('_', 1)[0]
                    source = DNA_MAIN_DIR + f_basename
                    if os.path.isdir(source):
                        if ASK:
                            DISPLAY(f'是否合成: {f_basename}.img [1/0]: ')
                            if input() == '0':
                                continue
                        boot_utils(source, DNA_DIST_DIR, 2)
                        continue
                for file in infile:
                    f_basename = os.path.basename(file).rsplit('_', 1)[0]
                    source = DNA_MAIN_DIR + f_basename
                    if os.path.isdir(source):
                        fsconfig = DNA_CONF_DIR + f_basename + '_fsconfig.txt'
                        contexts = DNA_CONF_DIR + f_basename + '_contexts.txt'
                        infojson = DNA_CONF_DIR + f_basename + '_info.txt'
                        if not os.path.isfile(infojson):
                            infojson = None
                        if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '0' and SETUP_MANIFEST['REPACK_TO_RW'] == '1':
                            if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '1':
                                SETUP_MANIFEST['REPACK_EROFS_IMG'] = '0'
                                SETUP_MANIFEST['REPACK_TO_RW'] = '1'
                        elif SETUP_MANIFEST['REPACK_EROFS_IMG'] == '0' and SETUP_MANIFEST['REPACK_TO_RW'] == '0':
                            if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '1':
                                SETUP_MANIFEST['REPACK_EROFS_IMG'] = '1'
                                SETUP_MANIFEST['REPACK_TO_RW'] = '0'
                        if os.path.isfile(contexts) and os.path.isfile(fsconfig):
                            if ASK:
                                DISPLAY(f'是否合成: {f_basename}.img [1/0]: ')
                                if input() == '0':
                                    continue
                            recompress(source, fsconfig, contexts, infojson, int(option))
            elif int(option) == 9:
                infile = glob.glob(DNA_CONF_DIR + '*_contexts.txt')
                BECOME_SILENT = input('> 是否开启静默 [0/1]: ')
                if BECOME_SILENT == '1':
                    ASK = False
                for file in infile:
                    f_basename = os.path.basename(file).rsplit('_', 1)[0]
                    source = DNA_MAIN_DIR + f_basename
                    if os.path.isdir(source):
                        fsconfig = DNA_CONF_DIR + f_basename + '_fsconfig.txt'
                        contexts = DNA_CONF_DIR + f_basename + '_contexts.txt'
                        infojson = DNA_CONF_DIR + f_basename + '_info.txt'
                        if not os.path.isfile(infojson):
                            infojson = None
                        if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '0' and SETUP_MANIFEST['REPACK_TO_RW'] == '1':
                            if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '1':
                                SETUP_MANIFEST['REPACK_EROFS_IMG'] = '0'
                                SETUP_MANIFEST['REPACK_TO_RW'] = '1'
                        elif SETUP_MANIFEST['REPACK_EROFS_IMG'] == '0' and SETUP_MANIFEST['REPACK_TO_RW'] == '0':
                            if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '1':
                                SETUP_MANIFEST['REPACK_EROFS_IMG'] = '1'
                                SETUP_MANIFEST['REPACK_TO_RW'] = '0'
                        if os.path.isfile(contexts) and os.path.isfile(fsconfig):
                            if ASK:
                                DISPLAY('是否合成: {f_basename}.img [1/0]: '.format(f_basename=f_basename))
                                if input() == '0':
                                    continue
                            recompress(source, fsconfig, contexts, infojson, int(option))
                source = DNA_MAIN_DIR + f_basename
                if os.path.isdir(source):
                    fsconfig = DNA_CONF_DIR + f_basename + '_fsconfig.txt'
                    contexts = DNA_CONF_DIR + f_basename + '_contexts.txt'
                    infojson = DNA_CONF_DIR + f_basename + '_info.txt'
                    if not os.path.isfile(infojson):
                        infojson = None
                    if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '0' and SETUP_MANIFEST['REPACK_TO_RW'] == '1':
                        if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '1':
                            SETUP_MANIFEST['REPACK_EROFS_IMG'] = '0'
                            SETUP_MANIFEST['REPACK_TO_RW'] = '1'
                    elif SETUP_MANIFEST['REPACK_EROFS_IMG'] == '0' and SETUP_MANIFEST['REPACK_TO_RW'] == '0':
                        if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '1':
                            SETUP_MANIFEST['REPACK_EROFS_IMG'] = '1'
                            SETUP_MANIFEST['REPACK_TO_RW'] = '0'
                    if os.path.isfile(contexts) and os.path.isfile(fsconfig):
                        if ASK:
                            DISPLAY('是否合成: {}.new.dat [1/0]: '.format(f_basename))
                            if input() == '1':
                                recompress(source, fsconfig, contexts, infojson, int(option))
            elif int(option) == 10:
                infile = glob.glob(DNA_CONF_DIR + '*_contexts.txt')
                if len(infile) > 0:
                    pause = True
                BECOME_SILENT = input('> 是否开启静默 [0/1]: ')
                if BECOME_SILENT == '1':
                    ASK = False
                for file in infile:
                    f_basename = os.path.basename(file).rsplit('_', 1)[0]
                    source = DNA_MAIN_DIR + f_basename
                    if os.path.isdir(source):
                        fsconfig = DNA_CONF_DIR + f_basename + '_fsconfig.txt'
                        contexts = DNA_CONF_DIR + f_basename + '_contexts.txt'
                        infojson = DNA_CONF_DIR + f_basename + '_info.txt'
                        if not os.path.isfile(infojson):
                            infojson = None
                        if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '0' and SETUP_MANIFEST['REPACK_TO_RW'] == '1':
                            if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '1':
                                SETUP_MANIFEST['REPACK_EROFS_IMG'] = '0'
                                SETUP_MANIFEST['REPACK_TO_RW'] = '1'
                        elif SETUP_MANIFEST['REPACK_EROFS_IMG'] == '0' and SETUP_MANIFEST['REPACK_TO_RW'] == '0':
                            if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '1':
                                SETUP_MANIFEST['REPACK_EROFS_IMG'] = '1'
                                SETUP_MANIFEST['REPACK_TO_RW'] = '0'
                        if os.path.isfile(contexts) and os.path.isfile(fsconfig):
                            if ASK:
                                DISPLAY('是否合成: {}.new.dat [1/0]: '.format(f_basename))
                                if input() == '0':
                                    continue
                            recompress(source, fsconfig, contexts, infojson, int(option))
                    for file in infile:
                        f_basename = os.path.basename(file).rsplit('_', 1)[0]
                        source = DNA_MAIN_DIR + f_basename
                        if os.path.isdir(source):
                            fsconfig = DNA_CONF_DIR + f_basename + '_fsconfig.txt'
                            contexts = DNA_CONF_DIR + f_basename + '_contexts.txt'
                            infojson = DNA_CONF_DIR + f_basename + '_info.txt'
                            if not os.path.isfile(infojson):
                                infojson = None
                            if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '0' and SETUP_MANIFEST['REPACK_TO_RW'] == '1':
                                if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '1':
                                    SETUP_MANIFEST['REPACK_EROFS_IMG'] = '0'
                                    SETUP_MANIFEST['REPACK_TO_RW'] = '1'
                            elif SETUP_MANIFEST['REPACK_EROFS_IMG'] == '0' and SETUP_MANIFEST['REPACK_TO_RW'] == '0':
                                if SETUP_MANIFEST['REPACK_EROFS_IMG'] == '1':
                                    SETUP_MANIFEST['REPACK_EROFS_IMG'] = '1'
                                    SETUP_MANIFEST['REPACK_TO_RW'] = '0'
                            if os.path.isfile(contexts) and os.path.isfile(fsconfig):
                                if ASK:
                                    DISPLAY(f'是否合成: {f_basename}.new.dat.br [1/0]: ')
                                    if input() == '0':
                                        continue
                                recompress(source, fsconfig, contexts, infojson, int(option))
                    else:
                        PAUSE('\x1b[0;33m{option}\x1b[0m enter error !')
                    if pause:
                        PAUSE()
    menu_main(project)
