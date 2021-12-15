import os, sys, setuptools, subprocess, shutil, platform, urllib, tempfile, ssl, json
from setuptools.command.install import install

assert platform.python_implementation() in ["CPython", "PyPy"], "ERROR: Python implementation must be CPython."
assert (sys.version_info > (3, 5, 0) or sys.version_info > (2, 7, 9)), "ERROR: Python version must be > 3.5."

home = os.path.expanduser("~")
contexto = ssl.create_default_context()
contexto.check_hostname = False
contexto.verify_mode = ssl.CERT_NONE # Ignore SSL Errors and Warnings if any.

def which(cmd, mode = os.F_OK | os.X_OK, path = None):
  # shutil.which is Python 3.3+ only.
  def _access_check(fn, mode):
    return (os.path.exists(fn) and os.access(fn, mode) and not os.path.isdir(fn))

  if _access_check(cmd, mode):
    return cmd
  path = (path or os.environ.get("PATH", os.defpath)).split(os.pathsep)
  if sys.platform == "win32":
    if os.curdir not in path:
      path.insert(0, os.curdir)
    pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
    matches = [cmd for ext in pathext if cmd.lower().endswith(ext.lower())]
    files = [cmd] if matches else [cmd + ext.lower() for ext in pathext]
  else:
    files = [cmd]
  seen = set()
  for dir in path:
    dir = os.path.normcase(dir)
    if dir not in seen:
      seen.add(dir)
      for thefile in files:
        name = os.path.join(dir, thefile)
        if _access_check(name, mode):
          return name
  print("ER\tshutil.which can not find executable " + cmd)
  return cmd


def prepare_folders():
  folders2create = [
    os.path.join(home, ".local"),
    os.path.join(home, ".nimble"),
    os.path.join(home, ".nimble", "pkgs"),
    os.path.join(home, ".choosenim"),
    os.path.join(home, ".choosenim", "channels"),
    os.path.join(home, ".choosenim", "downloads"),
    os.path.join(home, ".choosenim", "toolchains")
  ]

  if sys.platform.startswith("linux"):
    folders2create.append(os.path.join("/usr", "bin", ".nimble"))
    folders2create.append(os.path.join("/usr", "lib", "nim"))
    folders2create.append(os.path.join("/usr", "lib", "nim", "lib"))
    folders2create.append(os.path.join("/etc","nim"))

  for folder in folders2create:
    if not os.path.exists(folder):  # Older Python do not have exists_ok
      print("OK\tCreate folder: " + folder)
      os.makedirs(folder)
    else:
      print("ER\tFolder already exists: " + folder)


def download(url, path):
  with urllib.request.urlopen(url, context=contexto) as response:
    with open(path, 'wb') as outfile:
      shutil.copyfileobj(response, outfile)

def get_link():
  arch = 32 if not platform.machine().endswith("64") else 64  # https://stackoverflow.com/a/12578715
  result = None
  if platform.machine().startswith("armv"):
    arch = arch if arch == 64 else "v7l"
    result = "https://github.com/nim-lang/nightlies/releases/download/latest-devel/linux_arm{}.tar.xz".format(arch)
  elif sys.platform.startswith("linux"):
    result = "https://github.com/nim-lang/nightlies/releases/download/latest-devel/linux_x{}.tar.xz".format(arch)
  elif sys.platform.startswith("win"):
    result = "https://github.com/nim-lang/nightlies/releases/download/latest-devel/windows_x{}.zip".format(arch)
  elif sys.platform.startswith("darwin"):
    result = "https://github.com/nim-lang/nightlies/releases/download/latest-devel/macosx_x{}.tar.xz".format(arch)
  assert result is not None, "Operating system or hardware architecture not supported or download not available or unkown network error."
  return result

def copy_folders(src, dst):
  try:
    shutil.copytree(src, dst)
  except:
    print("ER\tFailed to copy folder: " + src + " into " + dst)
  else:
    print("OK\tCopying: " + src + " into " + dst)

def backup_nim_version(src):
  #Backup the current version
  bsrc = None
  dest = src

  if os.path.exists(src):
    print("Deleting backup folder: ", src)
    shutil.rmtree(src)

  if "usr" not in src:
    bsrc = os.path.join(home, ".nimble")
  else:
    bsrc = os.path.join("/usr", "bin", ".nimble") if "bin" in src else os.path.join("/usr", "lib", "nim")

  os.rename(bsrc, dest)
  os.chmod(dest, 0o775)

def nim_setup():
  # Basically this does the same as choosenim, but in pure Python,
  # so we dont need to "bundle" several choosenim EXEs, bash, etc.
  prepare_folders()
  latest_stable_link = get_link()
  ext = ".exe" if sys.platform.startswith("win") else ""
  filename = os.path.join(tempfile.gettempdir(), latest_stable_link.split("/")[-1])

  print("OK\tDownloading: " + latest_stable_link)
  download(latest_stable_link, filename)
  print("OK\tDecompressing: " + filename + " into " + os.path.join(home, ".choosenim", "toolchains", "nim-#devel"))
  shutil.unpack_archive(filename, os.path.join(home, ".choosenim", "toolchains"))
  for folder in os.listdir(os.path.join(home, ".choosenim", "toolchains")):
    if folder.lower().startswith("nim-"):
      print("OK\tCopying: " + os.path.join(home, ".choosenim", "toolchains", folder) + " into " + os.path.join(home, ".choosenim", "toolchains", "nim-#devel"))
      os.rename(
        os.path.join(home, ".choosenim", "toolchains", folder),
        os.path.join(home, ".choosenim", "toolchains", "nim-#devel"))
      break

  for executable in os.listdir(os.path.join(home, ".choosenim", "toolchains", "nim-#devel", "bin")):
    try:  # To force executables to be executables, in case of buggy permissions, happened in the past.
      os.chmod(os.path.join(home, ".choosenim", "toolchains", "nim-#devel", "bin", executable), 0o775)
      print("OK\tNew binary executable: " + executable)
    except:
      print("ER\tFailed to chmod: " + executable)

  backup_nim_version(os.path.join(home,".nimble_backup"))

  #All folders are stored in the same location for every os
  #copy_folders(os.path.join(home, ".choosenim", "toolchains", "nim-#devel"), os.path.join(home, ".nimble"))
  os.rename(os.path.join(home, ".choosenim", "toolchains", "nim-#devel"), os.path.join(home, ".nimble"))

  if not sys.platform.startswith("win"):
    #shutil.copyfile(os.path.join(home, ".choosenim", "toolchains", "nim-#devel", "bin", "nim" + ext), os.path.join(home, "nim" + ext))
    #shutil.copyfile(os.path.join(home, ".choosenim", "toolchains", "nim-#devel", "bin", "nimble" + ext), os.path.join(home, "nimble" + ext))
    shutil.copyfile(os.path.join(home, ".nimble", "bin", "nim" + ext), os.path.join(home, "nim" + ext))
    shutil.copyfile(os.path.join(home, ".nimble", "bin", "nimble" + ext), os.path.join(home, "nimble" + ext))

    os.chmod(os.path.join("/etc", "nim"), 0o775)
    for config in os.listdir(os.path.join(home, ".nimble", "config")):
      shutil.copyfile(os.path.join(home, ".nimble", "config",config),os.path.join("/etc", "nim",config))

    backup_nim_version(os.path.join("/usr", "bin", ".nimble_backup"))
    backup_nim_version(os.path.join("/usr", "lib", "nim_backup"))

    copy_folders(os.path.join(home, ".nimble", "bin"), os.path.join("/usr", "bin", ".nimble", "bin"))
    copy_folders(os.path.join(home, ".nimble", "lib"), os.path.join("/usr", "lib", "nim"))

    shutil.copyfile(os.path.join(home, ".nimble", "bin", "nim" + ext), os.path.join("/usr", "bin", "nim" + ext))
    shutil.copyfile(os.path.join(home, ".nimble", "bin", "nimble" + ext), os.path.join("/usr", "bin", "nimble" + ext))

    os.chmod(os.path.join("/usr", "bin", ".nimble", "bin"), 0o775)
    os.chmod(os.path.join("/usr", "lib", "nim"), 0o775)

    os.chmod(os.path.join("/usr", "bin", "nim" + ext), 0o775)
    os.chmod(os.path.join("/usr", "bin", "nimble" + ext), 0o775)


def choosenim_setup():
  # We have to check if the user has choosenim already working.
  # Check for choosenim using "choosenim --version", to see if it is already installed,
  # if it is installed, run "choosenim update self" and "choosenim update stable",
  # if it is not installed just return.
  result = False
  shutil.rmtree(os.path.join(home, ".choosenim", "downloads"), ignore_errors=True)  # Clear download cache.
  choosenim_exe = "choosenim.exe" if sys.platform.startswith("win") else "choosenim"
  if subprocess.call(choosenim_exe + " --version", shell=True, timeout=9) == 0:
    print("ER\tChoosenim is already installed and working on the system " + choosenim_exe)
    if subprocess.call(choosenim_exe + " update self", shell=True, timeout=999) != 0:
      print("ER\tFailed to run '" + choosenim_exe + " update self'")  # Dont worry if "update self" fails.
    if subprocess.call(choosenim_exe + " update stable", shell=True, timeout=999) == 0:
      result = True
    else:
      print("ER\tFailed to run '" + choosenim_exe + " update stable'")
  else:
    result = True
  return result


def add_to_path(filename):
  new_path = "export PATH=" + os.path.join(home, ".nimble", "bin") + ":" + os.path.join(home, ".choosenim", "toolchains", "nim-#devel", "bin") + ":$PATH"
  filename = os.path.join(home, filename)
  try:
    found = False
    with open(filename, "a") as f:
      for line in f:
        if new_path == line:
          found = True
      if not found:
        print("OK\tAppending to " + filename)
        f.write(new_path)
  except:
    print("OK\tWriting to " + filename)
    with open(filename, "w") as f:
      f.write(new_path)
  finally:
    # source ".bashrc" updates the PATH without restarting the terminal.   
    os.system("bash -c 'source " + filename + "'")

def run_finishexe():
  # Just for setting required directories in front of %PATH% environment variable
  # before finish.exe download a compatible compiler

  # Add new nim binaries and libs to path
  required_dirs = '{};{}'.format(os.path.join(home, ".nimble", "bin"), os.path.join(home, ".nimble", "lib"))
  for p in os.environ['PATH'].split(';'):
    # Git is required for downloading nimble packages.
    # Python probably got lost after setting the path, so we added them here.
    if "git" in p.lower() or "python" in p.lower():
      required_dirs = required_dirs + ';' + p
  required_dirs = required_dirs + ';' + '%path%'
  # persists this values in path
  os.system("setx PATH \"{}\"".format(required_dirs))

  finishexe = os.path.join(home, ".nimble", "finish.exe")
  os.system("mkdir dist")
  if os.path.exists(finishexe):
    if subprocess.call(finishexe + " -y", shell=True) != 0:
      print("ER\tFailed to run: " + finishexe)
    else:
      print("ER\tReboot to finish installation!")
  else:
    print("ER\tFile not found: " + finishexe)


def install_nimble_packages(nimble_exe, nim_exe=""):
  packages = ["cpython", "nodejs", "fusion"]
  installed_packages = 0
  nimble_cmd = None

  nimble_cmd =  " --accept --noColor --noSSLCheck" if nim_exe == "" else " --accept --noColor --noSSLCheck --nim=" + nim_exe
  nimble_cmd = nimble_exe + nimble_cmd

  if subprocess.call(nimble_cmd + " refresh", shell=True, timeout=999) == 0:
    print("OK\t" + nimble_cmd + " --verbose refresh")
    for package in packages:
      if subprocess.call(nimble_cmd + " --tarballs install " + package, shell=True, timeout=999) == 0:
        print("OK\t" + nimble_cmd + " --tarballs install " + package)
        installed_packages += 1
      else:
        print("ER\tFailed to run '" + nimble_cmd + " --tarballs install " + package + "'")

  return installed_packages


def nimble_setup():
  # After choosenim, we check that Nimble is working,
  # as "nimble" or "~/.nimble/bin/nimble", then install nimpy and fusion
  result = False
  ext = ".exe" if sys.platform.startswith("win") else ""

  # nim and nimble are already in the path, so... let's use them ;)
  nimble_exe = os.path.join(home, ".nimble", "bin", "nimble" + ext) if "GITHUB_ACTIONS" in os.environ else "nimble"+ext
  nim_exe = os.path.join(home, ".nimble", "bin", "nim" + ext) if "GITHUB_ACTIONS" in os.environ else "nim"+ext

  nim_ok = subprocess.call(nim_exe + " --version", shell=True, timeout=9)
  nimble_ok = subprocess.call(nimble_exe + " --version", shell=True, timeout=9)

  if nim_ok + nimble_ok == 0:
    result = install_nimble_packages(nimble_exe, nim_exe) if "GITHUB_ACTIONS" in os.environ else install_nimble_packages(nimble_exe)

  if not sys.platform.startswith("win"):
    copy_folders(os.path.join(home, ".nimble", "pkgs"), os.path.join("/usr", "bin", ".nimble", "pkgs"))

  return result == 3

  #nimble_exe = os.path.join(home, "nimble" + ext)
  #if subprocess.call(nimble_exe + " --version", shell=True, timeout=99) != 0:
  #  nimble_exe = os.path.join(home, '.nimble', 'bin', "nimble" + ext)  # Try full path to "nimble"
  #  if subprocess.call(nimble_exe + " --version", shell=True, timeout=99) != 0:
  #    nimble_exe = "nimble"
  #    if subprocess.call(nimble_exe + " --version", shell=True, timeout=99) != 0:
  #      print("ER\tNim not found, tried 'nimble' and " + nimble_exe)
  #nim_exe = os.path.join(home, "nim" + ext)
  #if subprocess.call(nim_exe + " --version", shell=True, timeout=99) != 0:
  #  nim_exe = os.path.join(home, '.nimble', 'bin', "nim" + ext)  # Try full path to "nim"
  #  if subprocess.call(nim_exe + " --version", shell=True, timeout=99) != 0:
  #    nim_exe = "nim"
  #    if subprocess.call(nim_exe + " --version", shell=True, timeout=99) != 0:
  #      print("ER\tNim not found, tried 'nim' and " + nim_exe)
  #if os.path.exists(nimble_exe):
  #  new_path = "PATH=" + os.path.join(home, ".nimble", "bin") + ":$PATH"
  #  nim_exe = os.path.join(home, ".nimble", "bin","nim")
  #  nimble_cmd = nimble_exe + " --accept --noColor --noSSLCheck --nim=" + nim_exe
  #  if subprocess.call(nimble_cmd + " refresh", shell=True, timeout=999) == 0:
  #    print("OK\t" + nimble_cmd + " --verbose refresh")
  #    if subprocess.call(nimble_cmd + " --tarballs install cpython", shell=True, timeout=999) == 0:
  #      print("OK\t" + nimble_cmd + " --tarballs install cpython")
  #      installed_packages += 1
  #    else:
  #      print("ER\tFailed to run '" + nimble_cmd + " --tarballs install cpython'")
  #    if subprocess.call(nimble_cmd + " --tarballs install nodejs", shell=True, timeout=999) == 0:
  #      print("OK\t" + nimble_cmd + " --tarballs install nodejs")
  #      installed_packages += 1
  #    else:
  #      print("ER\tFailed to run '" + nimble_cmd + " --tarballs install nodejs'")
  #    if subprocess.call(nimble_cmd + " --tarballs install fusion", shell=True, timeout=999) == 0:
  #      print("OK\t" + nimble_cmd + " --tarballs install fusion")
  #      installed_packages += 1
  #    else:
  #      print("ER\tFailed to run '" + nimble_cmd + " --tarballs install fusion'")
  #  else:
  #    print("ER\tFailed to run '" + nimble_cmd + " refresh'")
  #else:
  #  print("ER\tFile not found " + nimble_exe)
  #if installed_packages == 3:
  #    result = True
  #return result


def postinstall():
  shutil.rmtree(os.path.join(home, ".choosenim", "toolchains", "nim-#devel", "doc"), ignore_errors=True)
  shutil.rmtree(os.path.join(home, ".choosenim", "toolchains", "nim-#devel", "tests"), ignore_errors=True)
  shutil.rmtree(os.path.join(home, ".choosenim", "toolchains", "nim-#devel", "nimpretty", "tests"), ignore_errors=True)
  shutil.rmtree(os.path.join(home, ".choosenim", "toolchains", "nim-#devel", "testament", "tests"), ignore_errors=True)
  shutil.rmtree(os.path.join(home, ".choosenim", "toolchains", "nim-#devel", "nimsuggest", "tests"), ignore_errors=True)
  shutil.rmtree(os.path.join(home, ".choosenim", "toolchains", "nim-#devel", "tools", "atlas", "tests"), ignore_errors=True)
  shutil.rmtree(os.path.join(home, ".choosenim", "toolchains", "nim-#devel", "dist", "nimble", "tests"), ignore_errors=True)

class X(install):

  def run(self):
    install.run(self)    # This is required by Python.
    if choosenim_setup():  # Check if choosenim is already installed.
      nim_setup()                   # Install Nim.
      if not sys.platform.startswith("win"):
        add_to_path(".bashrc")
        add_to_path(".profile")
        add_to_path(".bash_profile")
        add_to_path(".zshrc")
        add_to_path(".zshenv")
#        add_to_path("/etc/profile") ?????
      else:  # Windows
        run_finishexe()
      if not nimble_setup():                       # Update Nimble.
        print("ER\tFailed to setup Nimble")
      postinstall()
    else:
      raise Exception(IOError, "Failed to install Nim")

try:
  setuptools.setup(
    name         = "choosenim_install",
    author       = "Juan_Carlos.nim",
    cmdclass     = {"install": X},
    author_email = "UNKNOWN",
    url          = "UNKNOWN",
  )
except Exception as e:
  print(e)
  print("ER\tPlease re-run as admin.")
