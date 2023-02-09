import os
import zipfile

directory = "/Users/witoldwolski/Dropbox/DataAnalysis"
outdir = os.path.join(directory, "zip_res")
walk = [x[0] for x in os.walk(directory)]

# find all directories to zip
def get_dirs_plus_depth(walk, directory , depth = 0):
    current_depth = directory.count(os.path.sep)
    correct_depth = [x for x in walk if x.count(os.path.sep) == (current_depth + depth)]
    return correct_depth

print(len(get_dirs_plus_depth(walk, directory, depth = 0 )) == 1)
dirs2zip = get_dirs_plus_depth(walk, directory, depth = 1 )

dirs2zip[0:4]

# create output locations
zip_files = [os.path.join(outdir, x.replace(directory + "/", "")) + ".zip" for x in dirs2zip]
zip_files[0:3]


# create output directories
zip_dir_uniq = list(set([os.path.dirname(x) for x in zip_files]))
zip_dir_to_create = [x for x in zip_dir_uniq if not os.path.exists(x)]
[print(x) for x in zip_dir_to_create]
[os.makedirs(x) for x in zip_dir_to_create]


def zipdir(src, zip_name):
    """
    Function creates zip archive from src in dst location. The name of archive is zip_name.
    :param src: Path to directory to be archived.
    :param dst: Path where archived dir will be stored.
    :param zip_name: The name of the archive.
    :return: None
    """
    print(src)
    print(zip_name)
    ziph = zipfile.ZipFile(zip_name, 'w', compresslevel=0)
    for root, dirs, files in os.walk(src):
        for file in files:
            ziph.write(os.path.join(root, file), arcname=os.path.join(root.replace(src, ""), file))
    ziph.close()

list(map(zipdir, dirs2zip, zip_files))