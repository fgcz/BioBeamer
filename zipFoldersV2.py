import errno
import stat
import os
import zipfile
import shutil
import sys


# find all directories to zip
def get_dirs_plus_depth(walk, directory, depth=0):
    current_depth = directory.count(os.path.sep)
    correct_depth = [x for x in walk if x.count(os.path.sep) == (current_depth + depth)]
    return correct_depth


def zipdir(src, zip_name):
    """
    Function creates zip archive from src in dst location. The name of archive is zip_name.
    :param src: Path to directory to be archived.
    :param dst: Path where archived dir will be stored.
    :param zip_name: The name of the archive.
    :return: None
    """
    if not os.path.exists(zip_name):
        print("creating :" + zip_name)
        zip_handle = zipfile.ZipFile(zip_name, 'w', compresslevel=0)
        for root, dirs, files in os.walk(src):
            for file in files:
                zip_handle.write(os.path.join(root, file), arcname=os.path.join(root.replace(src, ""), file))
        zip_handle.close()
    return src


def handleRemoveReadonly(func, path, exc):
    excvalue = exc[1]
    if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
        func(path)
    else:
        raise


def remove(dir):
    print("removing: " + dir)
    shutil.rmtree(dir, ignore_errors=False, onerror=handleRemoveReadonly)


if __name__ == '__main__':
    if sys.maxsize > 2 ** 32:
        print("python is 64")

    if len(sys.argv) >= 2:
        directory = sys.argv[1]
        depth = int(sys.argv[2])
    else:
        directory = "A:\\Large_images"
        depth = 5

    if len(sys.argv) > 2:
        outdir = sys.argv[3]
    else:
        outdir = os.path.join("A:\\", "Data2San_IMG")

    walk = [x[0] for x in os.walk(directory)]

    print(len(get_dirs_plus_depth(walk, directory, depth=0)) == 1)
    dirs2zip = get_dirs_plus_depth(walk, directory, depth=depth)

    # create output locations
    zip_files = [os.path.join(outdir, x.replace(directory + "\\", "")) + ".zip" for x in dirs2zip]

    # create output directories
    zip_dir_uniq = list(set([os.path.dirname(x) for x in zip_files]))
    zip_dir_to_create = [x for x in zip_dir_uniq if not os.path.exists(x)]
    [os.makedirs(x) for x in zip_dir_to_create]

    tmp = list(map(zipdir, dirs2zip, zip_files))

    folders2remove = set([os.path.dirname(x) for x in dirs2zip])
    script_file_path = os.path.join(directory, "rm_files.sh")
    with open(script_file_path, "a" if os.path.exists(script_file_path) else "w") as script_file:
        for file_path in folders2remove:
            script_file.write(f"rm -Rf \"{file_path}\"\n")

    tmp = list(map(remove, folders2remove))



# from mapNetworks import Drive
# import MyLog
#
# logger = MyLog.MyLog()
#
# drive = Drive(logger.logger, password="IWJpbzA3YmVhbWVyIQ==", networkPath="\\fgcz-ms.fgcz-net.unizh.ch\Data2San")
# if not drive.mapDrive() == 0:
#     logger.logger.error("Can't map network drive {}".format(bio_beamer_parser.parameters['target_path']))
#     exit(0)
# Drive.mapDrive()
#
# if not drive == 0:
#     drive.unmapDrive()
