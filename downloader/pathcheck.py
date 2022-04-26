import os


# This function checks if the path exists. If it does not, it will create a directory there.
# If the function cannot execute properly, it will exit.
def pathexists(dirpath, relative):
    if relative:
        dirpath = os.getcwd() + dirpath
    # If the path exists, return and continue.
    if os.path.isdir(dirpath):
        return
    else:
        try:
            # If the path does not exist, make it.
            os.mkdir(dirpath)
        except OSError:
            # If error, print debug and exit.
            print("Creation of path failed. Exiting program.")
            exit()


# This function clears the directory of all files, while leaving other directories.
def clearcache(dirpath, relative):
    if relative:
        dirpath = os.getcwd() + dirpath
    for file in os.listdir(dirpath):
        if os.path.isfile(dirpath + file):
            os.remove(dirpath + file)


# This function checks the size of the directory and all files under it.
# If the size of it is greater than one gigabyte, it will return true. else false.
def checkcache(dirpath, relative):
    if relative:
        dirpath = os.getcwd() + dirpath

    size = 0
    for folderpath, foldernames, filenames in os.walk(dirpath):
        for file in filenames:
            path = folderpath + file
            size += os.path.getsize(path)
    # Return true or false depending on whether the size of the files are greater than 1 gigabyte.
    if size > 1000000000:
        return True
    return False


if __name__ == '__main__':
    print(checkcache("\\MP3s\\", True))