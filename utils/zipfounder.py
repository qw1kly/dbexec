from functools import wraps
import os, zipfile


def type_of_filter(type : str):
    def format_filter(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            all_objects = func(*args, **kwargs)
            return list(filter(lambda name: name.endswith(type), all_objects))
        return wrapper
    return format_filter


@type_of_filter(type='.zip')
def list_of_databases():
    return os.listdir("bak_files")


def extract_bak(zip_path, work_dir):
    with zipfile.ZipFile(zip_path) as z:
        bak_name = next(n for n in z.namelist() if n.lower().endswith(".bak"))
        z.extract(bak_name, work_dir)
        return os.path.join(work_dir, bak_name)