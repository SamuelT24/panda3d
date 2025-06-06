#!/usr/bin/env python
########################################################################
#
# To build panda using this script, type 'makepanda.py' on unix
# or 'makepanda.bat' on windows, and examine the help-text.
# Then run the script again with the appropriate options to compile
# panda3d.
#
########################################################################

import sys
if sys.version_info < (3, 8):
    print("This version of Python is not supported, use version 3.8 or higher.")
    exit(1)

try:
    import os
    import time
    import re
    import getopt
    import threading
    import signal
    import shutil
    import plistlib
    import queue
except KeyboardInterrupt:
    raise
except:
    print("You are either using an incomplete or an old version of Python!")
    print("Please install the development package of Python and try again.")
    exit(1)

from makepandacore import *

from sysconfig import get_platform

try:
    import zlib
except:
    zlib = None

########################################################################
##
## PARSING THE COMMAND LINE OPTIONS
##
## You might be tempted to change the defaults by editing them
## here.  Don't do it.  Instead, create a script that compiles
## panda with your preferred options.  Or, create
## a 'makepandaPreferences' file and put it into your python path.
##
########################################################################

COMPILER=0
INSTALLER=0
WHEEL=0
RUNTESTS=0
GENMAN=0
COMPRESSOR="zlib"
THREADCOUNT=0
CFLAGS=""
CXXFLAGS=""
LDFLAGS=""
DISTRIBUTOR=""
VERSION=None
DEBVERSION=None
WHLVERSION=None
RPMVERSION=None
RPMRELEASE="1"
GIT_COMMIT=None
MAJOR_VERSION=None
OSX_ARCHS=[]
STRDXSDKVERSION = 'default'
WINDOWS_SDK = None
MSVC_VERSION = None
BOOUSEINTELCOMPILER = False
OPENCV_VER_23 = False
PLATFORM = None
COPY_PYTHON = True

PkgListSet(["PYTHON", "DIRECT",                        # Python support
  "GL", "GLES", "GLES2"] + DXVERSIONS + ["TINYDISPLAY", "NVIDIACG", # 3D graphics
  "EGL",                                               # OpenGL (ES) integration
  "EIGEN",                                             # Linear algebra acceleration
  "OPENAL", "FMODEX",                                  # Audio playback
  "VORBIS", "OPUS", "FFMPEG", "SWSCALE", "SWRESAMPLE", # Audio decoding
  "ODE", "BULLET", "PANDAPHYSICS",                     # Physics
  "SPEEDTREE",                                         # SpeedTree
  "ZLIB", "PNG", "JPEG", "TIFF", "OPENEXR", "SQUISH",  # 2D Formats support
  "FCOLLADA", "ASSIMP", "EGG",                         # 3D Formats support
  "FREETYPE", "HARFBUZZ",                              # Text rendering
  "VRPN", "OPENSSL",                                   # Transport
  "FFTW",                                              # Algorithm helpers
  "ARTOOLKIT", "OPENCV", "DIRECTCAM", "VISION",        # Augmented Reality
  "GTK3",                                              # GTK3 is used for PStats on Unix
  "MFC", "WX", "FLTK",                                 # Used for web plug-in only
  "COCOA",                                             # macOS toolkits
  "X11",                                               # Unix platform support
  "PANDATOOL", "PVIEW", "DEPLOYTOOLS",                 # Toolchain
  "SKEL",                                              # Example SKEL project
  "PANDAFX",                                           # Some distortion special lenses
  "PANDAPARTICLESYSTEM",                               # Built in particle system
  "CONTRIB",                                           # Experimental
  "SSE2", "NEON",                                      # Compiler features
  "MIMALLOC",                                          # Memory allocators
  "NAMETAG", "MOVEMENT", "NAVIGATION",                 # libotp
  "DNA", "SUIT", "PETS",                               # libtoontown
])

CheckPandaSourceTree()

def keyboardInterruptHandler(x,y):
    exit("keyboard interrupt")

signal.signal(signal.SIGINT, keyboardInterruptHandler)

########################################################################
##
## Command-line parser.
##
## You can type "makepanda --help" to see all the options.
##
########################################################################

def usage(problem):
    if problem:
        print("")
        print("Error parsing command-line input: %s" % (problem))

    print("")
    print("Makepanda generates a 'built' subdirectory containing a")
    print("compiled copy of Panda3D.  Command-line arguments are:")
    print("")
    print("  --help            (print the help message you're reading now)")
    print("  --verbose         (print out more information)")
    print("  --tests           (run the test suite)")
    print("  --installer       (build an installer)")
    print("  --wheel           (build a pip-installable .whl)")
    print("  --optimize X      (optimization level can be 1,2,3,4)")
    print("  --version X       (set the panda version number)")
    print("  --lzma            (use lzma compression when building Windows installer)")
    print("  --distributor X   (short string identifying the distributor of the build)")
    print("  --outputdir X     (use the specified directory instead of 'built')")
    print("  --threads N       (use the multithreaded build system. see manual)")
    print("  --universal       (build universal binaries (macOS 11.0+ only))")
    print("  --override \"O=V\"  (override dtool_config/prc option value)")
    print("  --static          (builds libraries for static linking)")
    print("  --target X        (experimental cross-compilation (android only))")
    print("  --arch X          (target architecture for cross-compilation)")
    print("")
    for pkg in PkgListGet():
        p = pkg.lower()
        print("  --use-%-9s   --no-%-9s (enable/disable use of %s)"%(p, p, pkg))
    if sys.platform != 'win32':
        print("  --<PKG>-incdir    (custom location for header files of thirdparty package)")
        print("  --<PKG>-libdir    (custom location for library files of thirdparty package)")
    print("")
    print("  --nothing         (disable every third-party lib)")
    print("  --everything      (enable every third-party lib)")
    print("  --directx-sdk=X   (specify version of DirectX SDK to use: jun2010, aug2009)")
    print("  --windows-sdk=X   (specify Windows SDK version, eg. 7.1, 8.1, 10 or 11.  Default is 8.1)")
    print("  --msvc-version=X  (specify Visual C++ version, eg. 14.1, 14.2, 14.3.  Default is 14.1)")
    print("  --use-icl         (experimental setting to use an intel compiler instead of MSVC on Windows)")
    print("")
    print("The simplest way to compile panda is to just type:")
    print("")
    print("  makepanda --everything")
    print("")
    os._exit(1)

def parseopts(args):
    global INSTALLER,WHEEL,RUNTESTS,GENMAN,DISTRIBUTOR,VERSION
    global COMPRESSOR,THREADCOUNT,OSX_ARCHS
    global DEBVERSION,WHLVERSION,RPMVERSION,RPMRELEASE,GIT_COMMIT
    global STRDXSDKVERSION, WINDOWS_SDK, MSVC_VERSION, BOOUSEINTELCOMPILER
    global COPY_PYTHON

    # Options for which to display a deprecation warning.
    removedopts = [
        "use-touchinput", "no-touchinput", "no-awesomium", "no-directscripts",
        "no-carbon", "no-physx", "no-rocket", "host", "osxtarget=",
        "no-max6", "no-max7", "no-max8", "no-max9", "no-max2009",
        "no-max2010", "no-max2011", "no-max2012", "no-max2013", "no-max2014",
        "no-maya6", "no-maya65", "no-maya7", "no-maya8", "no-maya85",
        "no-maya2008", "no-maya2009", "no-maya2010", "no-maya2011",
        "no-maya2012", "no-maya2013", "no-maya20135", "no-maya2014",
        "no-maya2015", "no-maya2016", "no-maya20165", "no-maya2017",
        "no-maya2018", "no-maya2019", "no-maya2020", "no-maya2022",
        ]

    # All recognized options.
    longopts = [
        "help","distributor=","verbose","tests",
        "optimize=","everything","nothing","installer","wheel","rtdist","nocolor",
        "version=","lzma","no-python","threads=","outputdir=","override=",
        "static","debversion=","rpmversion=","rpmrelease=","p3dsuffix=","rtdist-version=",
        "directx-sdk=", "windows-sdk=", "msvc-version=", "clean", "use-icl",
        "universal", "target=", "arch=", "git-commit=", "no-copy-python",
        "cggl-incdir=", "cggl-libdir=",
        ] + removedopts

    anything = 0
    optimize = ""
    target = None
    target_archs = []
    universal = False
    clean_build = False
    for pkg in PkgListGet():
        longopts.append("use-" + pkg.lower())
        longopts.append("no-" + pkg.lower())
        longopts.append(pkg.lower() + "-incdir=")
        longopts.append(pkg.lower() + "-libdir=")

    try:
        opts, extras = getopt.getopt(args, "", longopts)
        for option, value in opts:
            if (option=="--help"): raise Exception
            elif (option=="--optimize"): optimize=value
            elif (option=="--installer"): INSTALLER=1
            elif (option=="--tests"): RUNTESTS=1
            elif (option=="--wheel"): WHEEL=1
            elif (option=="--verbose"): SetVerbose(True)
            elif (option=="--distributor"): DISTRIBUTOR=value
            elif (option=="--genman"): GENMAN=1
            elif (option=="--everything"): PkgEnableAll()
            elif (option=="--nothing"): PkgDisableAll()
            elif (option=="--threads"): THREADCOUNT=int(value)
            elif (option=="--outputdir"): SetOutputDir(value.strip())
            elif (option=="--universal"): universal = True
            elif (option=="--target"): target = value.strip()
            elif (option=="--arch"): target_archs.append(value.strip())
            elif (option=="--nocolor"): DisableColors()
            elif (option=="--version"):
                match = re.match(r'^\d+\.\d+(\.\d+)+', value)
                if not match:
                    usage("version requires three digits")
                WHLVERSION = value
                VERSION = match.group()
            elif (option=="--lzma"): COMPRESSOR="lzma"
            elif (option=="--override"): AddOverride(value.strip())
            elif (option=="--static"): SetLinkAllStatic(True)
            elif (option=="--debversion"): DEBVERSION=value
            elif (option=="--rpmversion"): RPMVERSION=value
            elif (option=="--rpmrelease"): RPMRELEASE=value
            elif (option=="--git-commit"): GIT_COMMIT=value
            # Backward compatibility, OPENGL was renamed to GL
            elif (option=="--use-opengl"): PkgEnable("GL")
            elif (option=="--no-opengl"): PkgDisable("GL")
            elif (option=="--directx-sdk"):
                STRDXSDKVERSION = value.strip().lower()
                if STRDXSDKVERSION == '':
                    print("No DirectX SDK version specified. Using 'default' DirectX SDK search")
                    STRDXSDKVERSION = 'default'
            elif (option=="--windows-sdk"):
                WINDOWS_SDK = value.strip().lower()
            elif (option=="--msvc-version"):
                MSVC_VERSION = value.strip().lower()
            elif (option=="--use-icl"): BOOUSEINTELCOMPILER = True
            elif (option=="--clean"): clean_build = True
            elif (option=="--no-copy-python"): COPY_PYTHON = False
            elif (option[2:] in removedopts or option[2:]+'=' in removedopts):
                Warn("Ignoring removed option %s" % (option))
            else:
                for pkg in PkgListGet() + ['CGGL']:
                    if option == "--use-" + pkg.lower():
                        PkgEnable(pkg)
                        break
                    elif option == "--no-" + pkg.lower():
                        PkgDisable(pkg)
                        break
                    elif option == "--" + pkg.lower() + "-incdir":
                        PkgSetCustomLocation(pkg)
                        IncDirectory(pkg, os.path.expanduser(value))
                        break
                    elif option == "--" + pkg.lower() + "-libdir":
                        PkgSetCustomLocation(pkg)
                        LibDirectory(pkg, os.path.expanduser(value))
                        break
            if (option == "--everything" or option.startswith("--use-")
                or option == "--nothing" or option.startswith("--no-")):
                anything = 1
    except:
        usage(sys.exc_info()[1])

    if not anything:
        usage("You should specify a list of packages to use or --everything to enable all packages.")

    if (optimize==""): optimize = "3"

    if target is not None or target_archs:
        SetTarget(target, target_archs[-1] if target_archs else None)

    if universal:
        if target_archs:
            exit("--universal is incompatible with --arch")

        OSX_ARCHS.append("x86_64")
        OSX_ARCHS.append("arm64")
    elif target_archs:
        OSX_ARCHS = target_archs
    elif GetTarget() == 'darwin':
        OSX_ARCHS = (GetTargetArch(),)

    try:
        SetOptimize(int(optimize))
        assert GetOptimize() in [1, 2, 3, 4]
    except:
        usage("Invalid setting for OPTIMIZE")

    if GIT_COMMIT is not None and not re.match("^[a-f0-9]{40}$", GIT_COMMIT):
        usage("Invalid SHA-1 hash given for --git-commit option!")

    if GetTarget() == 'windows':
        if not MSVC_VERSION:
            print("No MSVC version specified. Defaulting to 14.1 (Visual Studio 2017).")
            MSVC_VERSION = (14, 1)
        else:
            try:
                MSVC_VERSION = tuple(int(d) for d in MSVC_VERSION.split('.'))[:2]
                if (len(MSVC_VERSION) == 1):
                    MSVC_VERSION += (0,)
            except:
                usage("Invalid setting for --msvc-version")

        if MSVC_VERSION < (14, 1):
            warn_prefix = "%sERROR:%s " % (GetColor("red"), GetColor())
            print("=========================================================================")
            print(warn_prefix + "Support for MSVC versions before 2017 has been discontinued.")
            print("=========================================================================")
            sys.stdout.flush()
            time.sleep(1.0)
            sys.exit(1)

    if clean_build and os.path.isdir(GetOutputDir()):
        print("Deleting %s" % (GetOutputDir()))
        shutil.rmtree(GetOutputDir())

parseopts(sys.argv[1:])

########################################################################
##
## Handle environment variables.
##
########################################################################

if ("CFLAGS" in os.environ):
    CFLAGS = os.environ["CFLAGS"].strip()

if ("CXXFLAGS" in os.environ):
    CXXFLAGS = os.environ["CXXFLAGS"].strip()

if ("RPM_OPT_FLAGS" in os.environ):
    CFLAGS += " " + os.environ["RPM_OPT_FLAGS"].strip()
    CXXFLAGS += " " + os.environ["RPM_OPT_FLAGS"].strip()

if ("LDFLAGS" in os.environ):
    LDFLAGS = os.environ["LDFLAGS"].strip()

os.environ["MAKEPANDA"] = os.path.abspath(sys.argv[0])
if GetHost() == "darwin":
    if tuple(OSX_ARCHS) == ('arm64',):
        os.environ["MACOSX_DEPLOYMENT_TARGET"] = "11.0"
    else:
        os.environ["MACOSX_DEPLOYMENT_TARGET"] = "10.9"

########################################################################
##
## Configure things based on the command-line parameters.
##
########################################################################

if VERSION is None:
    # Take the value from the setup.cfg file.
    VERSION = GetMetadataValue('version')
    match = re.match(r'^\d+\.\d+(\.\d+)+', VERSION)
    if not match:
        exit("Invalid version %s in setup.cfg, three digits are required" % (VERSION))
    if WHLVERSION is None:
        WHLVERSION = VERSION
    VERSION = match.group()

if WHLVERSION is None:
    WHLVERSION = VERSION

print("Version: %s" % VERSION)

if DEBVERSION is None:
    DEBVERSION = VERSION

if RPMVERSION is None:
    RPMVERSION = VERSION

MAJOR_VERSION = '.'.join(VERSION.split('.')[:2])

# Now determine the distutils-style platform tag for the target system.
target = GetTarget()
target_arch = GetTargetArch()
if target == 'windows':
    if target_arch == 'x64':
        PLATFORM = 'win-amd64'
    else:
        PLATFORM = 'win32'

elif target == 'darwin':
    arch_tag = None
    if not OSX_ARCHS:
        arch_tag = target_arch
    elif len(OSX_ARCHS) == 1:
        arch_tag = OSX_ARCHS[0]
    elif frozenset(OSX_ARCHS) == frozenset(('i386', 'ppc')):
        arch_tag = 'fat'
    elif frozenset(OSX_ARCHS) == frozenset(('x86_64', 'i386')):
        arch_tag = 'intel'
    elif frozenset(OSX_ARCHS) == frozenset(('x86_64', 'ppc64')):
        arch_tag = 'fat64'
    elif frozenset(OSX_ARCHS) == frozenset(('x86_64', 'i386', 'ppc')):
        arch_tag = 'fat32'
    elif frozenset(OSX_ARCHS) == frozenset(('x86_64', 'i386', 'ppc64', 'ppc')):
        arch_tag = 'universal'
    elif frozenset(OSX_ARCHS) == frozenset(('x86_64', 'arm64')):
        arch_tag = 'universal2'
    else:
        raise RuntimeError('No arch tag for arch combination %s' % OSX_ARCHS)

    if arch_tag == 'arm64':
        PLATFORM = 'macosx-11.0-' + arch_tag
    elif sys.version_info >= (3, 13):
        PLATFORM = 'macosx-10.13-' + arch_tag
    else:
        PLATFORM = 'macosx-10.9-' + arch_tag

elif target == 'linux' and (os.path.isfile("/lib/libc-2.5.so") or os.path.isfile("/lib64/libc-2.5.so")) and os.path.isdir("/opt/python"):
    # This is manylinux1.  A bit of a sloppy check, though.
    if target_arch in ('x86_64', 'amd64'):
        PLATFORM = 'manylinux1-x86_64'
    elif target_arch in ('arm64', 'aarch64'):
        PLATFORM = 'manylinux1-aarch64'
    else:
        PLATFORM = 'manylinux1-i686'

elif target == 'linux' and (os.path.isfile("/lib/libc-2.12.so") or os.path.isfile("/lib64/libc-2.12.so")) and os.path.isdir("/opt/python"):
    # Same sloppy check for manylinux2010.
    if target_arch in ('x86_64', 'amd64'):
        PLATFORM = 'manylinux2010-x86_64'
    elif target_arch in ('arm64', 'aarch64'):
        PLATFORM = 'manylinux2010-aarch64'
    else:
        PLATFORM = 'manylinux2010-i686'

elif target == 'linux' and (os.path.isfile("/lib/libc-2.17.so") or os.path.isfile("/lib64/libc-2.17.so")) and os.path.isdir("/opt/python"):
    # Same sloppy check for manylinux2014.
    if target_arch in ('x86_64', 'amd64'):
        PLATFORM = 'manylinux2014-x86_64'
    elif target_arch in ('arm64', 'aarch64'):
        PLATFORM = 'manylinux2014-aarch64'
    else:
        PLATFORM = 'manylinux2014-i686'

elif target == 'linux' and (os.path.isfile("/lib/i386-linux-gnu/libc-2.24.so") or os.path.isfile("/lib/x86_64-linux-gnu/libc-2.24.so")) and os.path.isdir("/opt/python"):
    # Same sloppy check for manylinux_2_24.
    if target_arch in ('x86_64', 'amd64'):
        PLATFORM = 'manylinux_2_24-x86_64'
    elif target_arch in ('arm64', 'aarch64'):
        PLATFORM = 'manylinux_2_24-aarch64'
    else:
        PLATFORM = 'manylinux_2_24-i686'

elif target == 'linux' and os.path.isfile("/lib64/libc-2.28.so") and os.path.isfile('/etc/almalinux-release') and os.path.isdir("/opt/python"):
    # Same sloppy check for manylinux_2_28.
    if target_arch in ('x86_64', 'amd64'):
        PLATFORM = 'manylinux_2_28-x86_64'
    elif target_arch in ('arm64', 'aarch64'):
        PLATFORM = 'manylinux_2_28-aarch64'
    else:
        raise RuntimeError('Unhandled arch %s, please file a bug report!' % (target_arch))

elif not CrossCompiling():
    if HasTargetArch():
        # Replace the architecture in the platform string.
        platform_parts = get_platform().rsplit('-', 1)
        if target_arch == 'amd64':
            target_arch = 'x86_64'
        PLATFORM = platform_parts[0] + '-' + target_arch
    else:
        # We're not cross-compiling; just take the host arch.
        PLATFORM = get_platform()

else:
    if target_arch == 'amd64':
        target_arch = 'x86_64'
    if target_arch == 'arm' and target == 'android':
        target_arch = 'armv7a'
    PLATFORM = '{0}-{1}'.format(target, target_arch)


print("Platform: %s" % PLATFORM)

outputdir_suffix = ""

if DISTRIBUTOR == "":
    DISTRIBUTOR = "makepanda"

if not IsCustomOutputDir():
    if GetTarget() == "windows" and GetTargetArch() == 'x64':
        outputdir_suffix += '_x64'

    SetOutputDir("built" + outputdir_suffix)

if (INSTALLER) and (PkgSkip("PYTHON")) and GetTarget() == 'windows':
    exit("Cannot build installer on Windows without python")

if WHEEL and PkgSkip("PYTHON"):
    exit("Cannot build wheel without Python")

if not os.path.isdir("contrib"):
    PkgDisable("CONTRIB")

# TEMP: Disable libp3navigation until we need it.
PkgDisable("NAVIGATION")

########################################################################
##
## Load the dependency cache.
##
########################################################################

LoadDependencyCache()

########################################################################
##
## Locate various SDKs.
##
########################################################################

MakeBuildTree()

SdkLocateDirectX(STRDXSDKVERSION)
SdkLocateMacOSX(OSX_ARCHS)
SdkLocatePython(False)
SdkLocateWindows(WINDOWS_SDK)
SdkLocateSpeedTree()
SdkLocateAndroid()

SdkAutoDisableDirectX()
SdkAutoDisableSpeedTree()

if not PkgSkip("PYTHON") and SDK["PYTHONVERSION"] == "python2.7":
    pref = "%sERROR:%s " % (GetColor("red"), GetColor())
    print("========================================================================")
    print(pref + "Python 2.7 has reached EOL as of January 1, 2020 and is no longer")
    print(pref + "supported.  Please upgrade to Python 3.5 or later.")
    print("========================================================================")
    sys.stdout.flush()
    sys.exit(1)

########################################################################
##
## Choose a Compiler.
##
## This should also set up any environment variables needed to make
## the compiler work.
##
########################################################################

if GetHost() == 'windows' and GetTarget() == 'windows':
    COMPILER = "MSVC"
    SdkLocateVisualStudio(MSVC_VERSION)
else:
    COMPILER = "GCC"

# Ensure we've pip-installed interrogate if we need it before setting
# PYTHONHOME, etc.
if not PkgSkip("PYTHON"):
    GetInterrogate()

SetupBuildEnvironment(COMPILER)

########################################################################
##
## External includes, external libraries, and external defsyms.
##
########################################################################

IncDirectory("ALWAYS", GetOutputDir()+"/tmp")
IncDirectory("ALWAYS", GetOutputDir()+"/include")

if (COMPILER == "MSVC"):
    PkgDisable("X11")
    PkgDisable("GLES")
    PkgDisable("GLES2")
    PkgDisable("EGL")
    PkgDisable("COCOA")
    DefSymbol("FLEX", "YY_NO_UNISTD_H")
    if not PkgSkip("PYTHON"):
        IncDirectory("ALWAYS", SDK["PYTHON"] + "/include")
        LibDirectory("ALWAYS", SDK["PYTHON"] + "/libs")
    SmartPkgEnable("EIGEN",     "eigen3",     (), ("Eigen/Dense",), target_pkg = 'ALWAYS')
    for pkg in PkgListGet():
        if not PkgSkip(pkg):
            if (pkg[:2]=="DX"):
                IncDirectory(pkg, SDK[pkg]      + "/include")
            elif GetThirdpartyDir() is not None:
                IncDirectory(pkg, GetThirdpartyDir() + pkg.lower() + "/include")
    for pkg in DXVERSIONS:
        if not PkgSkip(pkg):
            vnum=pkg[2:]

            if GetTargetArch() == 'x64':
                LibDirectory(pkg, SDK[pkg] + '/lib/x64')
            else:
                LibDirectory(pkg, SDK[pkg] + '/lib/x86')
                LibDirectory(pkg, SDK[pkg] + '/lib')

            LibName(pkg, 'd3dVNUM.lib'.replace("VNUM", vnum))
            LibName(pkg, 'd3dxVNUM.lib'.replace("VNUM", vnum))
            LibName(pkg, 'dxerr.lib')
            #LibName(pkg, 'ddraw.lib')
            LibName(pkg, 'dxguid.lib')

            if SDK.get("VISUALSTUDIO_VERSION") >= (14,0):
                # dxerr needs this for __vsnwprintf definition.
                LibName(pkg, 'legacy_stdio_definitions.lib')

    if not PkgSkip("FREETYPE") and os.path.isdir(GetThirdpartyDir() + "freetype/include/freetype2"):
        IncDirectory("FREETYPE", GetThirdpartyDir() + "freetype/include/freetype2")

    IncDirectory("ALWAYS", GetThirdpartyDir() + "extras/include")
    LibName("WINSOCK", "wsock32.lib")
    LibName("WINSOCK2", "wsock32.lib")
    LibName("WINSOCK2", "ws2_32.lib")
    LibName("WINCOMCTL", "comctl32.lib")
    LibName("WINCOMDLG", "comdlg32.lib")
    LibName("UXTHEME", "uxtheme.lib")
    LibName("WINUSER", "user32.lib")
    LibName("WINMM", "winmm.lib")
    LibName("WINIMM", "imm32.lib")
    LibName("WINKERNEL", "kernel32.lib")
    LibName("WINOLE", "ole32.lib")
    LibName("WINOLEAUT", "oleaut32.lib")
    LibName("WINOLDNAMES", "oldnames.lib")
    LibName("WINSHELL", "shell32.lib")
    LibName("WINGDI", "gdi32.lib")
    LibName("ADVAPI", "advapi32.lib")
    LibName("IPHLPAPI", "iphlpapi.lib")
    LibName("SETUPAPI", "setupapi.lib")
    LibName("GL", "opengl32.lib")
    LibName("GLES", "libgles_cm.lib")
    LibName("GLES2", "libGLESv2.lib")
    LibName("EGL", "libEGL.lib")
    LibName("MSIMG", "msimg32.lib")
    if (PkgSkip("DIRECTCAM")==0): LibName("DIRECTCAM", "strmiids.lib")
    if (PkgSkip("DIRECTCAM")==0): LibName("DIRECTCAM", "quartz.lib")
    if (PkgSkip("DIRECTCAM")==0): LibName("DIRECTCAM", "odbc32.lib")
    if (PkgSkip("DIRECTCAM")==0): LibName("DIRECTCAM", "odbccp32.lib")
    if (PkgSkip("MIMALLOC")==0): LibName("MIMALLOC", GetThirdpartyDir() + "mimalloc/lib/mimalloc-static.lib")
    if (PkgSkip("OPENSSL")==0):
        if os.path.isfile(GetThirdpartyDir() + "openssl/lib/libpandassl.lib"):
            LibName("OPENSSL", GetThirdpartyDir() + "openssl/lib/libpandassl.lib")
            LibName("OPENSSL", GetThirdpartyDir() + "openssl/lib/libpandaeay.lib")
        elif os.path.isfile(GetThirdpartyDir() + "openssl/lib/ssleay32.lib"):
            LibName("OPENSSL", GetThirdpartyDir() + "openssl/lib/libeay32.lib")
            LibName("OPENSSL", GetThirdpartyDir() + "openssl/lib/ssleay32.lib")
        else:
            LibName("OPENSSL", GetThirdpartyDir() + "openssl/lib/libssl.lib")
            LibName("OPENSSL", GetThirdpartyDir() + "openssl/lib/libcrypto.lib")
            LibName("OPENSSL", "crypt32.lib")
            LibName("OPENSSL", "ws2_32.lib")
    if (PkgSkip("PNG")==0):
        if os.path.isfile(GetThirdpartyDir() + "png/lib/libpng16_static.lib"):
            LibName("PNG", GetThirdpartyDir() + "png/lib/libpng16_static.lib")
        else:
            LibName("PNG", GetThirdpartyDir() + "png/lib/libpng_static.lib")
    if (PkgSkip("TIFF")==0):
        if os.path.isfile(GetThirdpartyDir() + "tiff/lib/libtiff.lib"):
            LibName("TIFF", GetThirdpartyDir() + "tiff/lib/libtiff.lib")
        else:
            LibName("TIFF", GetThirdpartyDir() + "tiff/lib/tiff.lib")
    if (PkgSkip("OPENEXR")==0):
        if os.path.isfile(GetThirdpartyDir() + "openexr/lib/OpenEXRCore-3_1.lib"):
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/OpenEXR-3_1.lib")
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/IlmThread-3_1.lib")
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/Imath-3_1.lib")
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/Iex-3_1.lib")
        elif os.path.isfile(GetThirdpartyDir() + "openexr/lib/OpenEXR-3_0.lib"):
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/OpenEXR-3_0.lib")
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/IlmThread-3_0.lib")
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/Imath-3_0.lib")
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/Iex-3_0.lib")
        elif os.path.isfile(GetThirdpartyDir() + "openexr/lib/OpenEXR.lib"):
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/OpenEXR.lib")
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/IlmThread.lib")
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/Imath.lib")
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/Iex.lib")
        else:
            suffix = ""
            if os.path.isfile(GetThirdpartyDir() + "openexr/lib/IlmImf-2_2.lib"):
                suffix = "-2_2"
            elif os.path.isfile(GetThirdpartyDir() + "openexr/lib/IlmImf-2_3.lib"):
                suffix = "-2_3"
            elif os.path.isfile(GetThirdpartyDir() + "openexr/lib/IlmImf-2_4.lib"):
                suffix = "-2_4"
                LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/Imath" + suffix + ".lib")
            if os.path.isfile(GetThirdpartyDir() + "openexr/lib/IlmImf" + suffix + "_s.lib"):
                suffix += "_s"  # _s suffix observed for OpenEXR 2.3 only so far
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/IlmImf" + suffix + ".lib")
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/IlmThread" + suffix + ".lib")
            LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/Iex" + suffix + ".lib")
            if suffix == "-2_2":
                LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/Half.lib")
            else:
                LibName("OPENEXR", GetThirdpartyDir() + "openexr/lib/Half" + suffix + ".lib")
        IncDirectory("OPENEXR", GetThirdpartyDir() + "openexr/include/OpenEXR")
        IncDirectory("OPENEXR", GetThirdpartyDir() + "openexr/include/Imath")
    if (PkgSkip("JPEG")==0):     LibName("JPEG",     GetThirdpartyDir() + "jpeg/lib/jpeg-static.lib")
    if (PkgSkip("ZLIB")==0):     LibName("ZLIB",     GetThirdpartyDir() + "zlib/lib/zlibstatic.lib")
    if (PkgSkip("VRPN")==0):     LibName("VRPN",     GetThirdpartyDir() + "vrpn/lib/vrpn.lib")
    if (PkgSkip("VRPN")==0):     LibName("VRPN",     GetThirdpartyDir() + "vrpn/lib/quat.lib")
    if (PkgSkip("NVIDIACG")==0): LibName("CGGL",     GetThirdpartyDir() + "nvidiacg/lib/cgGL.lib")
    if (PkgSkip("NVIDIACG")==0): LibName("CGDX9",    GetThirdpartyDir() + "nvidiacg/lib/cgD3D9.lib")
    if (PkgSkip("NVIDIACG")==0): LibName("NVIDIACG", GetThirdpartyDir() + "nvidiacg/lib/cg.lib")
    if (PkgSkip("FREETYPE")==0): LibName("FREETYPE", GetThirdpartyDir() + "freetype/lib/freetype.lib")
    if (PkgSkip("HARFBUZZ")==0):
        LibName("HARFBUZZ", GetThirdpartyDir() + "harfbuzz/lib/harfbuzz.lib")
        IncDirectory("HARFBUZZ", GetThirdpartyDir() + "harfbuzz/include/harfbuzz")
    if (PkgSkip("FFTW")==0):     LibName("FFTW",     GetThirdpartyDir() + "fftw/lib/fftw3.lib")
    if (PkgSkip("ARTOOLKIT")==0):LibName("ARTOOLKIT",GetThirdpartyDir() + "artoolkit/lib/libAR.lib")
    if (PkgSkip("OPENCV")==0):   LibName("OPENCV",   GetThirdpartyDir() + "opencv/lib/cv.lib")
    if (PkgSkip("OPENCV")==0):   LibName("OPENCV",   GetThirdpartyDir() + "opencv/lib/highgui.lib")
    if (PkgSkip("OPENCV")==0):   LibName("OPENCV",   GetThirdpartyDir() + "opencv/lib/cvaux.lib")
    if (PkgSkip("OPENCV")==0):   LibName("OPENCV",   GetThirdpartyDir() + "opencv/lib/ml.lib")
    if (PkgSkip("OPENCV")==0):   LibName("OPENCV",   GetThirdpartyDir() + "opencv/lib/cxcore.lib")
    if (PkgSkip("FFMPEG")==0):   LibName("FFMPEG",   GetThirdpartyDir() + "ffmpeg/lib/avcodec.lib")
    if (PkgSkip("FFMPEG")==0):   LibName("FFMPEG",   GetThirdpartyDir() + "ffmpeg/lib/avformat.lib")
    if (PkgSkip("FFMPEG")==0):   LibName("FFMPEG",   GetThirdpartyDir() + "ffmpeg/lib/avutil.lib")
    if (PkgSkip("SWSCALE")==0):  LibName("SWSCALE",  GetThirdpartyDir() + "ffmpeg/lib/swscale.lib")
    if (PkgSkip("SWRESAMPLE")==0):LibName("SWRESAMPLE",GetThirdpartyDir() + "ffmpeg/lib/swresample.lib")
    if (PkgSkip("FCOLLADA")==0):
        LibName("FCOLLADA", GetThirdpartyDir() + "fcollada/lib/FCollada.lib")
        IncDirectory("FCOLLADA", GetThirdpartyDir() + "fcollada/include/FCollada")
    if (PkgSkip("ASSIMP")==0):
        LibName("ASSIMP", GetThirdpartyDir() + "assimp/lib/assimp.lib")
        if os.path.isfile(GetThirdpartyDir() + "assimp/lib/IrrXML.lib"):
            LibName("ASSIMP", GetThirdpartyDir() + "assimp/lib/IrrXML.lib")
        IncDirectory("ASSIMP", GetThirdpartyDir() + "assimp/include")
    if (PkgSkip("SQUISH")==0):
        if GetOptimize() <= 2:
            LibName("SQUISH",   GetThirdpartyDir() + "squish/lib/squishd.lib")
        else:
            LibName("SQUISH",   GetThirdpartyDir() + "squish/lib/squish.lib")
    if (PkgSkip("OPENAL")==0):
        LibName("OPENAL", GetThirdpartyDir() + "openal/lib/OpenAL32.lib")
        if not os.path.isfile(GetThirdpartyDir() + "openal/bin/OpenAL32.dll"):
            # Link OpenAL Soft statically.
            DefSymbol("OPENAL", "AL_LIBTYPE_STATIC")
    if (PkgSkip("ODE")==0):
        LibName("ODE",      GetThirdpartyDir() + "ode/lib/ode_single.lib")
        DefSymbol("ODE",    "dSINGLE", "")
    if (PkgSkip("FMODEX")==0):
        if (GetTargetArch() == 'x64'):
            LibName("FMODEX",   GetThirdpartyDir() + "fmodex/lib/fmodex64_vc.lib")
        else:
            LibName("FMODEX",   GetThirdpartyDir() + "fmodex/lib/fmodex_vc.lib")
    if (PkgSkip("VORBIS")==0):
        for lib in ('ogg', 'vorbis', 'vorbisfile'):
            path = GetThirdpartyDir() + "vorbis/lib/lib{0}_static.lib".format(lib)
            if not os.path.isfile(path):
                path = GetThirdpartyDir() + "vorbis/lib/{0}.lib".format(lib)
            LibName("VORBIS", path)
    if (PkgSkip("OPUS")==0):
        IncDirectory("OPUS", GetThirdpartyDir() + "opus/include/opus")
        for lib in ('ogg', 'opus', 'opusfile'):
            path = GetThirdpartyDir() + "opus/lib/lib{0}_static.lib".format(lib)
            if not os.path.isfile(path):
                path = GetThirdpartyDir() + "opus/lib/{0}.lib".format(lib)
            LibName("OPUS", path)

    if not PkgSkip("SPEEDTREE"):
        if GetTargetArch() == 'x64':
            libdir = SDK["SPEEDTREE"] + "/Lib/Windows/VC10.x64/"
            p64ext = '64'
        else:
            libdir = SDK["SPEEDTREE"] + "/Lib/Windows/VC10/"
            p64ext = ''

        debugext = ''
        if (GetOptimize() <= 2): debugext = "_d"
        libsuffix = "_v%s_VC100MT%s_Static%s.lib" % (
            SDK["SPEEDTREEVERSION"], p64ext, debugext)
        LibName("SPEEDTREE", "%sSpeedTreeCore%s" % (libdir, libsuffix))
        LibName("SPEEDTREE", "%sSpeedTreeForest%s" % (libdir, libsuffix))
        LibName("SPEEDTREE", "%sSpeedTree%sRenderer%s" % (libdir, SDK["SPEEDTREEAPI"], libsuffix))
        LibName("SPEEDTREE", "%sSpeedTreeRenderInterface%s" % (libdir, libsuffix))
        if (SDK["SPEEDTREEAPI"] == "OpenGL"):
            LibName("SPEEDTREE",  "%sglew32.lib" % (libdir))
            LibName("SPEEDTREE",  "glu32.lib")
        IncDirectory("SPEEDTREE", SDK["SPEEDTREE"] + "/Include")
    if (PkgSkip("BULLET")==0):
        suffix = '.lib'
        if GetTargetArch() == 'x64' and os.path.isfile(GetThirdpartyDir() + "bullet/lib/BulletCollision_x64.lib"):
            suffix = '_x64.lib'
        LibName("BULLET", GetThirdpartyDir() + "bullet/lib/LinearMath" + suffix)
        LibName("BULLET", GetThirdpartyDir() + "bullet/lib/BulletCollision" + suffix)
        LibName("BULLET", GetThirdpartyDir() + "bullet/lib/BulletDynamics" + suffix)
        LibName("BULLET", GetThirdpartyDir() + "bullet/lib/BulletSoftBody" + suffix)

if (COMPILER=="GCC"):
    if GetTarget() != "darwin":
        PkgDisable("COCOA")

    if GetTarget() == 'darwin':
        if OSX_ARCHS and 'x86_64' not in OSX_ARCHS and 'i386' not in OSX_ARCHS:
            # These support only these archs, so don't build them if we're not
            # targeting any of the supported archs.
            PkgDisable("FMODEX")
            PkgDisable("NVIDIACG")
        elif OSX_ARCHS and 'arm64' in OSX_ARCHS:
            # We must be using the 11.0 SDK or higher, so can't build FMOD Ex
            if not PkgSkip("FMODEX"):
                Warn("thirdparty package fmodex is not supported when targeting arm64, excluding from build")
            PkgDisable("FMODEX")
        elif not os.path.isfile(SDK.get("MACOSX", "") + '/usr/lib/libstdc++.6.0.9.tbd') and \
             not os.path.isfile(SDK.get("MACOSX", "") + '/usr/lib/libstdc++.6.0.9.dylib'):
            # Also, we can't target FMOD Ex on 10.14 and above
            if not PkgSkip("FMODEX"):
                Warn("thirdparty package fmodex requires one of MacOSX 10.9-10.13 SDK, excluding from build")
            PkgDisable("FMODEX")

    #if not PkgSkip("PYTHON"):
    #    IncDirectory("PYTHON", SDK["PYTHON"])
    if (GetHost() == "darwin"):
        if (PkgSkip("FREETYPE")==0 and not os.path.isdir(GetThirdpartyDir() + 'freetype')):
            IncDirectory("FREETYPE", "/usr/X11/include")
            IncDirectory("FREETYPE", "/usr/X11/include/freetype2")
            LibDirectory("FREETYPE", "/usr/X11/lib")

    if (GetHost() == "freebsd"):
        IncDirectory("ALWAYS", "/usr/local/include")
        LibDirectory("ALWAYS", "/usr/local/lib")
        if (os.path.isdir("/usr/PCBSD")):
            IncDirectory("ALWAYS", "/usr/PCBSD/local/include")
            LibDirectory("ALWAYS", "/usr/PCBSD/local/lib")
        SmartPkgEnable("INOTIFY", "libinotify", ("inotify"), "sys/inotify.h")

    if GetTarget() != "windows":
        PkgDisable("DIRECTCAM")

    fcollada_libs = ("FColladaD", "FColladaSD", "FColladaS")
    # WARNING! The order of the ffmpeg libraries matters!
    ffmpeg_libs = ("libavformat", "libavcodec", "libavutil")
    assimp_libs = ("libassimp", "libassimpd")

    #         Name         pkg-config   libs, include(dir)s
    SmartPkgEnable("ARTOOLKIT", "",          ("AR"), "AR/ar.h")
    SmartPkgEnable("FCOLLADA",  "",          ChooseLib(fcollada_libs, "FCOLLADA"), ("FCollada", "FCollada/FCollada.h"))
    SmartPkgEnable("ASSIMP",    "assimp",    ChooseLib(assimp_libs, "ASSIMP"), "assimp/Importer.hpp")
    SmartPkgEnable("FFMPEG",    ffmpeg_libs, ffmpeg_libs, ("libavformat/avformat.h", "libavcodec/avcodec.h", "libavutil/avutil.h"))
    SmartPkgEnable("SWSCALE",   "libswscale", "libswscale", ("libswscale/swscale.h"), target_pkg = "FFMPEG", thirdparty_dir = "ffmpeg")
    SmartPkgEnable("SWRESAMPLE","libswresample", "libswresample", ("libswresample/swresample.h"), target_pkg = "FFMPEG", thirdparty_dir = "ffmpeg")
    SmartPkgEnable("FFTW",      "fftw3",     ("fftw3"), ("fftw.h"))
    SmartPkgEnable("FMODEX",    "",          ("fmodex"), ("fmodex", "fmodex/fmod.h"))
    SmartPkgEnable("NVIDIACG",  "",          ("Cg"), "Cg/cg.h", framework = "Cg")
    SmartPkgEnable("ODE",       "",          ("ode"), "ode/ode.h", tool = "ode-config")
    SmartPkgEnable("SQUISH",    "",          ("squish"), "squish.h")
    SmartPkgEnable("TIFF",      "libtiff-4", ("tiff"), "tiff.h")
    SmartPkgEnable("VRPN",      "",          ("vrpn", "quat"), ("vrpn", "quat.h", "vrpn/vrpn_Types.h"))
    SmartPkgEnable("OPUS",      "opusfile",  ("opusfile", "opus", "ogg"), ("ogg/ogg.h", "opus/opusfile.h", "opus"))
    SmartPkgEnable("JPEG",      "",          ("jpeg"), "jpeglib.h")
    SmartPkgEnable("MIMALLOC",  "",          ("mimalloc"), "mimalloc.h")

    if GetTarget() != 'emscripten':
        # Most of these are provided by emscripten or via emscripten-ports.
        SmartPkgEnable("OPENAL",   "openal",    ("openal"), "AL/al.h", framework = "OpenAL")
        SmartPkgEnable("EIGEN",    "eigen3",    (), ("Eigen/Dense",), target_pkg = 'ALWAYS')
        SmartPkgEnable("VORBIS",   "vorbisfile",("vorbisfile", "vorbis", "ogg"), ("ogg/ogg.h", "vorbis/vorbisfile.h"))
        SmartPkgEnable("BULLET",   "bullet", ("BulletSoftBody", "BulletDynamics", "BulletCollision", "LinearMath"), ("bullet", "bullet/btBulletDynamicsCommon.h"))
        SmartPkgEnable("FREETYPE", "freetype2", ("freetype"), ("freetype2", "freetype2/freetype/freetype.h"))
        SmartPkgEnable("HARFBUZZ", "harfbuzz",  ("harfbuzz"), ("harfbuzz", "harfbuzz/hb-ft.h"))
        SmartPkgEnable("PNG",      "libpng",    ("png"), "png.h", tool = "libpng-config")
        SmartPkgEnable("GL",       "gl",        ("GL"), ("GL/gl.h"), framework = "OpenGL")
        SmartPkgEnable("GLES",     "glesv1_cm", ("GLESv1_CM"), ("GLES/gl.h"), framework = "OpenGLES")
        SmartPkgEnable("GLES2",    "glesv2",    ("GLESv2"), ("GLES2/gl2.h")) #framework = "OpenGLES"?
        SmartPkgEnable("EGL",      "egl",       ("EGL"), ("EGL/egl.h"))

        # Copy freetype libraries to be specified after harfbuzz libraries as well,
        # because there's a circular dependency between the two libraries.
        if not PkgSkip("FREETYPE") and not PkgSkip("HARFBUZZ"):
            for (opt, name) in LIBNAMES:
                if opt == "FREETYPE":
                    LibName("HARFBUZZ", name)
    else:
        PkgDisable("EIGEN")
        PkgDisable("X11")
        PkgDisable("GL")
        PkgDisable("GLES")
        PkgDisable("TINYDISPLAY")
        for pkg, empkg in {
            'VORBIS': 'VORBIS',
            'BULLET': 'BULLET',
            'ZLIB': 'ZLIB',
            'FREETYPE': 'FREETYPE',
            'HARFBUZZ': 'HARFBUZZ',
            'PNG': 'LIBPNG',
        }.items():
            if not PkgSkip(pkg):
                LinkFlag(pkg, '-s USE_' + empkg + '=1')
                CompileFlag(pkg, '-s USE_' + empkg + '=1')

    if not PkgSkip("FFMPEG"):
        if GetTarget() == "darwin":
            LibName("FFMPEG", "-framework VideoDecodeAcceleration")
        elif os.path.isfile(GetThirdpartyDir() + "ffmpeg/lib/libavcodec.a"):
            # Needed when linking ffmpeg statically on Linux.
            LibName("FFMPEG", "-Wl,-Bsymbolic")
            # Don't export ffmpeg symbols from libp3ffmpeg when linking statically.
            if GetTarget() != "emscripten":
                for ffmpeg_lib in ffmpeg_libs:
                    LibName("FFMPEG", "-Wl,--exclude-libs,%s.a" % (ffmpeg_lib))

    if not PkgSkip("OPENEXR"):
        # OpenEXR libraries have different names depending on the version.
        openexr_libdir = os.path.join(GetThirdpartyDir(), "openexr", "lib")
        openexr_incs = ("OpenEXR", "Imath", "OpenEXR/ImfOutputFile.h")
        if os.path.isfile(os.path.join(openexr_libdir, "libOpenEXR-3_1.a")):
            SmartPkgEnable("OPENEXR", "", ("OpenEXR-3_1", "IlmThread-3_1", "Imath-3_1", "Iex-3_1"), openexr_incs)
        if os.path.isfile(os.path.join(openexr_libdir, "libOpenEXR-3_0.a")):
            SmartPkgEnable("OPENEXR", "", ("OpenEXR-3_0", "IlmThread-3_0", "Imath-3_0", "Iex-3_0"), openexr_incs)
        elif os.path.isfile(os.path.join(openexr_libdir, "libOpenEXR.a")):
            SmartPkgEnable("OPENEXR", "", ("OpenEXR", "IlmThread", "Imath", "Iex"), openexr_incs)
        elif os.path.isfile(os.path.join(openexr_libdir, "libIlmImf.a")):
            SmartPkgEnable("OPENEXR", "", ("IlmImf", "Imath", "Half", "Iex", "IexMath", "IlmThread"), openexr_incs)
        else:
            # Find it in the system, preferably using pkg-config, otherwise
            # using the OpenEXR 3 naming scheme.
            SmartPkgEnable("OPENEXR", "OpenEXR", ("OpenEXR", "IlmThread", "Imath", "Iex"), openexr_incs)

    if GetTarget() not in ("darwin", "emscripten"):
        for fcollada_lib in fcollada_libs:
            LibName("FCOLLADA", "-Wl,--exclude-libs,lib%s.a" % (fcollada_lib))

        if not PkgSkip("SWSCALE"):
            LibName("SWSCALE", "-Wl,--exclude-libs,libswscale.a")

        if not PkgSkip("SWRESAMPLE"):
            LibName("SWRESAMPLE", "-Wl,--exclude-libs,libswresample.a")

        if not PkgSkip("JPEG"):
            LibName("JPEG", "-Wl,--exclude-libs,libjpeg.a")

        if not PkgSkip("TIFF"):
            LibName("TIFF", "-Wl,--exclude-libs,libtiff.a")

        if not PkgSkip("PNG"):
            LibName("PNG", "-Wl,--exclude-libs,libpng.a")
            LibName("PNG", "-Wl,--exclude-libs,libpng16.a")

        if not PkgSkip("SQUISH"):
            LibName("SQUISH", "-Wl,--exclude-libs,libsquish.a")

        if not PkgSkip("OPENEXR"):
            LibName("OPENEXR", "-Wl,--exclude-libs,libHalf.a")
            LibName("OPENEXR", "-Wl,--exclude-libs,libIex.a")
            LibName("OPENEXR", "-Wl,--exclude-libs,libIexMath.a")
            LibName("OPENEXR", "-Wl,--exclude-libs,libIlmImf.a")
            LibName("OPENEXR", "-Wl,--exclude-libs,libIlmImfUtil.a")
            LibName("OPENEXR", "-Wl,--exclude-libs,libIlmThread.a")
            LibName("OPENEXR", "-Wl,--exclude-libs,libImath.a")
            LibName("OPENEXR", "-Wl,--exclude-libs,libOpenEXR.a")
            LibName("OPENEXR", "-Wl,--exclude-libs,libOpenEXRCore.a")
            LibName("OPENEXR", "-Wl,--exclude-libs,libOpenEXRUtil.a")

        if not PkgSkip("VORBIS"):
            LibName("VORBIS", "-Wl,--exclude-libs,libogg.a")
            LibName("VORBIS", "-Wl,--exclude-libs,libvorbis.a")
            LibName("VORBIS", "-Wl,--exclude-libs,libvorbisenc.a")
            LibName("VORBIS", "-Wl,--exclude-libs,libvorbisfile.a")

        if not PkgSkip("OPUS"):
            LibName("OPUS", "-Wl,--exclude-libs,libogg.a")
            LibName("OPUS", "-Wl,--exclude-libs,libopus.a")
            LibName("OPUS", "-Wl,--exclude-libs,libopusfile.a")

        if not PkgSkip("VRPN"):
            LibName("VRPN", "-Wl,--exclude-libs,libvrpn.a")
            LibName("VRPN", "-Wl,--exclude-libs,libquat.a")

        if not PkgSkip("ARTOOLKIT"):
            LibName("ARTOOLKIT", "-Wl,--exclude-libs,libAR.a")
            LibName("ARTOOLKIT", "-Wl,--exclude-libs,libARMulti.a")

        if not PkgSkip("HARFBUZZ"):
            LibName("HARFBUZZ", "-Wl,--exclude-libs,libharfbuzz.a")

        if not PkgSkip("MIMALLOC"):
            LibName("MIMALLOC", "-Wl,--exclude-libs,libmimalloc.a")

    if PkgSkip("FFMPEG") or GetTarget() == "darwin":
        cv_lib = ChooseLib(("opencv_core", "cv"), "OPENCV")
        if cv_lib == "opencv_core":
            OPENCV_VER_23 = True
            SmartPkgEnable("OPENCV", "opencv",   ("opencv_core", "opencv_highgui"), ("opencv2/core/core.hpp"))
        else:
            SmartPkgEnable("OPENCV", "opencv",   ("cv", "highgui", "cvaux", "ml", "cxcore"),
                           ("opencv", "opencv/cv.h", "opencv/cxcore.h", "opencv/highgui.h"))
    else:
        PkgDisable("OPENCV")

    if not PkgSkip("OPENAL"):
        if GetTarget() == "darwin":
            LibName("OPENAL", "-framework AudioUnit")
            LibName("OPENAL", "-framework AudioToolbox")
            LibName("OPENAL", "-framework CoreAudio")
        elif GetTarget() != "emscripten":
            LibName("OPENAL", "-Wl,--exclude-libs,libopenal.a")

    if not PkgSkip("ASSIMP") and \
        os.path.isfile(GetThirdpartyDir() + "assimp/lib/libassimp.a"):
        # Also pick up IrrXML, which is needed when linking statically.
        irrxml = GetThirdpartyDir() + "assimp/lib/libIrrXML.a"
        if os.path.isfile(irrxml):
            LibName("ASSIMP", irrxml)

            if GetTarget() not in ("darwin", "emscripten"):
                LibName("ASSIMP", "-Wl,--exclude-libs,libassimp.a")
                LibName("ASSIMP", "-Wl,--exclude-libs,libIrrXML.a")

    if not PkgSkip("PYTHON"):
        python_lib = SDK["PYTHONVERSION"]
        SmartPkgEnable("PYTHON", "", python_lib, (SDK["PYTHONVERSION"], SDK["PYTHONVERSION"] + "/Python.h"))

        if not PkgSkip("PYTHON") and GetTarget() == "emscripten":
            # Python may have been compiled with these requirements.
            # Is there a cleaner way to check this?
            LinkFlag("PYTHON", "-s USE_BZIP2=1 -s USE_SQLITE3=1")
            if PkgHasCustomLocation("PYTHON"):
                python_libdir = FindLibDirectory("PYTHON")
            else:
                python_libdir = GetThirdpartyDir() + "python/lib"

            for lib in "libmpdec.a", "libexpat.a", "libHacl_Hash_SHA2.a":
                if os.path.isfile(python_libdir + "/" + lib):
                    LibName("PYTHON", python_libdir + "/" + lib)

        if GetTarget() == "linux":
            LibName("PYTHON", "-lutil")
            LibName("PYTHON", "-lrt")

    SmartPkgEnable("OPENSSL",   "openssl",   ("ssl", "crypto"), ("openssl/ssl.h", "openssl/crypto.h"))
    SmartPkgEnable("GTK3",      "gtk+-3.0")
    if GetTarget() != 'emscripten':
       SmartPkgEnable("ZLIB",      "zlib",      ("z"), "zlib.h")

    if not PkgSkip("OPENSSL") and GetTarget() not in ("darwin", "emscripten"):
        LibName("OPENSSL", "-Wl,--exclude-libs,libssl.a")
        LibName("OPENSSL", "-Wl,--exclude-libs,libcrypto.a")

    if GetTarget() not in ('darwin', 'emscripten'):
        # CgGL is covered by the Cg framework, and we don't need X11 components on OSX
        if not PkgSkip("NVIDIACG"):
            SmartPkgEnable("CGGL", "", ("CgGL"), "Cg/cgGL.h", thirdparty_dir = "nvidiacg")
        if GetTarget() != "android":
            SmartPkgEnable("X11", "x11", "X11", ("X11", "X11/Xlib.h", "X11/XKBlib.h"))
        else:
            PkgDisable("X11")

    if GetHost() != "darwin":
        # Workaround for an issue where pkg-config does not include this path
        if GetTargetArch() in ("x86_64", "amd64"):
            if not PkgSkip("X11"):
                if (os.path.isdir("/usr/X11R6/lib64")):
                    LibDirectory("ALWAYS", "/usr/X11R6/lib64")
                else:
                    LibDirectory("ALWAYS", "/usr/X11R6/lib")
        elif not PkgSkip("X11"):
            LibDirectory("ALWAYS", "/usr/X11R6/lib")

    if GetTarget() == 'darwin':
        LibName("ALWAYS", "-framework AppKit")
        LibName("IOKIT", "-framework IOKit")
        LibName("QUARTZ", "-framework Quartz")
        LibName("AGL", "-framework AGL")
        LibName("CARBON", "-framework Carbon")
        LibName("COCOA", "-framework Cocoa")
        # Fix for a bug in OSX Leopard:
        LibName("GL", "-dylib_file /System/Library/Frameworks/OpenGL.framework/Versions/A/Libraries/libGL.dylib:/System/Library/Frameworks/OpenGL.framework/Versions/A/Libraries/libGL.dylib")
        # When using pre-11.0 SDKs, for PStats
        if os.path.basename(SDK["MACOSX"]).startswith("MacOSX10."):
            LibName("COCOA", "-Wl,-U,_OBJC_CLASS_$_NSTrackingSeparatorToolbarItem")

        # Temporary exceptions to removal of this flag
        if not PkgSkip("FFMPEG"):
            LibName("FFMPEG", "-undefined dynamic_lookup")
        if not PkgSkip("ASSIMP"):
            LibName("ASSIMP", "-undefined dynamic_lookup")
        if not PkgSkip("VRPN"):
            LibName("VRPN", "-undefined dynamic_lookup")

    if GetTarget() == 'android':
        LibName("ALWAYS", '-llog')
        LibName("ANDROID", '-landroid')
        LibName("JNIGRAPHICS", '-ljnigraphics')
        LibName("OPENSLES", '-lOpenSLES')

DefSymbol("WITHINPANDA", "WITHIN_PANDA", "1")
if GetLinkAllStatic() or GetTarget() == 'emscripten':
    DefSymbol("ALWAYS", "LINK_ALL_STATIC")
if GetTarget() == 'android':
    DefSymbol("ALWAYS", "ANDROID")

if not PkgSkip("EIGEN"):
    if GetOptimize() >= 3:
        if COMPILER == "MSVC":
            # Squeeze out a bit more performance on MSVC builds...
            # Only do this if EIGEN_NO_DEBUG is also set, otherwise it
            # will turn them into runtime assertions.
            DefSymbol("ALWAYS", "EIGEN_NO_STATIC_ASSERT")

if not PkgSkip("EGL"):
    DefSymbol('EGL', 'HAVE_EGL', '')
    if PkgSkip("X11"):
        DefSymbol('EGL', 'EGL_NO_X11', '')

if not PkgSkip("X11"):
    DefSymbol('X11', 'USE_X11', '')

########################################################################
##
## Give a Status Report on Command-Line Options
##
########################################################################

def printStatus(header,warnings):
    if GetVerbose():
        print("")
        print("-------------------------------------------------------------------")
        print(header)
        tkeep = ""
        tomit = ""
        for x in PkgListGet():
            if PkgSkip(x):
                tomit = tomit + x + " "
            else:
                tkeep = tkeep + x + " "

        print("Makepanda: Compiler: %s" % (COMPILER))
        print("Makepanda: Optimize: %d" % (GetOptimize()))
        print("Makepanda: Keep Pkg: %s" % (tkeep))
        print("Makepanda: Omit Pkg: %s" % (tomit))

        if GENMAN:
            print("Makepanda: Generate API reference manual")
        else:
            print("Makepanda: Don't generate API reference manual")

        if GetHost() == "windows":
            if INSTALLER:
                print("Makepanda: Build installer, using %s" % (COMPRESSOR))
            else:
                print("Makepanda: Don't build installer")

        print("Makepanda: Version ID: %s" % (VERSION))
        for x in warnings:
            print("Makepanda: %s" % (x))
        print("-------------------------------------------------------------------")
        print("")
        sys.stdout.flush()

########################################################################
##
## BracketNameWithQuotes
##
########################################################################

def BracketNameWithQuotes(name):
    # Workaround for OSX bug - compiler doesn't like those flags quoted.
    if (name.startswith("-framework")): return name
    if (name.startswith("-dylib_file")): return name
    if (name.startswith("-undefined ")): return name

    # Don't add quotes when it's not necessary.
    if " " not in name: return name

    # Account for quoted name (leave as is) but quote everything else (e.g., to protect spaces within paths from improper parsing)
    if (name.startswith('"') and name.endswith('"')): return name
    else: return '"' + name + '"'

########################################################################
##
## CompileCxx
##
########################################################################

def CompileCxx(obj,src,opts):
    ipath = GetListOption(opts, "DIR:")
    optlevel = GetOptimizeOption(opts)
    if (COMPILER=="MSVC"):
        if not BOOUSEINTELCOMPILER:
            cmd = "cl "
            if GetTargetArch() == 'x64':
                cmd += "/favor:blend "
            cmd += "/wd4996 "

            # Set the minimum version to Windows Vista.
            cmd += "/DWINVER=0x600 "

            cmd += "/Fo" + obj + " /nologo /c"
            if GetTargetArch() == 'x86':
                # x86 (32 bit) MSVC 2015+ defaults to /arch:SSE2
                if not PkgSkip("SSE2") or 'SSE2' in opts:   # x86 with SSE2
                    cmd += " /arch:SSE2"    # let's still be explicit and pass in /arch:SSE2
                else:                                       # x86 without SSE2
                    cmd += " /arch:IA32"
            for x in ipath: cmd += " /I" + x
            for (opt,dir) in INCDIRECTORIES:
                if (opt=="ALWAYS") or (opt in opts): cmd += " /I" + BracketNameWithQuotes(dir)
            for (opt,var,val) in DEFSYMBOLS:
                if (opt=="ALWAYS") or (opt in opts): cmd += " /D" + var + "=" + val
            if (opts.count('MSFORSCOPE')): cmd += ' /Zc:forScope-'

            if (optlevel==1): cmd += " /MDd /Zi /RTCs /GS"
            if (optlevel==2): cmd += " /MDd /Zi"
            if (optlevel==3): cmd += " /MD /Zi /GS- /O2 /fp:fast"
            if (optlevel==4):
                cmd += " /MD /Zi /GS- /O2 /fp:fast /DFORCE_INLINING /DNDEBUG /GL"
                cmd += " /Zp16"      # jean-claude add /Zp16 insures correct static alignment for SSEx

            cmd += " /Fd" + os.path.splitext(obj)[0] + ".pdb"

            building = GetValueOption(opts, "BUILDING:")
            if (building):
                cmd += " /DBUILDING_" + building

            if ("BIGOBJ" in opts) or GetTargetArch() == 'x64' or not PkgSkip("EIGEN"):
                cmd += " /bigobj"

            cmd += " /Zm300"
            if 'EXCEPTIONS' in opts:
                cmd += " /EHsc"
            else:
                cmd += " /D_HAS_EXCEPTIONS=0"

            if 'RTTI' not in opts:
                cmd += " /GR-"

            cmd += " /W3 " + BracketNameWithQuotes(src)
            oscmd(cmd)
        else:
            cmd = "icl "
            if GetTargetArch() == 'x64':
                cmd += "/favor:blend "
            cmd += "/wd4996 /wd4267 /wd4101 "
            cmd += "/DWINVER=0x600 "
            cmd += "/Fo" + obj + " /c"
            for x in ipath: cmd += " /I" + x
            for (opt,dir) in INCDIRECTORIES:
                if (opt=="ALWAYS") or (opt in opts): cmd += " /I" + BracketNameWithQuotes(dir)
            for (opt,var,val) in DEFSYMBOLS:
                if (opt=="ALWAYS") or (opt in opts): cmd += " /D" + var + "=" + val
            if (opts.count('MSFORSCOPE')):  cmd += ' /Zc:forScope-'

            if (optlevel==1): cmd += " /MDd /Zi /RTCs /GS"
            if (optlevel==2): cmd += " /MDd /Zi /arch:SSE3"
            # core changes from jean-claude (dec 2011)
            # ----------------------------------------
            # performance will be seeked at level 3 & 4
            # -----------------------------------------
            if (optlevel==3):
                cmd += " /MD /Zi /O2 /Oi /Ot /arch:SSE3"
                cmd += " /Ob0"
                cmd += " /Qipo-"                            # beware of IPO !!!
            ##      Lesson learned: Don't use /GL flag -> end result is MESSY
            ## ----------------------------------------------------------------
            if (optlevel==4):
                cmd += " /MD /Zi /O3 /Oi /Ot /Ob0 /Yc /DNDEBUG"  # /Ob0 a ete rajoute en cours de route a 47%
                cmd += " /Qipo"                              # optimization multi file

            # for 3 & 4 optimization levels
            # -----------------------------
            if (optlevel>=3):
                cmd += " /fp:fast=2"
                cmd += " /Qftz"
                cmd += " /Qfp-speculation:fast"
                cmd += " /Qopt-matmul"                        # needs /O2 or /O3
                cmd += " /Qprec-div-"
                cmd += " /Qsimd"

                cmd += " /QxHost"                            # compile for target host; Compiling for distribs should probably strictly enforce /arch:..
                cmd += " /Quse-intel-optimized-headers"        # use intel optimized headers
                cmd += " /Qparallel"                        # enable parallelization
                cmd += " /Qvc10"                                # for Microsoft Visual C++ 2010

            ## PCH files coexistence: the /Qpchi option causes the Intel C++ Compiler to name its
            ## PCH files with a .pchi filename suffix and reduce build time.
            ## The /Qpchi option is on by default but interferes with Microsoft libs; so use /Qpchi- to turn it off.
            ## I need to have a deeper look at this since the compile time is quite influenced by this setting !!!
            cmd += " /Qpchi-"                                 # keep it this way!

            ## Inlining seems to be an issue here ! (the linker doesn't find necessary info later on)
            ## ------------------------------------
            ## so don't use cmd += " /DFORCE_INLINING"        (need to check why with Panda developpers!)
            ## Inline expansion  /Ob1    :    Allow functions marked inline to be inlined.
            ## Inline any        /Ob2    :    Inline functions deemed appropriate by compiler.

            ## Ctor displacement /vd0    :    Disable constructor displacement.
            ## Choose this option only if no class constructors or destructors call virtual functions.
            ## Use /vd1 (default) to enable. Alternate: #pragma vtordisp

            ## Best case ptrs    /vmb    :    Use best case "pointer to class member" representation.
            ## Use this option if you always define a class before you declare a pointer to a member of the class.
            ## The compiler will issue an error if it encounters a pointer declaration before the class is defined.
            ## Alternate: #pragma pointers_to_members

            cmd += " /Fd" + os.path.splitext(obj)[0] + ".pdb"
            building = GetValueOption(opts, "BUILDING:")
            if (building): cmd += " /DBUILDING_" + building
            if ("BIGOBJ" in opts) or GetTargetArch() == 'x64':
                cmd += " /bigobj"

            # level of warnings and optimization reports
            if GetVerbose():
                cmd += " /W3 " # or /W4 or /Wall
                cmd += " /Qopt-report:2 /Qopt-report-phase:hlo /Qopt-report-phase:hpo"    # some optimization reports
            else:
                cmd += " /W1 "
            cmd += " /EHa /Zm300"
            cmd += " " + BracketNameWithQuotes(src)

            oscmd(cmd)

    if (COMPILER=="GCC"):
        if (src.endswith(".c")): cmd = GetCC() +' -fPIC -c -o ' + obj
        else:                    cmd = GetCXX()+' -std=gnu++14 -ftemplate-depth-70 -fPIC -c -o ' + obj
        for (opt, dir) in INCDIRECTORIES:
            if (opt=="ALWAYS") or (opt in opts): cmd += ' -I' + BracketNameWithQuotes(dir)
        for (opt, dir) in FRAMEWORKDIRECTORIES:
            if (opt=="ALWAYS") or (opt in opts): cmd += ' -F' + BracketNameWithQuotes(dir)
        for (opt,var,val) in DEFSYMBOLS:
            if (opt=="ALWAYS") or (opt in opts): cmd += ' -D' + var + '=' + val
        for (opt,flag) in COMPILEFLAGS:
            if (opt=="ALWAYS") or (opt in opts): cmd += ' ' + flag
        for x in ipath: cmd += ' -I' + x

        if not GetLinkAllStatic() and 'NOHIDDEN' not in opts:
            cmd += ' -fvisibility=hidden'

        # Mac-specific flags.
        if GetTarget() == "darwin":
            cmd += " -Wno-deprecated-declarations"
            if SDK.get("MACOSX"):
                cmd += " -isysroot " + SDK["MACOSX"]

            if tuple(OSX_ARCHS) == ('arm64',):
                cmd += " -mmacosx-version-min=11.0"
            else:
                cmd += " -mmacosx-version-min=10.9"

            # Use libc++ to enable C++11 features.
            cmd += " -stdlib=libc++"

            for arch in OSX_ARCHS:
                if 'NOARCH:' + arch.upper() not in opts:
                    cmd += " -arch %s" % arch

        elif 'clang' not in GetCXX().split('/')[-1] and GetCXX() != 'em++':
            # Enable interprocedural optimizations in GCC.
            cmd += " -fno-semantic-interposition"

        if "SYSROOT" in SDK:
            if GetTarget() != "android":
                cmd += ' --sysroot=%s' % (SDK["SYSROOT"])
            cmd += ' -no-canonical-prefixes'

        # Android-specific flags.
        arch = GetTargetArch()

        if GetTarget() == "android":
            # Most of the specific optimization flags here were
            # just copied from the default Android Makefiles.
            if "ANDROID_GCC_TOOLCHAIN" in SDK:
                cmd += ' -gcc-toolchain ' + SDK["ANDROID_GCC_TOOLCHAIN"].replace('\\', '/')
            cmd += ' -ffunction-sections -funwind-tables'
            cmd += ' -target ' + SDK["ANDROID_TRIPLE"]
            if arch in ('armv7a', 'arm'):
                cmd += ' -march=armv7-a -mfloat-abi=softfp -mfpu=vfpv3-d16'
            #elif arch == 'arm':
            #    cmd += ' -march=armv5te -mtune=xscale -msoft-float'
            elif arch == 'mips':
                cmd += ' -mips32'
            elif arch == 'mips64':
                cmd += ' -fintegrated-as'
            elif arch == 'x86':
                cmd += ' -march=i686 -mssse3 -mfpmath=sse -m32'
                cmd += ' -mstackrealign'
            elif arch == 'x86_64':
                cmd += ' -march=x86-64 -msse4.2 -mpopcnt -m64'

            cmd += " -Wa,--noexecstack"

            # Do we want thumb or arm instructions?
            if arch != 'arm64' and arch.startswith('arm'):
                if optlevel >= 3:
                    cmd += ' -mthumb'
                else:
                    cmd += ' -marm'

            # Enable SIMD instructions if requested
            if arch != 'arm64' and arch.startswith('arm') and PkgSkip("NEON") == 0:
                cmd += ' -mfpu=neon'

        elif GetTarget() == 'emscripten':
            if GetOptimize() <= 1:
                cmd += " -s ASSERTIONS=2"
            elif GetOptimize() <= 2:
                cmd += " -s ASSERTIONS=1"

        else:
            cmd += " -pthread"

        if not src.endswith(".c"):
            # We don't use exceptions for most modules.
            if 'EXCEPTIONS' in opts:
                cmd += " -fexceptions"
            else:
                cmd += " -fno-exceptions"
                if GetTarget() == 'emscripten':
                    cmd += " -s DISABLE_EXCEPTION_CATCHING=1"

                if src.endswith(".mm"):
                    # Work around Apple compiler bug.
                    cmd += " -U__EXCEPTIONS"

            target = GetTarget()
            if 'RTTI' not in opts and target != "darwin":
                # We always disable RTTI on Android for memory usage reasons.
                if optlevel >= 4 or target == "android":
                    cmd += " -fno-rtti"

        if ('SSE2' in opts or not PkgSkip("SSE2")) and not arch.startswith("arm") and arch != 'aarch64':
            if GetTarget() != "emscripten":
                cmd += " -msse2"

        # Needed by both Python, Panda, Eigen, all of which break aliasing rules.
        cmd += " -fno-strict-aliasing"

        # Certain clang versions crash when passing these math flags while
        # compiling Objective-C++ code
        if not src.endswith(".m") and not src.endswith(".mm"):
            if optlevel >= 3:
                cmd += " -ffast-math -fno-stack-protector"
            if optlevel == 3:
                # Fast math is nice, but we'd like to see NaN in dev builds.
                cmd += " -fno-finite-math-only"

            # Make sure this is off to avoid GCC/Eigen bug (see GitHub #228)
            if GetTarget() != "emscripten":
                cmd += " -fno-unsafe-math-optimizations"

        if (optlevel==1):
            if GetTarget() == "emscripten":
                cmd += " -g -D_DEBUG"
            else:
                cmd += " -ggdb -D_DEBUG"
        if (optlevel==2): cmd += " -O1 -D_DEBUG"
        if (optlevel==3): cmd += " -O2"
        if (optlevel==4): cmd += " -O3 -DNDEBUG"

        # Enable more warnings.
        cmd += " -Wall -Wno-unused-function -Werror=return-type"

        # Ignore unused variables in NDEBUG builds, often used in asserts.
        if optlevel == 4:
            cmd += " -Wno-unused-variable"

        if src.endswith(".c"):
            cmd += ' ' + CFLAGS
        else:
            cmd += ' ' + CXXFLAGS
        cmd = cmd.rstrip()

        building = GetValueOption(opts, "BUILDING:")
        if (building): cmd += " -DBUILDING_" + building
        cmd += ' ' + BracketNameWithQuotes(src)
        oscmd(cmd)

########################################################################
##
## CompileBison
##
########################################################################

def CompileBison(wobj, wsrc, opts):
    ifile = os.path.basename(wsrc)
    wdsth = GetOutputDir() + "/include/" + ifile[:-4] + ".h"
    wdsth2 = GetOutputDir() + "/tmp/" + ifile + ".h"
    wdstc = GetOutputDir() + "/tmp/" + ifile + ".cxx"
    pre = GetValueOption(opts, "BISONPREFIX_")
    bison = GetBison()
    if bison is None:
        # We don't have bison.  See if there is a prebuilt file.
        base, ext = os.path.splitext(wsrc)
        if os.path.isfile(base + '.h.prebuilt') and \
           os.path.isfile(base + '.cxx.prebuilt'):
            CopyFile(wdstc, base + '.cxx.prebuilt')
            CopyFile(wdsth, base + '.h.prebuilt')
            CopyFile(wdsth2, base + '.h.prebuilt')
        else:
            exit('Could not find bison!')
    else:
        oscmd(bison + ' -y -d -o'+GetOutputDir()+'/tmp/'+ifile[:-4]+'.c -p '+pre+' '+wsrc)
        CopyFile(wdstc, GetOutputDir()+"/tmp/"+ifile[:-4]+".c")
        CopyFile(wdsth, GetOutputDir()+"/tmp/"+ifile[:-4]+".h")

    # Finally, compile the generated source file.
    CompileCxx(wobj, wdstc, opts + ["FLEX"])

########################################################################
##
## CompileFlex
##
########################################################################

def CompileFlex(wobj,wsrc,opts):
    ifile = os.path.basename(wsrc)
    wdst = GetOutputDir()+"/tmp/"+ifile+".cxx"
    pre = GetValueOption(opts, "BISONPREFIX_")
    dashi = opts.count("FLEXDASHI")
    flex = GetFlex()
    want_version = GetValueOption(opts, "FLEXVERSION:")
    if flex and want_version:
        # Is flex at the required version for this file?
        want_version = tuple(map(int, want_version.split('.')))
        have_version = GetFlexVersion()
        if want_version > have_version:
            Warn("Skipping flex %s for file %s, need at least %s" % (
                '.'.join(map(str, have_version)),
                ifile,
                '.'.join(map(str, want_version)),
            ))
            flex = None

    if flex is None:
        # We don't have flex.  See if there is a prebuilt file.
        base, ext = os.path.splitext(wsrc)
        if os.path.isfile(base + '.cxx.prebuilt'):
            CopyFile(wdst, base + '.cxx.prebuilt')
        else:
            exit('Could not find flex!')
    else:
        if (dashi):
            oscmd(flex + " -i -P" + pre + " -o"+wdst+" "+wsrc)
        else:
            oscmd(flex +    " -P" + pre + " -o"+wdst+" "+wsrc)

    # Finally, compile the generated source file.
    CompileCxx(wobj, wdst, opts + ["FLEX"])

########################################################################
##
## CompileIgate
##
########################################################################

def CompileIgate(woutd,wsrc,opts):
    outbase = os.path.basename(woutd)[:-3]
    woutc = GetOutputDir()+"/tmp/"+outbase+"_igate.cxx"
    srcdir = GetValueOption(opts, "SRCDIR:")
    module = GetValueOption(opts, "IMOD:")
    library = GetValueOption(opts, "ILIB:")
    ipath = GetListOption(opts, "DIR:")
    if (PkgSkip("PYTHON")):
        WriteFile(woutc, "")
        WriteFile(woutd, "")
        ConditionalWriteFile(woutd, "")
        return

    cmd = GetInterrogate()

    if GetVerbose():
        cmd += ' -v'

    cmd += ' -srcdir %s -I%s' % (srcdir, srcdir)
    cmd += ' -DCPPPARSER -D__STDC__=1 -D__cplusplus=201103L'
    if (COMPILER=="MSVC"):
        cmd += ' -D_WIN32'
        if GetTargetArch() == 'x64':
            cmd += ' -D_WIN64 -D_M_X64 -D_M_AMD64'
        else:
            cmd += ' -D_M_IX86'
        # NOTE: this 1600 value is the version number for VC2010.
        cmd += ' -D_MSC_VER=1600 -D"__declspec(param)=" -D__cdecl -D_near -D_far -D__near -D__far -D__stdcall'
    if (COMPILER=="GCC"):
        cmd += ' -D__attribute__\\(x\\)='
        target_arch = GetTargetArch()
        if target_arch in ("x86_64", "amd64"):
            cmd += ' -D_LP64'
        elif target_arch in ('aarch64', 'arm64'):
            cmd += ' -D_LP64 -D__LP64__ -D__aarch64__'
        else:
            cmd += ' -D__i386__'

        target = GetTarget()
        if target == 'darwin':
            cmd += ' -D__APPLE__'
        elif target == 'android':
            cmd += ' -D__ANDROID__'

    if GetTarget() == "emscripten":
        cmd += ' -D__EMSCRIPTEN__'

    optlevel = GetOptimizeOption(opts)
    if (optlevel==1): cmd += ' -D_DEBUG'
    if (optlevel==2): cmd += ' -D_DEBUG'
    if (optlevel==3): pass
    if (optlevel==4): cmd += ' -DNDEBUG'
    cmd += ' -oc ' + woutc + ' -od ' + woutd
    cmd += ' -fnames -string -refcount -assert -python-native'
    cmd += ' -S' + GetOutputDir() + '/include/parser-inc'

    # Add -I, -S and -D flags
    for x in ipath:
        cmd += ' -I' + BracketNameWithQuotes(x)
    for (opt,dir) in INCDIRECTORIES:
        if (opt=="ALWAYS") or (opt in opts):
            cmd += ' -S' + BracketNameWithQuotes(dir)
    for (opt,var,val) in DEFSYMBOLS:
        if (opt=="ALWAYS") or (opt in opts):
            cmd += ' -D' + var + '=' + val

    #building = GetValueOption(opts, "BUILDING:")
    #if (building): cmd += " -DBUILDING_"+building
    cmd += ' -module ' + module + ' -library ' + library
    for x in wsrc:
        if (x.startswith("/")):
            cmd += ' ' + BracketNameWithQuotes(x)
        else:
            cmd += ' ' + BracketNameWithQuotes(os.path.basename(x))
    oscmd(cmd)

########################################################################
##
## CompileImod
##
########################################################################

def CompileImod(wobj, wsrc, opts):
    module = GetValueOption(opts, "IMOD:")
    library = GetValueOption(opts, "ILIB:")
    woutc = os.path.splitext(wobj)[0] + ".cxx"

    if (PkgSkip("PYTHON")):
        WriteFile(woutc, "")
        CompileCxx(wobj, woutc, opts)
        return

    cmd = GetInterrogateModule()

    cmd += ' -oc ' + woutc + ' -module ' + module + ' -library ' + library + ' -python-native'
    importmod = GetValueOption(opts, "IMPORT:")
    if importmod:
        cmd += ' -import ' + importmod
    initfunc = GetValueOption(opts, "INIT:")
    if initfunc:
        cmd += ' -init ' + initfunc
    for x in wsrc: cmd += ' ' + BracketNameWithQuotes(x)
    oscmd(cmd)
    CompileCxx(wobj,woutc,opts)
    return

########################################################################
##
## CompileLib
##
########################################################################

def CompileLib(lib, obj, opts):
    if (COMPILER=="MSVC"):
        if not BOOUSEINTELCOMPILER:
            #Use MSVC Linker
            cmd = 'link /lib /nologo'
            if GetOptimizeOption(opts) == 4:
                cmd += " /LTCG"
            if HasTargetArch():
                cmd += " /MACHINE:" + GetTargetArch().upper()
            cmd += ' /OUT:' + BracketNameWithQuotes(lib)
            for x in obj:
                if not x.endswith('.lib'):
                    cmd += ' ' + BracketNameWithQuotes(x)
            oscmd(cmd)
        else:
            # Choose Intel linker; from Jean-Claude
            cmd = 'xilink /verbose:lib /lib '
            if HasTargetArch():
                cmd += " /MACHINE:" + GetTargetArch().upper()
            cmd += ' /OUT:' + BracketNameWithQuotes(lib)
            for x in obj: cmd += ' ' + BracketNameWithQuotes(x)
            cmd += ' /LIBPATH:"C:\\Program Files (x86)\\Intel\\Composer XE 2011 SP1\\ipp\\lib\\ia32"'
            cmd += ' /LIBPATH:"C:\\Program Files (x86)\\Intel\\Composer XE 2011 SP1\\TBB\\Lib\\ia32\\vc10"'
            cmd += ' /LIBPATH:"C:\\Program Files (x86)\\Intel\\Composer XE 2011 SP1\\compiler\\lib\\ia32"'
            oscmd(cmd)

    if (COMPILER=="GCC"):
        if GetTarget() == 'darwin':
            cmd = 'libtool -static -o ' + BracketNameWithQuotes(lib)
        else:
            cmd = GetAR() + ' cru ' + BracketNameWithQuotes(lib)
        for x in obj:
            if GetLinkAllStatic() and x.endswith('.a'):
                continue
            cmd += ' ' + BracketNameWithQuotes(x)
        oscmd(cmd)

        oscmd(GetRanlib() + ' ' + BracketNameWithQuotes(lib))

########################################################################
##
## CompileLink
##
########################################################################

def CompileLink(dll, obj, opts):
    if (COMPILER=="MSVC"):
        if not BOOUSEINTELCOMPILER:
            cmd = "link /nologo "
            if HasTargetArch():
                cmd += " /MACHINE:" + GetTargetArch().upper()
            if ("MFC" not in opts):
                cmd += " /NOD:MFC90.LIB /NOD:MFC80.LIB /NOD:LIBCMT"
            cmd += " /NOD:LIBCI.LIB /DEBUG"
            cmd += " /nod:libc /nod:libcmtd /nod:atlthunk /nod:atls /nod:atlsd"
            if (GetOrigExt(dll) != ".exe"): cmd += " /DLL"
            optlevel = GetOptimizeOption(opts)
            if (optlevel==1): cmd += " /MAP /MAPINFO:EXPORTS /NOD:MSVCRT.LIB /NOD:MSVCPRT.LIB /NOD:MSVCIRT.LIB"
            if (optlevel==2): cmd += " /MAP:NUL /NOD:MSVCRT.LIB /NOD:MSVCPRT.LIB /NOD:MSVCIRT.LIB"
            if (optlevel==3): cmd += " /MAP:NUL /NOD:MSVCRTD.LIB /NOD:MSVCPRTD.LIB /NOD:MSVCIRTD.LIB"
            if (optlevel==4): cmd += " /MAP:NUL /LTCG /NOD:MSVCRTD.LIB /NOD:MSVCPRTD.LIB /NOD:MSVCIRTD.LIB"
            if ("MFC" in opts):
                if (optlevel<=2): cmd += " /NOD:MSVCRTD.LIB mfcs100d.lib MSVCRTD.lib"
                else: cmd += " /NOD:MSVCRT.LIB mfcs100.lib MSVCRT.lib"
            cmd += " /FIXED:NO /OPT:REF /STACK:4194304 /INCREMENTAL:NO "
            cmd += ' /OUT:' + BracketNameWithQuotes(dll)

            if not PkgSkip("PYTHON"):
                # If we're building without Python, don't pick it up implicitly.
                if "PYTHON" not in opts:
                    pythonv = SDK["PYTHONVERSION"].replace('.', '')
                    if optlevel <= 2:
                        cmd += ' /NOD:{}_d.lib'.format(pythonv)
                    else:
                        cmd += ' /NOD:{}.lib'.format(pythonv)

            # Set the subsystem.  Specify that we want to target Windows XP.
            subsystem = GetValueOption(opts, "SUBSYSTEM:") or "CONSOLE"
            cmd += " /SUBSYSTEM:" + subsystem
            if GetTargetArch() == 'x64':
                cmd += ",6.00"
            else:
                cmd += ",6.00"

            if dll.endswith(".dll") or dll.endswith(".pyd"):
                cmd += ' /IMPLIB:' + GetOutputDir() + '/lib/' + os.path.splitext(os.path.basename(dll))[0] + ".lib"

            for (opt, dir) in LIBDIRECTORIES:
                if (opt=="ALWAYS") or (opt in opts):
                    cmd += ' /LIBPATH:' + BracketNameWithQuotes(dir)

            for x in obj:
                if x.endswith(".dll") or x.endswith(".pyd"):
                    cmd += ' ' + GetOutputDir() + '/lib/' + os.path.splitext(os.path.basename(x))[0] + ".lib"
                elif x.endswith(".lib"):
                    dname = os.path.splitext(os.path.basename(x))[0] + ".dll"
                    if (GetOrigExt(x) != ".ilb" and os.path.exists(GetOutputDir()+"/bin/" + dname)):
                        exit("Error: in makepanda, specify "+dname+", not "+x)
                    cmd += ' ' + BracketNameWithQuotes(x)
                elif x.endswith(".def"):
                    cmd += ' /DEF:' + BracketNameWithQuotes(x)
                elif x.endswith(".dat"):
                    pass
                else:
                    cmd += ' ' + BracketNameWithQuotes(x)

            if (GetOrigExt(dll)==".exe" and "NOICON" not in opts):
                cmd += " " + GetOutputDir() + "/tmp/pandaIcon.res"

            for (opt, name) in LIBNAMES:
                if (opt=="ALWAYS") or (opt in opts):
                    cmd += " " + BracketNameWithQuotes(name)

            oscmd(cmd)
        else:
            cmd = "xilink"
            if GetVerbose(): cmd += " /verbose:lib"
            if HasTargetArch():
                cmd += " /MACHINE:" + GetTargetArch().upper()
            if ("MFC" not in opts):
                cmd += " /NOD:MFC90.LIB /NOD:MFC80.LIB /NOD:LIBCMT"
            cmd += " /NOD:LIBCI.LIB /DEBUG"
            cmd += " /nod:libc /nod:libcmtd /nod:atlthunk /nod:atls"
            cmd += ' /LIBPATH:"C:\\Program Files (x86)\\Intel\\Composer XE 2011 SP1\\ipp\\lib\\ia32"'
            cmd += ' /LIBPATH:"C:\\Program Files (x86)\\Intel\\Composer XE 2011 SP1\\TBB\\Lib\\ia32\\vc10"'
            cmd += ' /LIBPATH:"C:\\Program Files (x86)\\Intel\\Composer XE 2011 SP1\\compiler\\lib\\ia32"'
            if (GetOrigExt(dll) != ".exe"): cmd += " /DLL"
            optlevel = GetOptimizeOption(opts)
            if (optlevel==1): cmd += " /MAP /MAPINFO:EXPORTS /NOD:MSVCRT.LIB /NOD:MSVCPRT.LIB /NOD:MSVCIRT.LIB"
            if (optlevel==2): cmd += " /MAP:NUL /NOD:MSVCRT.LIB /NOD:MSVCPRT.LIB /NOD:MSVCIRT.LIB"
            if (optlevel==3): cmd += " /MAP:NUL /NOD:MSVCRTD.LIB /NOD:MSVCPRTD.LIB /NOD:MSVCIRTD.LIB"
            if (optlevel==4): cmd += " /MAP:NUL /LTCG /NOD:MSVCRTD.LIB /NOD:MSVCPRTD.LIB /NOD:MSVCIRTD.LIB"
            if ("MFC" in opts):
                if (optlevel<=2): cmd += " /NOD:MSVCRTD.LIB mfcs100d.lib MSVCRTD.lib"
                else: cmd += " /NOD:MSVCRT.LIB mfcs100.lib MSVCRT.lib"
            cmd += " /FIXED:NO /OPT:REF /STACK:4194304 /INCREMENTAL:NO "
            cmd += ' /OUT:' + BracketNameWithQuotes(dll)

            subsystem = GetValueOption(opts, "SUBSYSTEM:")
            if subsystem:
                cmd += " /SUBSYSTEM:" + subsystem

            if dll.endswith(".dll"):
                cmd += ' /IMPLIB:' + GetOutputDir() + '/lib/' + os.path.splitext(os.path.basename(dll))[0] + ".lib"

            for (opt, dir) in LIBDIRECTORIES:
                if (opt=="ALWAYS") or (opt in opts):
                    cmd += ' /LIBPATH:' + BracketNameWithQuotes(dir)

            for x in obj:
                if x.endswith(".dll") or x.endswith(".pyd"):
                    cmd += ' ' + GetOutputDir() + '/lib/' + os.path.splitext(os.path.basename(x))[0] + ".lib"
                elif x.endswith(".lib"):
                    dname = os.path.splitext(dll)[0]+".dll"
                    if (GetOrigExt(x) != ".ilb" and os.path.exists(GetOutputDir()+"/bin/" + os.path.splitext(os.path.basename(x))[0] + ".dll")):
                        exit("Error: in makepanda, specify "+dname+", not "+x)
                    cmd += ' ' + BracketNameWithQuotes(x)
                elif x.endswith(".def"):
                    cmd += ' /DEF:' + BracketNameWithQuotes(x)
                elif x.endswith(".dat"):
                    pass
                else:
                    cmd += ' ' + BracketNameWithQuotes(x)

            if (GetOrigExt(dll)==".exe" and "NOICON" not in opts):
                cmd += " " + GetOutputDir() + "/tmp/pandaIcon.res"

            for (opt, name) in LIBNAMES:
                if (opt=="ALWAYS") or (opt in opts):
                    cmd += " " + BracketNameWithQuotes(name)

            oscmd(cmd)

    if COMPILER == "GCC":
        cxx = GetCXX()
        if GetOrigExt(dll) == ".exe":
            cmd = cxx + ' -o ' + dll + ' -L' + GetOutputDir() + '/lib -L' + GetOutputDir() + '/tmp'
            if GetTarget() == "android":
                # Necessary to work around an issue with libandroid depending on vendor libraries
                cmd += ' -Wl,--allow-shlib-undefined'
        else:
            if (GetTarget() == "darwin"):
                cmd = cxx
                if GetOrigExt(dll) == ".pyd":
                    cmd += ' -bundle -undefined dynamic_lookup'
                elif "BUNDLE" in opts:
                    cmd += ' -bundle'
                else:
                    install_name = '@loader_path/../lib/' + os.path.basename(dll)
                    cmd += ' -dynamiclib -install_name ' + install_name
                    cmd += ' -compatibility_version ' + MAJOR_VERSION + ' -current_version ' + VERSION
                cmd += ' -o ' + dll + ' -L' + GetOutputDir() + '/lib -L' + GetOutputDir() + '/tmp'
            else:
                cmd = cxx + ' -shared'
                # Always set soname on Android to avoid a linker warning when loading the library.
                if GetTarget() == 'android' or ("MODULE" not in opts and GetTarget() != 'emscripten'):
                    cmd += " -Wl,-soname=" + os.path.basename(dll)
                cmd += ' -o ' + dll + ' -L' + GetOutputDir() + '/lib -L' + GetOutputDir() + '/tmp'

        if GetTarget() == 'emscripten' and GetOrigExt(dll) != ".exe":
            for x in obj:
                if GetOrigExt(x) not in (".dat", ".dll"):
                    cmd += ' ' + x
        else:
            for x in obj:
                if GetOrigExt(x) != ".dat":
                    cmd += ' ' + x

        if (GetOrigExt(dll) == ".exe" and GetTarget() == 'windows' and "NOICON" not in opts):
            cmd += " " + GetOutputDir() + "/tmp/pandaIcon.res"

        # macOS specific flags.
        if GetTarget() == 'darwin':
            cmd += " -headerpad_max_install_names"
            if SDK.get("MACOSX"):
                cmd += " -isysroot " + SDK["MACOSX"] + " -Wl,-syslibroot," + SDK["MACOSX"]

            if tuple(OSX_ARCHS) == ('arm64',):
                cmd += " -mmacosx-version-min=11.0"
            elif sys.version_info >= (3, 13) and 'PYTHON' in opts:
                cmd += " -mmacosx-version-min=10.13"
            else:
                cmd += " -mmacosx-version-min=10.9"

            # Use libc++ to enable C++11 features.
            cmd += " -stdlib=libc++"

            for arch in OSX_ARCHS:
                if 'NOARCH:' + arch.upper() not in opts:
                    cmd += " -arch %s" % arch

        elif GetTarget() == 'android':
            arch = GetTargetArch()
            if "ANDROID_GCC_TOOLCHAIN" in SDK:
                cmd += ' -gcc-toolchain ' + SDK["ANDROID_GCC_TOOLCHAIN"].replace('\\', '/')
            cmd += " -Wl,-z,noexecstack -Wl,-z,relro -Wl,-z,now"
            cmd += ' -target ' + SDK["ANDROID_TRIPLE"]
            if arch in ('armv7a', 'arm'):
                cmd += " -march=armv7-a -Wl,--fix-cortex-a8"
            elif arch == 'mips':
                cmd += ' -mips32'
            cmd += ' -lc -lm'

        elif GetTarget() == 'emscripten':
            cmd += " -s WARN_ON_UNDEFINED_SYMBOLS=1 -mbulk-memory"

            if GetOrigExt(dll) == ".exe":
                cmd += " -s EXIT_RUNTIME=1"

                if dll.endswith(".js") and "SUBSYSTEM:WINDOWS" not in opts:
                    cmd += " --pre-js dtool/src/dtoolutil/console_preamble.js"

        else:
            cmd += " -pthread"
            if "SYSROOT" in SDK:
                cmd += " --sysroot=%s -no-canonical-prefixes" % (SDK["SYSROOT"])

        if LDFLAGS != "":
            cmd += " " + LDFLAGS

        # Don't link libraries with Python, except on Android.
        if "PYTHON" in opts and GetOrigExt(dll) != ".exe" and GetTarget() != 'android':
            opts = opts[:]
            opts.remove("PYTHON")

        for (opt, dir) in LIBDIRECTORIES:
            if (opt=="ALWAYS") or (opt in opts):
                cmd += ' -L' + BracketNameWithQuotes(dir)
        for (opt, dir) in FRAMEWORKDIRECTORIES:
            if (opt=="ALWAYS") or (opt in opts):
                cmd += ' -F' + BracketNameWithQuotes(dir)
        if GetOrigExt(dll) == ".exe" or GetTarget() != 'emscripten':
            for (opt, name) in LIBNAMES:
                if (opt=="ALWAYS") or (opt in opts):
                    cmd += ' ' + BracketNameWithQuotes(name)
        for (opt, flag) in LINKFLAGS:
            if (opt=="ALWAYS") or (opt in opts):
                cmd += ' ' + flag

        if GetTarget() not in ('freebsd', 'emscripten'):
            cmd += " -ldl"

        if GetTarget() == 'emscripten':
            optlevel = GetOptimizeOption(opts)
            if optlevel == 2: cmd += " -O1"
            if optlevel == 3: cmd += " -O2"
            if optlevel == 4: cmd += " -O3"

        oscmd(cmd)

        if GetOptimizeOption(opts) == 4 and GetTarget() in ('linux', 'android'):
            oscmd(GetStrip() + " --strip-unneeded " + BracketNameWithQuotes(dll))

        os.system("chmod +x " + BracketNameWithQuotes(dll))

        if dll.endswith("." + MAJOR_VERSION + ".dylib"):
            newdll = dll[:-6-len(MAJOR_VERSION)] + "dylib"
            if os.path.isfile(newdll):
                os.remove(newdll)
            oscmd("ln -s " + BracketNameWithQuotes(os.path.basename(dll)) + " " + BracketNameWithQuotes(newdll))

        elif dll.endswith("." + MAJOR_VERSION):
            newdll = dll[:-len(MAJOR_VERSION)-1]
            if os.path.isfile(newdll):
                os.remove(newdll)
            oscmd("ln -s " + BracketNameWithQuotes(os.path.basename(dll)) + " " + BracketNameWithQuotes(newdll))

##########################################################################################
#
# CompileEgg
#
##########################################################################################

def CompileEgg(eggfile, src, opts):
    pz = False
    if eggfile.endswith(".pz"):
        pz = True
        eggfile = eggfile[:-3]

    # Determine the location of the pzip and flt2egg tools.
    if CrossCompiling():
        # We may not be able to use our generated versions of these tools,
        # so we'll expect them to already be present in the PATH.
        pzip = 'pzip'
        flt2egg = 'flt2egg'
    else:
        # If we're compiling for this machine, we can use the binaries we've built.
        pzip = os.path.join(GetOutputDir(), 'bin', 'pzip')
        flt2egg = os.path.join(GetOutputDir(), 'bin', 'flt2egg')
        if not os.path.isfile(pzip):
            pzip = 'pzip'
        if not os.path.isfile(flt2egg):
            flt2egg = 'flt2egg'

    if src.endswith(".egg"):
        CopyFile(eggfile, src)
    elif src.endswith(".flt"):
        oscmd(flt2egg + ' -ps keep -o ' + BracketNameWithQuotes(eggfile) + ' ' + BracketNameWithQuotes(src))

    if pz:
        if zlib:
            WriteBinaryFile(eggfile + '.pz', zlib.compress(ReadBinaryFile(eggfile)))
            os.remove(eggfile)
        else:
            oscmd(pzip + ' ' + BracketNameWithQuotes(eggfile))

##########################################################################################
#
# CompileRes, CompileRsrc
#
##########################################################################################

def CompileRes(target, src, opts):
    """Compiles a Windows .rc file into a .res file."""
    ipath = GetListOption(opts, "DIR:")
    if (COMPILER == "MSVC"):
        cmd = "rc"
        cmd += " /Fo" + BracketNameWithQuotes(target)
        for x in ipath: cmd += " /I" + x
        for (opt,dir) in INCDIRECTORIES:
            if (opt=="ALWAYS") or (opt in opts):
                cmd += " /I" + BracketNameWithQuotes(dir)
        for (opt,var,val) in DEFSYMBOLS:
            if (opt=="ALWAYS") or (opt in opts):
                cmd += " /D" + var + "=" + val
        cmd += " " + BracketNameWithQuotes(src)
    else:
        cmd = "windres"
        for x in ipath: cmd += " -I" + x
        for (opt,dir) in INCDIRECTORIES:
            if (opt=="ALWAYS") or (opt in opts):
                cmd += " -I" + BracketNameWithQuotes(dir)
        for (opt,var,val) in DEFSYMBOLS:
            if (opt=="ALWAYS") or (opt in opts):
                cmd += " -D" + var + "=" + val
        cmd += " -i " + BracketNameWithQuotes(src)
        cmd += " -o " + BracketNameWithQuotes(target)

    oscmd(cmd)

def CompileRsrc(target, src, opts):
    """Compiles a Mac OS .r file into an .rsrc file."""
    ipath = GetListOption(opts, "DIR:")
    if os.path.isfile("/usr/bin/Rez"):
        cmd = "Rez -useDF"
    elif os.path.isfile("/Library/Developer/CommandLineTools/usr/bin/Rez"):
        cmd = "/Library/Developer/CommandLineTools/usr/bin/Rez -useDF"
    else:
        cmd = "/Developer/Tools/Rez -useDF"
    cmd += " -o " + BracketNameWithQuotes(target)
    for x in ipath:
        cmd += " -i " + x
    for (opt,dir) in INCDIRECTORIES:
        if (opt=="ALWAYS") or (opt in opts):
            cmd += " -i " + BracketNameWithQuotes(dir)
    for (opt,var,val) in DEFSYMBOLS:
        if (opt=="ALWAYS") or (opt in opts):
            if (val == ""):
                cmd += " -d " + var
            else:
                cmd += " -d " + var + " = " + val

    cmd += " " + BracketNameWithQuotes(src)
    oscmd(cmd)

##########################################################################################
#
# CompileJava (Android only)
#
##########################################################################################

def CompileJava(target, src, opts):
    """Compiles a .java file into a .class file."""
    if GetHost() == 'android':
        cmd = "ecj "
    else:
        cmd = "javac "
        home = os.environ.get('JAVA_HOME')
        if home:
            javac_path = os.path.join(home, 'bin', 'javac')
            if GetHost() == 'windows':
                javac_path += '.exe'
            if os.path.isfile(javac_path):
                cmd = BracketNameWithQuotes(javac_path) + " "

        cmd += "-Xlint:deprecation "

    optlevel = GetOptimizeOption(opts)
    if optlevel >= 4:
        cmd += "-debug:none "

    classpath = BracketNameWithQuotes(SDK["ANDROID_JAR"] + ":" + GetOutputDir() + "/classes")
    cmd += "-cp " + classpath + " "
    cmd += "-d " + GetOutputDir() + "/classes "
    cmd += BracketNameWithQuotes(src)
    oscmd(cmd)

##########################################################################################
#
# FreezePy
#
##########################################################################################

def FreezePy(target, inputs, opts):
    assert len(inputs) > 0

    cmdstr = BracketNameWithQuotes(SDK["PYTHONEXEC"].replace('\\', '/')) + " "
    cmdstr += "-B "

    cmdstr += os.path.join(GetOutputDir(), "direct", "dist", "pfreeze.py")

    if 'FREEZE_STARTUP' in opts:
        cmdstr += " -s"

    if GetOrigExt(target) == '.exe':
        src = inputs.pop(0)
    else:
        src = ""

    for i in inputs:
        i = os.path.splitext(i)[0]
        i = i.replace('/', '.')

        if i.startswith('direct.src'):
            i = i.replace('.src.', '.')

        cmdstr += " -i " + i

    cmdstr += " -o " + target + " " + src

    if ("LINK_PYTHON_STATIC" in opts):
        os.environ["LINK_PYTHON_STATIC"] = "1"
    oscmd(cmdstr)
    if ("LINK_PYTHON_STATIC" in os.environ):
        del os.environ["LINK_PYTHON_STATIC"]

    if (not os.path.exists(target)):
        exit("FREEZER_ERROR")

##########################################################################################
#
# CompileBundle
#
##########################################################################################

def CompileBundle(target, inputs, opts):
    assert GetTarget() == "darwin", 'bundles can only be made for macOS'
    plist = None
    resources = []
    objects = []
    for i in inputs:
        if i.endswith(".plist"):
            if plist is not None:
                exit("Only one plist file can be used when creating a bundle!")
            plist = i
        elif i.endswith(".rsrc") or i.endswith(".icns"):
            resources.append(i)
        elif GetOrigExt(i) == ".obj" or GetOrigExt(i) in SUFFIX_LIB or GetOrigExt(i) in SUFFIX_DLL:
            objects.append(i)
        else:
            exit("Don't know how to bundle file %s" % i)

    # Now link the object files to form the bundle.
    if plist is None:
        exit("One plist file must be used when creating a bundle!")
    bundleName = plistlib.load(open(plist, 'rb'))["CFBundleExecutable"]

    oscmd("rm -rf %s" % target)
    oscmd("mkdir -p %s/Contents/MacOS/" % target)
    oscmd("mkdir -p %s/Contents/Resources/" % target)
    if target.endswith(".app"):
        SetOrigExt("%s/Contents/MacOS/%s" % (target, bundleName), ".exe")
    else:
        SetOrigExt("%s/Contents/MacOS/%s" % (target, bundleName), ".dll")
    CompileLink("%s/Contents/MacOS/%s" % (target, bundleName), objects, opts + ["BUNDLE"])
    oscmd("cp %s %s/Contents/Info.plist" % (plist, target))
    for r in resources:
        oscmd("cp %s %s/Contents/Resources/" % (r, target))

##########################################################################################
#
# CompileMIDL
#
##########################################################################################

def CompileMIDL(target, src, opts):
    ipath = GetListOption(opts, "DIR:")
    if (COMPILER=="MSVC"):
        cmd = "midl"
        cmd += " /out" + BracketNameWithQuotes(os.path.dirname(target))
        for x in ipath: cmd += " /I" + x
        for (opt,dir) in INCDIRECTORIES:
            if (opt=="ALWAYS") or (opt in opts): cmd += " /I" + BracketNameWithQuotes(dir)
        for (opt,var,val) in DEFSYMBOLS:
            if (opt=="ALWAYS") or (opt in opts): cmd += " /D" + var + "=" + val
        cmd += " " + BracketNameWithQuotes(src)

        oscmd(cmd)

##########################################################################################
#
# CompileDalvik
#
##########################################################################################

def CompileDalvik(target, inputs, opts):
    cmd = "d8 --output " + os.path.dirname(target)

    if GetOptimize() <= 2:
        cmd += " --debug"
    else:
        cmd += " --release"

    if "ANDROID_API" in SDK:
        cmd += " --min-api %d" % (SDK["ANDROID_API"])

    if "ANDROID_JAR" in SDK:
        cmd += " --lib %s" % (SDK["ANDROID_JAR"])

    for i in inputs:
        cmd += " " + BracketNameWithQuotes(i)

    oscmd(cmd)

##########################################################################################
#
# CompileAnything
#
##########################################################################################

def CompileAnything(target, inputs, opts, progress = None):
    if opts.count("DEPENDENCYONLY"):
        return
    if len(inputs) == 0:
        exit("No input files for target "+target)
    infile = inputs[0]
    origsuffix = GetOrigExt(target)

    if len(inputs) == 1 and origsuffix == GetOrigExt(infile):
        # It must be a simple copy operation.
        ProgressOutput(progress, "Copying file", target)
        CopyFile(target, infile)
        if origsuffix == ".exe" and GetHost() != "windows":
            os.system("chmod +x \"%s\"" % target)
        return

    elif infile.endswith(".py"):
        if origsuffix == ".obj":
            source = os.path.splitext(target)[0] + ".c"
            SetOrigExt(source, ".c")
            ProgressOutput(progress, "Building frozen source", source)
            FreezePy(source, inputs, opts)
            ProgressOutput(progress, "Building C++ object", target)
            return CompileCxx(target, source, opts)

        if origsuffix == ".exe":
            ProgressOutput(progress, "Building frozen executable", target)
        else:
            ProgressOutput(progress, "Building frozen library", target)
        return FreezePy(target, inputs, opts)

    elif infile.endswith(".idl"):
        ProgressOutput(progress, "Compiling MIDL file", infile)
        return CompileMIDL(target, infile, opts)
    elif origsuffix in SUFFIX_LIB:
        ProgressOutput(progress, "Linking static library", target)
        return CompileLib(target, inputs, opts)
    elif origsuffix in SUFFIX_DLL or (origsuffix == ".plugin" and GetTarget() != "darwin"):
        if (origsuffix == ".exe"):
            ProgressOutput(progress, "Linking executable", target)
        else:
            ProgressOutput(progress, "Linking dynamic library", target)

        # Add version number to the dynamic library, on unix
        if origsuffix == ".dll" and "MODULE" not in opts:
            tplatform = GetTarget()
            if tplatform == "darwin":
                # On Mac, libraries are named like libpanda.1.2.dylib
                if target.lower().endswith(".dylib"):
                    target = target[:-5] + MAJOR_VERSION + ".dylib"
                    SetOrigExt(target, origsuffix)
            elif tplatform not in ("windows", "android", "emscripten"):
                # On Linux, libraries are named like libpanda.so.1.2
                target += "." + MAJOR_VERSION
                SetOrigExt(target, origsuffix)
        return CompileLink(target, inputs, opts)
    elif origsuffix == ".in":
        ProgressOutput(progress, "Building Interrogate database", target)
        return CompileIgate(target, inputs, opts)
    elif origsuffix == ".plugin" and GetTarget() == "darwin":
        ProgressOutput(progress, "Building plugin bundle", target)
        return CompileBundle(target, inputs, opts)
    elif origsuffix == ".app":
        ProgressOutput(progress, "Building application bundle", target)
        return CompileBundle(target, inputs, opts)
    elif origsuffix == ".pz":
        ProgressOutput(progress, "Compressing", target)
        return CompileEgg(target, infile, opts)
    elif origsuffix == ".egg":
        ProgressOutput(progress, "Converting", target)
        return CompileEgg(target, infile, opts)
    elif origsuffix == ".res":
        ProgressOutput(progress, "Building resource object", target)
        return CompileRes(target, infile, opts)
    elif origsuffix == ".rsrc":
        ProgressOutput(progress, "Building resource object", target)
        return CompileRsrc(target, infile, opts)
    elif origsuffix == ".class":
        ProgressOutput(progress, "Building Java class", target)
        return CompileJava(target, infile, opts)
    elif origsuffix == ".obj":
        if (infile.endswith(".cxx")):
            ProgressOutput(progress, "Building C++ object", target)
            return CompileCxx(target, infile, opts)
        elif infile.endswith(".c"):
            ProgressOutput(progress, "Building C object", target)
            return CompileCxx(target, infile, opts)
        elif infile.endswith(".mm"):
            ProgressOutput(progress, "Building Objective-C++ object", target)
            return CompileCxx(target, infile, opts)
        elif infile.endswith(".yxx"):
            ProgressOutput(progress, "Building Bison object", target)
            return CompileBison(target, infile, opts)
        elif infile.endswith(".lxx"):
            ProgressOutput(progress, "Building Flex object", target)
            return CompileFlex(target, infile, opts)
        elif infile.endswith(".in"):
            ProgressOutput(progress, "Building Interrogate object", target)
            return CompileImod(target, inputs, opts)
        elif infile.endswith(".rc"):
            ProgressOutput(progress, "Building resource object", target)
            return CompileRes(target, infile, opts)
        elif infile.endswith(".r"):
            ProgressOutput(progress, "Building resource object", target)
            return CompileRsrc(target, infile, opts)
    elif origsuffix == ".dex":
        ProgressOutput(progress, "Building Dalvik object", target)
        return CompileDalvik(target, inputs, opts)
    exit("Don't know how to compile: %s from %s" % (target, inputs))

##########################################################################################
#
# Generate dtool_config.h, prc_parameters.h, and dtool_have_xxx.dat
#
##########################################################################################

DTOOL_CONFIG=[
    #_Variable_________________________Windows___________________Unix__________
    ("HAVE_PYTHON",                    '1',                      '1'),
    ("USE_DEBUG_PYTHON",               'UNDEF',                  'UNDEF'),
    ("PYTHON_FRAMEWORK",               'UNDEF',                  'UNDEF'),
    ("COMPILE_IN_DEFAULT_FONT",        '1',                      '1'),
    ("STDFLOAT_DOUBLE",                'UNDEF',                  'UNDEF'),
    ("REPORT_OPENSSL_ERRORS",          '1',                      '1'),
    ("USE_PANDAFILESTREAM",            '1',                      '1'),
    ("USE_DELETED_CHAIN",              '1',                      '1'),
    ("HAVE_MIMALLOC",                  'UNDEF',                  'UNDEF'),
    ("HAVE_WGL",                       '1',                      'UNDEF'),
    ("HAVE_DX9",                       'UNDEF',                  'UNDEF'),
    ("HAVE_THREADS",                   '1',                      '1'),
    ("SIMPLE_THREADS",                 'UNDEF',                  'UNDEF'),
    ("OS_SIMPLE_THREADS",              '1',                      '1'),
    ("DEBUG_THREADS",                  'UNDEF',                  'UNDEF'),
    ("HAVE_POSIX_THREADS",             'UNDEF',                  '1'),
    ("MUTEX_SPINLOCK",                 'UNDEF',                  'UNDEF'),
    ("HAVE_AUDIO",                     '1',                      '1'),
    ("NOTIFY_DEBUG",                   'UNDEF',                  'UNDEF'),
    ("DO_PSTATS",                      'UNDEF',                  'UNDEF'),
    ("DO_DCAST",                       'UNDEF',                  'UNDEF'),
    ("DO_COLLISION_RECORDING",         'UNDEF',                  'UNDEF'),
    ("SUPPORT_IMMEDIATE_MODE",         'UNDEF',                  'UNDEF'),
    ("SUPPORT_FIXED_FUNCTION",         '1',                      '1'),
    ("DO_MEMORY_USAGE",                'UNDEF',                  'UNDEF'),
    ("DO_PIPELINING",                  '1',                      '1'),
    ("DEFAULT_PATHSEP",                '";"',                    '":"'),
    ("WORDS_BIGENDIAN",                'UNDEF',                  'UNDEF'),
    ("PHAVE_LOCKF",                    '1',                      '1'),
    ("SIMPLE_STRUCT_POINTERS",         '1',                      'UNDEF'),
    ("HAVE_DINKUM",                    'UNDEF',                  'UNDEF'),
    ("HAVE_STL_HASH",                  'UNDEF',                  'UNDEF'),
    ("GETTIMEOFDAY_ONE_PARAM",         'UNDEF',                  'UNDEF'),
    ("HAVE_GETOPT",                    'UNDEF',                  '1'),
    ("HAVE_GETOPT_LONG_ONLY",          'UNDEF',                  '1'),
    ("PHAVE_GETOPT_H",                 'UNDEF',                  '1'),
    ("PHAVE_LINUX_INPUT_H",            'UNDEF',                  '1'),
    ("IOCTL_TERMINAL_WIDTH",           'UNDEF',                  '1'),
    ("HAVE_IOS_TYPEDEFS",              '1',                      '1'),
    ("HAVE_IOS_BINARY",                '1',                      '1'),
    ("STATIC_INIT_GETENV",             '1',                      'UNDEF'),
    ("HAVE_PROC_SELF_EXE",             'UNDEF',                  '1'),
    ("HAVE_PROC_SELF_MAPS",            'UNDEF',                  '1'),
    ("HAVE_PROC_SELF_ENVIRON",         'UNDEF',                  '1'),
    ("HAVE_PROC_SELF_CMDLINE",         'UNDEF',                  '1'),
    ("HAVE_PROC_CURPROC_FILE",         'UNDEF',                  'UNDEF'),
    ("HAVE_PROC_CURPROC_MAP",          'UNDEF',                  'UNDEF'),
    ("HAVE_PROC_CURPROC_CMDLINE",      'UNDEF',                  'UNDEF'),
    ("HAVE_GLOBAL_ARGV",               '1',                      'UNDEF'),
    ("PROTOTYPE_GLOBAL_ARGV",          'UNDEF',                  'UNDEF'),
    ("GLOBAL_ARGV",                    '__argv',                 'UNDEF'),
    ("GLOBAL_ARGC",                    '__argc',                 'UNDEF'),
    ("PHAVE_IO_H",                     '1',                      'UNDEF'),
    ("PHAVE_IOSTREAM",                 '1',                      '1'),
    ("PHAVE_STRING_H",                 'UNDEF',                  '1'),
    ("PHAVE_LIMITS_H",                 'UNDEF',                  '1'),
    ("PHAVE_STDLIB_H",                 'UNDEF',                  '1'),
    ("PHAVE_MALLOC_H",                 '1',                      '1'),
    ("PHAVE_SYS_MALLOC_H",             'UNDEF',                  'UNDEF'),
    ("PHAVE_ALLOCA_H",                 'UNDEF',                  '1'),
    ("PHAVE_LOCALE_H",                 'UNDEF',                  '1'),
    ("PHAVE_SSTREAM",                  '1',                      '1'),
    ("PHAVE_NEW",                      '1',                      '1'),
    ("PHAVE_SYS_TYPES_H",              '1',                      '1'),
    ("PHAVE_SYS_TIME_H",               'UNDEF',                  '1'),
    ("PHAVE_UNISTD_H",                 'UNDEF',                  '1'),
    ("PHAVE_UTIME_H",                  'UNDEF',                  '1'),
    ("PHAVE_GLOB_H",                   'UNDEF',                  '1'),
    ("PHAVE_DIRENT_H",                 'UNDEF',                  '1'),
    ("PHAVE_UCONTEXT_H",               'UNDEF',                  '1'),
    ("PHAVE_STDINT_H",                 '1',                      '1'),
    ("HAVE_RTTI",                      '1',                      '1'),
    ("HAVE_X11",                       'UNDEF',                  '1'),
    ("IS_LINUX",                       'UNDEF',                  '1'),
    ("IS_OSX",                         'UNDEF',                  'UNDEF'),
    ("IS_FREEBSD",                     'UNDEF',                  'UNDEF'),
    ("HAVE_EIGEN",                     'UNDEF',                  'UNDEF'),
    ("LINMATH_ALIGN",                  '1',                      '1'),
    ("HAVE_ZLIB",                      'UNDEF',                  'UNDEF'),
    ("HAVE_PNG",                       'UNDEF',                  'UNDEF'),
    ("HAVE_JPEG",                      'UNDEF',                  'UNDEF'),
    ("HAVE_VIDEO4LINUX",               'UNDEF',                  '1'),
    ("HAVE_TIFF",                      'UNDEF',                  'UNDEF'),
    ("HAVE_OPENEXR",                   'UNDEF',                  'UNDEF'),
    ("HAVE_SGI_RGB",                   '1',                      '1'),
    ("HAVE_TGA",                       '1',                      '1'),
    ("HAVE_IMG",                       '1',                      '1'),
    ("HAVE_SOFTIMAGE_PIC",             '1',                      '1'),
    ("HAVE_BMP",                       '1',                      '1'),
    ("HAVE_PNM",                       '1',                      '1'),
    ("HAVE_STB_IMAGE",                 '1',                      '1'),
    ("HAVE_VORBIS",                    'UNDEF',                  'UNDEF'),
    ("HAVE_OPUS",                      'UNDEF',                  'UNDEF'),
    ("HAVE_FREETYPE",                  'UNDEF',                  'UNDEF'),
    ("HAVE_FFTW",                      'UNDEF',                  'UNDEF'),
    ("HAVE_OPENSSL",                   'UNDEF',                  'UNDEF'),
    ("HAVE_NET",                       'UNDEF',                  'UNDEF'),
    ("WANT_NATIVE_NET",                '1',                      '1'),
    ("SIMULATE_NETWORK_DELAY",         'UNDEF',                  'UNDEF'),
    ("HAVE_CG",                        'UNDEF',                  'UNDEF'),
    ("HAVE_CGGL",                      'UNDEF',                  'UNDEF'),
    ("HAVE_CGDX9",                     'UNDEF',                  'UNDEF'),
    ("HAVE_ARTOOLKIT",                 'UNDEF',                  'UNDEF'),
    ("HAVE_DIRECTCAM",                 'UNDEF',                  'UNDEF'),
    ("HAVE_SQUISH",                    'UNDEF',                  'UNDEF'),
    ("HAVE_COCOA",                     'UNDEF',                  'UNDEF'),
    ("HAVE_OPENAL_FRAMEWORK",          'UNDEF',                  'UNDEF'),
    ("USE_TAU",                        'UNDEF',                  'UNDEF'),
    ("PRC_SAVE_DESCRIPTIONS",          '1',                      '1'),
#    ("_SECURE_SCL",                    '0',                      'UNDEF'),
#    ("_SECURE_SCL_THROWS",             '0',                      'UNDEF'),
]

PRC_PARAMETERS=[
    ("DEFAULT_PRC_DIR",                '"<auto>etc"',            '"<auto>etc"'),
    ("PRC_DIR_ENVVARS",                '"PANDA_PRC_DIR"',        '"PANDA_PRC_DIR"'),
    ("PRC_PATH_ENVVARS",               '"PANDA_PRC_PATH"',       '"PANDA_PRC_PATH"'),
    ("PRC_PATH2_ENVVARS",              'UNDEF',                  'UNDEF'),
    ("PRC_PATTERNS",                   '"*.prc"',                '"*.prc"'),
    ("PRC_ENCRYPTED_PATTERNS",         '"*.prc.pe"',             '"*.prc.pe"'),
    ("PRC_ENCRYPTION_KEY",             '""',                     '""'),
    ("PRC_EXECUTABLE_PATTERNS",        'UNDEF',                  'UNDEF'),
    ("PRC_EXECUTABLE_ARGS_ENVVAR",     '"PANDA_PRC_XARGS"',      '"PANDA_PRC_XARGS"'),
    ("PRC_PUBLIC_KEYS_FILENAME",       '""',                     '""'),
    ("PRC_RESPECT_TRUST_LEVEL",        'UNDEF',                  'UNDEF'),
    ("PRC_DCONFIG_TRUST_LEVEL",        '0',                      '0'),
    ("PRC_INC_TRUST_LEVEL",            '0',                      '0'),
]

def WriteConfigSettings():
    dtool_config={}
    prc_parameters={}
    speedtree_parameters={}

    if (GetTarget() == 'windows'):
        for key,win,unix in DTOOL_CONFIG:
            dtool_config[key] = win
        for key,win,unix in PRC_PARAMETERS:
            prc_parameters[key] = win
    else:
        for key,win,unix in DTOOL_CONFIG:
            dtool_config[key] = unix
        for key,win,unix in PRC_PARAMETERS:
            prc_parameters[key] = unix

    for x in PkgListGet():
        if ("HAVE_"+x in dtool_config):
            if (PkgSkip(x)==0):
                dtool_config["HAVE_"+x] = '1'
            else:
                dtool_config["HAVE_"+x] = 'UNDEF'

    dtool_config["HAVE_NET"] = '1'

    if GetTarget() == 'windows':
        if not PkgSkip("MIMALLOC"):
            # This is faster than both DeletedBufferChain and malloc,
            # especially in the multi-threaded case.
            dtool_config["USE_MEMORY_MIMALLOC"] = '1'
            dtool_config["USE_DELETED_CHAIN"] = 'UNDEF'
        else:
            # If we don't have mimalloc, use DeletedBufferChain as fallback,
            # which is still more efficient than malloc.
            dtool_config["USE_DELETED_CHAIN"] = '1'
    else:
        # On other systems, the default malloc seems to be fine.
        dtool_config["USE_DELETED_CHAIN"] = 'UNDEF'

    if (PkgSkip("NVIDIACG")==0):
        dtool_config["HAVE_CG"] = '1'
        dtool_config["HAVE_CGGL"] = '1'
        dtool_config["HAVE_CGDX9"] = '1'

    if GetTarget() not in ("linux", "android"):
        dtool_config["HAVE_PROC_SELF_EXE"] = 'UNDEF'
        dtool_config["HAVE_PROC_SELF_MAPS"] = 'UNDEF'
        dtool_config["HAVE_PROC_SELF_CMDLINE"] = 'UNDEF'
        dtool_config["HAVE_PROC_SELF_ENVIRON"] = 'UNDEF'

    if (GetTarget() == "darwin"):
        dtool_config["PYTHON_FRAMEWORK"] = 'Python'
        dtool_config["PHAVE_MALLOC_H"] = 'UNDEF'
        dtool_config["PHAVE_SYS_MALLOC_H"] = '1'
        if not os.path.isdir(GetThirdpartyDir() + "openal"):
            dtool_config["HAVE_OPENAL_FRAMEWORK"] = '1'
        dtool_config["HAVE_X11"] = 'UNDEF'  # We might have X11, but we don't need it.
        dtool_config["IS_LINUX"] = 'UNDEF'
        dtool_config["HAVE_VIDEO4LINUX"] = 'UNDEF'
        dtool_config["PHAVE_LINUX_INPUT_H"] = 'UNDEF'
        dtool_config["IS_OSX"] = '1'

    if (GetTarget() == "freebsd"):
        dtool_config["IS_LINUX"] = 'UNDEF'
        dtool_config["HAVE_VIDEO4LINUX"] = 'UNDEF'
        dtool_config["IS_FREEBSD"] = '1'
        dtool_config["PHAVE_ALLOCA_H"] = 'UNDEF'
        dtool_config["PHAVE_MALLOC_H"] = 'UNDEF'
        dtool_config["HAVE_PROC_CURPROC_FILE"] = '1'
        dtool_config["HAVE_PROC_CURPROC_MAP"] = '1'
        dtool_config["HAVE_PROC_CURPROC_CMDLINE"] = '1'

    if (GetTarget() == "android"):
        # Android does have RTTI, but we disable it anyway.
        dtool_config["HAVE_RTTI"] = 'UNDEF'
        dtool_config["PHAVE_GLOB_H"] = 'UNDEF'
        dtool_config["PHAVE_LOCKF"] = 'UNDEF'
        dtool_config["HAVE_VIDEO4LINUX"] = 'UNDEF'

    if (GetTarget() == "emscripten"):
        # There are no threads in JavaScript, so don't bother using them.
        dtool_config["HAVE_THREADS"] = 'UNDEF'
        dtool_config["DO_PIPELINING"] = 'UNDEF'
        dtool_config["HAVE_POSIX_THREADS"] = 'UNDEF'
        dtool_config["IS_LINUX"] = 'UNDEF'
        dtool_config["HAVE_VIDEO4LINUX"] = 'UNDEF'
        dtool_config["HAVE_NET"] = 'UNDEF'
        dtool_config["PHAVE_LINUX_INPUT_H"] = 'UNDEF'
        dtool_config["HAVE_X11"] = 'UNDEF'
        dtool_config["HAVE_GLX"] = 'UNDEF'

        # There are no environment vars either, or default prc files.
        prc_parameters["DEFAULT_PRC_DIR"] = 'UNDEF'
        prc_parameters["PRC_DIR_ENVVARS"] = 'UNDEF'
        prc_parameters["PRC_PATH_ENVVARS"] = 'UNDEF'
        prc_parameters["PRC_PATH2_ENVVARS"] = 'UNDEF'
        prc_parameters["PRC_PATTERNS"] = 'UNDEF'
        prc_parameters["PRC_ENCRYPTED_PATTERNS"] = 'UNDEF'

    if (GetOptimize() <= 2 and GetTarget() == "windows"):
        dtool_config["USE_DEBUG_PYTHON"] = '1'

    if (GetOptimize() <= 3):
        if (dtool_config["HAVE_NET"] != 'UNDEF'):
            dtool_config["DO_PSTATS"] = '1'

    if (GetOptimize() <= 3):
        dtool_config["DO_DCAST"] = '1'

    if (GetOptimize() <= 3):
        dtool_config["DO_COLLISION_RECORDING"] = '1'

    if (GetOptimize() <= 3) and GetTarget() != 'emscripten':
        dtool_config["DO_MEMORY_USAGE"] = '1'

    if (GetOptimize() <= 3):
        dtool_config["NOTIFY_DEBUG"] = '1'

    if (GetOptimize() >= 4):
        dtool_config["PRC_SAVE_DESCRIPTIONS"] = 'UNDEF'

    if (GetOptimize() >= 4):
        # Disable RTTI on release builds.
        dtool_config["HAVE_RTTI"] = 'UNDEF'

    # Now that we have OS_SIMPLE_THREADS, we can support
    # SIMPLE_THREADS on exotic architectures like win64, so we no
    # longer need to disable it for this platform.
##     if GetTarget() == 'windows' and GetTargetArch() == 'x64':
##         dtool_config["SIMPLE_THREADS"] = 'UNDEF'

    if not PkgSkip("SPEEDTREE"):
        speedtree_parameters["SPEEDTREE_OPENGL"] = "UNDEF"
        speedtree_parameters["SPEEDTREE_DIRECTX9"] = "UNDEF"
        if SDK["SPEEDTREEAPI"] == "OpenGL":
            speedtree_parameters["SPEEDTREE_OPENGL"] = "1"
        elif SDK["SPEEDTREEAPI"] == "DirectX9":
            speedtree_parameters["SPEEDTREE_DIRECTX9"] = "1"

        speedtree_parameters["SPEEDTREE_BIN_DIR"] = (SDK["SPEEDTREE"] + "/Bin")

    conf = "/* prc_parameters.h.  Generated automatically by makepanda.py */\n"
    for key in sorted(prc_parameters.keys()):
        if ((key == "DEFAULT_PRC_DIR") or (key[:4]=="PRC_")):
            val = OverrideValue(key, prc_parameters[key])
            if (val == 'UNDEF'): conf = conf + "#undef " + key + "\n"
            else:                conf = conf + "#define " + key + " " + val + "\n"
    ConditionalWriteFile(GetOutputDir() + '/include/prc_parameters.h', conf)

    conf = "/* dtool_config.h.  Generated automatically by makepanda.py */\n"
    for key in sorted(dtool_config.keys()):
        val = OverrideValue(key, dtool_config[key])

        if key in ('HAVE_CG', 'HAVE_CGGL', 'HAVE_CGDX9') and val != 'UNDEF':
            # These are not available for ARM, period.
            conf = conf + "#ifdef __aarch64__\n"
            conf = conf + "#undef " + key + "\n"
            conf = conf + "#else\n"
            conf = conf + "#define " + key + " " + val + "\n"
            conf = conf + "#endif\n"
        elif val == 'UNDEF':
            conf = conf + "#undef " + key + "\n"
        else:
            conf = conf + "#define " + key + " " + val + "\n"

    ConditionalWriteFile(GetOutputDir() + '/include/dtool_config.h', conf)

    if not PkgSkip("SPEEDTREE"):
        conf = "/* speedtree_parameters.h.  Generated automatically by makepanda.py */\n"
        for key in sorted(speedtree_parameters.keys()):
            val = OverrideValue(key, speedtree_parameters[key])
            if (val == 'UNDEF'): conf = conf + "#undef " + key + "\n"
            else:                conf = conf + "#define " + key + " \"" + val.replace("\\", "\\\\") + "\"\n"
        ConditionalWriteFile(GetOutputDir() + '/include/speedtree_parameters.h', conf)

    for x in PkgListGet():
        if (PkgSkip(x)): ConditionalWriteFile(GetOutputDir() + '/tmp/dtool_have_'+x.lower()+'.dat', "0\n")
        else:            ConditionalWriteFile(GetOutputDir() + '/tmp/dtool_have_'+x.lower()+'.dat', "1\n")

    # Finally, write a platform.dat with the platform we are compiling for.
    ConditionalWriteFile(GetOutputDir() + '/tmp/platform.dat', PLATFORM)

    # This is useful for tools like makepackage that need to know things about
    # the build parameters.
    ConditionalWriteFile(GetOutputDir() + '/tmp/optimize.dat', str(GetOptimize()))


WriteConfigSettings()

WarnConflictingFiles()
if SystemLibraryExists("dtoolbase"):
    Warn("Found conflicting Panda3D libraries from other ppremake build!")
if SystemLibraryExists("p3dtoolconfig"):
    Warn("Found conflicting Panda3D libraries from other makepanda build!")

##########################################################################################
#
# Generate pandaVersion.h, pythonversion, null.cxx, etc.
#
##########################################################################################

PANDAVERSION_H="""
#define PANDA_MAJOR_VERSION $VERSION1
#define PANDA_MINOR_VERSION $VERSION2
#define PANDA_SEQUENCE_VERSION $VERSION3
#define PANDA_VERSION $NVERSION
#define PANDA_NUMERIC_VERSION $NVERSION
#define PANDA_VERSION_STR "$VERSION"
#define PANDA_ABI_VERSION_STR "$VERSION1.$VERSION2"
#define PANDA_DISTRIBUTOR "$DISTRIBUTOR"
"""

CHECKPANDAVERSION_CXX="""
# include "dtoolbase.h"
EXPCL_DTOOL_DTOOLBASE int panda_version_$VERSION1_$VERSION2 = 0;
"""

CHECKPANDAVERSION_H="""
# ifndef CHECKPANDAVERSION_H
# define CHECKPANDAVERSION_H
# include "dtoolbase.h"
extern EXPCL_DTOOL_DTOOLBASE int panda_version_$VERSION1_$VERSION2;
// Hack to forcibly depend on the check
template<typename T>
class CheckPandaVersion {
public:
  int check_version() { return panda_version_$VERSION1_$VERSION2; }
};
template class CheckPandaVersion<void>;
# endif
"""


def CreatePandaVersionFiles():
    parts = VERSION.split(".", 2)
    version1 = int(parts[0])
    version2 = int(parts[1])
    version3 = 0
    if len(parts) > 2:
        for c in parts[2]:
            if c.isdigit():
                version3 = version3 * 10 + ord(c) - 48
            else:
                break
    nversion = version1 * 1000000 + version2 * 1000 + version3
    if DISTRIBUTOR != "cmu":
        # Subtract 1 if we are not an official version.
        nversion -= 1

    pandaversion_h = PANDAVERSION_H
    pandaversion_h = pandaversion_h.replace("$VERSION1",str(version1))
    pandaversion_h = pandaversion_h.replace("$VERSION2",str(version2))
    pandaversion_h = pandaversion_h.replace("$VERSION3",str(version3))
    pandaversion_h = pandaversion_h.replace("$VERSION",VERSION)
    pandaversion_h = pandaversion_h.replace("$NVERSION",str(nversion))
    pandaversion_h = pandaversion_h.replace("$DISTRIBUTOR",DISTRIBUTOR)
    if (DISTRIBUTOR == "cmu"):
        pandaversion_h += "\n#define PANDA_OFFICIAL_VERSION\n"
    else:
        pandaversion_h += "\n#undef  PANDA_OFFICIAL_VERSION\n"

    if GIT_COMMIT:
        pandaversion_h += "\n#define PANDA_GIT_COMMIT_STR \"%s\"\n" % (GIT_COMMIT)

    # Allow creating a deterministic build by setting this.
    source_date = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date:
        # This matches the GCC / Clang format for __DATE__ __TIME__
        source_date = time.gmtime(int(source_date))
        try:
            source_date = time.strftime('%b %e %Y %H:%M:%S', source_date)
        except ValueError:
            source_date = time.strftime('%b %d %Y %H:%M:%S', source_date)
            if source_date[3:5] == ' 0':
                source_date = source_date[:3] + '  ' + source_date[5:]
        pandaversion_h += "\n#define PANDA_BUILD_DATE_STR \"%s\"\n" % (source_date)

    checkpandaversion_cxx = CHECKPANDAVERSION_CXX.replace("$VERSION1",str(version1))
    checkpandaversion_cxx = checkpandaversion_cxx.replace("$VERSION2",str(version2))
    checkpandaversion_cxx = checkpandaversion_cxx.replace("$VERSION3",str(version3))
    checkpandaversion_cxx = checkpandaversion_cxx.replace("$NVERSION",str(nversion))

    checkpandaversion_h = CHECKPANDAVERSION_H.replace("$VERSION1",str(version1))
    checkpandaversion_h = checkpandaversion_h.replace("$VERSION2",str(version2))
    checkpandaversion_h = checkpandaversion_h.replace("$VERSION3",str(version3))
    checkpandaversion_h = checkpandaversion_h.replace("$NVERSION",str(nversion))

    ConditionalWriteFile(GetOutputDir()+'/include/pandaVersion.h',        pandaversion_h)
    ConditionalWriteFile(GetOutputDir()+'/include/checkPandaVersion.cxx', checkpandaversion_cxx)
    ConditionalWriteFile(GetOutputDir()+'/include/checkPandaVersion.h',   checkpandaversion_h)
    ConditionalWriteFile(GetOutputDir()+"/tmp/null.cxx","")

CreatePandaVersionFiles()

##########################################################################################
#
# Copy the "direct" tree
#
##########################################################################################

if not PkgSkip("DIRECT"):
    CopyPythonTree(GetOutputDir() + '/direct', 'direct/src', threads=THREADCOUNT)
    ConditionalWriteFile(GetOutputDir() + '/direct/__init__.py', "")

    # This file used to be copied, but would nowadays cause conflicts.
    # Let's get it out of the way in case someone hasn't cleaned their build since.
    if os.path.isfile(GetOutputDir() + '/bin/panda3d.py'):
        os.remove(GetOutputDir() + '/bin/panda3d.py')
    if os.path.isfile(GetOutputDir() + '/lib/panda3d.py'):
        os.remove(GetOutputDir() + '/lib/panda3d.py')

    # This directory doesn't exist at all any more.
    if os.path.isdir(os.path.join(GetOutputDir(), 'direct', 'ffi')):
        shutil.rmtree(os.path.join(GetOutputDir(), 'direct', 'ffi'))

# These files used to exist; remove them to avoid conflicts.
del_files = ['core.py', 'core.pyc', 'core.pyo',
             '_core.pyd', '_core.so',
             'direct.py', 'direct.pyc', 'direct.pyo',
             '_direct.pyd', '_direct.so',
             'dtoolconfig.pyd', 'dtoolconfig.so',
             'net.pyd', 'net.so',
             'interrogatedb.pyd', 'interrogatedb.so']

for basename in del_files:
    path = os.path.join(GetOutputDir(), 'panda3d', basename)
    if os.path.isfile(path):
        print("Removing %s" % (path))
        os.remove(path)

# Write an appropriate panda3d/__init__.py
p3d_init = """"Python bindings for the Panda3D libraries"

__version__ = '%s'

if __debug__:
    if 1 / 2 == 0:
        raise ImportError("Python 2 is not supported.")
""" % (WHLVERSION)

if GetTarget() == 'windows':
    p3d_init += """
if '__file__' in locals():
    import os

    bindir = os.path.join(os.path.dirname(__file__), '..', 'bin')
    if os.path.isdir(bindir):
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(bindir)
        elif not os.environ.get('PATH'):
            os.environ['PATH'] = bindir
        else:
            os.environ['PATH'] = bindir + os.pathsep + os.environ['PATH']
    del os, bindir
"""

if not PkgSkip("PYTHON"):
    ConditionalWriteFile(GetOutputDir() + '/panda3d/__init__.py', p3d_init)

    # Also add this file, for backward compatibility.
    ConditionalWriteFile(GetOutputDir() + '/panda3d/dtoolconfig.py', """\
'''Alias of :mod:`panda3d.interrogatedb`.

.. deprecated:: 1.10.0
   This module has been renamed to :mod:`panda3d.interrogatedb`.
'''

if __debug__:
    print("Warning: panda3d.dtoolconfig is deprecated, use panda3d.interrogatedb instead.")
from .interrogatedb import *
""")

    # Add this for forward compatibility.
    ConditionalWriteFile(GetOutputDir() + '/panda3d/net.py', """\
__all__ = 'BufferedDatagramConnection', 'Buffered_DatagramConnection', 'Connection', 'ConnectionListener', 'ConnectionManager', 'ConnectionReader', 'ConnectionWriter', 'DatagramGeneratorNet', 'DatagramSinkNet', 'Dtool_BorrowThisReference', 'Dtool_PyNativeInterface', 'NetAddress', 'NetDatagram', 'PointerToBaseConnection', 'PointerToBase_Connection', 'PointerToConnection', 'PointerTo_Connection', 'QueuedConnectionListener', 'QueuedConnectionManager', 'QueuedConnectionReader', 'QueuedReturnConnectionListenerData', 'QueuedReturnDatagram', 'QueuedReturnNetDatagram', 'QueuedReturnPointerToConnection', 'QueuedReturn_ConnectionListenerData', 'QueuedReturn_Datagram', 'QueuedReturn_NetDatagram', 'QueuedReturn_PointerTo_Connection', 'RecentConnectionReader', 'SocketAddress', 'SocketFdset', 'SocketIP', 'SocketTCP', 'SocketTCPListen', 'SocketUDP', 'SocketUDPIncoming', 'SocketUDPOutgoing', 'Socket_Address', 'Socket_IP', 'Socket_TCP', 'Socket_TCP_Listen', 'Socket_UDP', 'Socket_UDP_Incoming', 'Socket_UDP_Outgoing', 'Socket_fdset'

from . import core

scope = globals()
for name in __all__:
    if hasattr(core, name):
        scope[name] = getattr(core, name)

del core, scope, name
""")

# PandaModules is now deprecated; generate a shim for backward compatibility.
for fn in glob.glob(GetOutputDir() + '/pandac/*.py') + glob.glob(GetOutputDir() + '/pandac/*.py[co]'):
    if os.path.basename(fn) not in ('PandaModules.py', '__init__.py'):
        os.remove(fn)

panda_modules = ['core']
if not PkgSkip("PANDAPHYSICS"):
    panda_modules.append('physics')
if not PkgSkip('PANDAFX'):
    panda_modules.append('fx')
if not PkgSkip("DIRECT"):
    panda_modules.append('direct')
if not PkgSkip("VISION"):
    panda_modules.append('vision')
if not PkgSkip("SKEL"):
    panda_modules.append('skel')
if not PkgSkip("EGG"):
    panda_modules.append('egg')
if not PkgSkip("ODE"):
    panda_modules.append('ode')
if not PkgSkip("VRPN"):
    panda_modules.append('vrpn')
if not PkgSkip("NAMETAG") or not PkgSkip("MOVEMENT") or not PkgSkip("NAVIGATION"):
    panda_modules.append('otp')
if not PkgSkip("DNA") or not PkgSkip("SUIT") or not PkgSkip("PETS"):
    panda_modules.append('toontown')

panda_modules_code = """
"This module is deprecated.  Import from panda3d.core and other panda3d.* modules instead."

if __debug__:
    print("Warning: pandac.PandaModules is deprecated, import from panda3d.core instead")
"""

for module in panda_modules:
    panda_modules_code += """
try:
    from panda3d.%s import *
except ImportError as err:
    if "No module named %s" not in str(err):
        raise""" % (module, module)

panda_modules_code += """

from direct.showbase import DConfig

def get_config_showbase():
    return DConfig

def get_config_express():
    return DConfig

getConfigShowbase = get_config_showbase
getConfigExpress = get_config_express
"""

exthelpers_code = """
"This module is deprecated.  Import from direct.extensions_native.extension_native_helpers instead."
from direct.extensions_native.extension_native_helpers import *
"""

if not PkgSkip("PYTHON"):
    ConditionalWriteFile(GetOutputDir() + '/pandac/PandaModules.py', panda_modules_code)
    ConditionalWriteFile(GetOutputDir() + '/pandac/extension_native_helpers.py', exthelpers_code)
    ConditionalWriteFile(GetOutputDir() + '/pandac/__init__.py', '')

##########################################################################################
#
# Write the dist-info directory.
#
##########################################################################################

# This is just some basic stuff since setuptools just needs this file to
# exist, otherwise it will not read the entry_points.txt file.  Maybe we will
# eventually want to merge this with the metadata generator in makewheel.py.
METADATA = """Metadata-Version: 2.1
Name: Panda3D
Version: {version}
License: BSD
Home-page: https://www.panda3d.org/
Author: Panda3D Team
Author-email: etc-panda3d@lists.andrew.cmu.edu
"""

ENTRY_POINTS = """[distutils.commands]
build_apps = direct.dist.commands:build_apps
bdist_apps = direct.dist.commands:bdist_apps

[setuptools.finalize_distribution_options]
build_apps = direct.dist._dist_hooks:finalize_distribution_options
"""

if not PkgSkip("DIRECT"):
    dist_dir = os.path.join(GetOutputDir(), 'panda3d.dist-info')
    MakeDirectory(dist_dir)

    ConditionalWriteFile(os.path.join(dist_dir, 'METADATA'), METADATA.format(version=VERSION))
    ConditionalWriteFile(os.path.join(dist_dir, 'entry_points.txt'), ENTRY_POINTS)

##########################################################################################
#
# Generate the PRC files into the ETC directory.
#
##########################################################################################

confautoprc = ReadFile("makepanda/confauto.in")
if not PkgSkip("SPEEDTREE"):
    # If SpeedTree is available, enable it in the config file
    confautoprc = confautoprc.replace('#st#', '')
else:
    # otherwise, disable it.
    confautoprc = confautoprc.replace('#st#', '#')

confautoprc = confautoprc.replace('\r\n', '\n')

if PkgSkip("ASSIMP") or GetLinkAllStatic():
    confautoprc = confautoprc.replace("load-file-type p3assimp", "#load-file-type p3assimp")

if PkgSkip("EGG") or GetLinkAllStatic():
    confautoprc = confautoprc.replace("load-file-type egg pandaegg", "#load-file-type egg pandaegg")

if PkgSkip("PANDATOOL") or PkgSkip("EGG") or GetLinkAllStatic():
    confautoprc = confautoprc.replace("load-file-type p3ptloader", "#load-file-type p3ptloader")

if PkgSkip("FFMPEG") or GetLinkAllStatic():
    confautoprc = confautoprc.replace("load-audio-type * p3ffmpeg", "#load-audio-type * p3ffmpeg")
    confautoprc = confautoprc.replace("load-video-type * p3ffmpeg", "#load-video-type * p3ffmpeg")

if (os.path.isfile("makepanda/myconfig.in")):
    configprc = ReadFile("makepanda/myconfig.in")
else:
    configprc = ReadFile("makepanda/config.in")

configprc = configprc.replace('\r\n', '\n')

if (GetTarget() == 'windows'):
    configprc = configprc.replace("$XDG_CACHE_HOME/panda3d", "$USER_APPDATA/Panda3D-%s" % MAJOR_VERSION)
elif not PkgSkip("X11") and not PkgSkip("GL") and not PkgSkip("EGL") and not GetLinkAllStatic():
    configprc = configprc.replace("#load-display pandadx9", "aux-display p3headlessgl")
else:
    configprc = configprc.replace("aux-display pandadx9", "")

if (GetTarget() == 'darwin'):
    configprc = configprc.replace("$XDG_CACHE_HOME/panda3d", "$HOME/Library/Caches/Panda3D-%s" % MAJOR_VERSION)

if PkgSkip("GL") or GetLinkAllStatic():
    configprc = configprc.replace("\nload-display pandagl", "\n#load-display pandagl")

if PkgSkip("GLES") or GetLinkAllStatic():
    configprc = configprc.replace("\n#load-display pandagles\n", "\n")

if PkgSkip("GL") and not PkgSkip("GLES2") and not GetLinkAllStatic():
    configprc = configprc.replace("\n#load-display pandagles2", "\nload-display pandagles2")
elif PkgSkip("GLES2") or GetLinkAllStatic():
    configprc = configprc.replace("\n#load-display pandagles2", "")

if PkgSkip("DX9") or GetLinkAllStatic():
    configprc = configprc.replace("\n#load-display pandadx9", "")

if PkgSkip("TINYDISPLAY") or GetLinkAllStatic():
    configprc = configprc.replace("\n#load-display p3tinydisplay", "")

if PkgSkip("OPENAL") or GetLinkAllStatic():
    configprc = configprc.replace("audio-library-name p3openal_audio", "#audio-library-name p3openal_audio")

if GetTarget() == 'windows':
    # Convert to Windows newlines.
    ConditionalWriteFile(GetOutputDir()+"/etc/Config.prc", configprc, newline='\r\n')
    ConditionalWriteFile(GetOutputDir()+"/etc/Confauto.prc", confautoprc, newline='\r\n')
else:
    ConditionalWriteFile(GetOutputDir()+"/etc/Config.prc", configprc)
    ConditionalWriteFile(GetOutputDir()+"/etc/Confauto.prc", confautoprc)

##########################################################################################
#
# Copy the precompiled binaries and DLLs into the build.
#
##########################################################################################

tp_dir = GetThirdpartyDir()
if tp_dir is not None:
    dylibs = {}

    if GetTarget() == 'darwin':
        # Make a list of all the dylibs we ship, to figure out whether we should use
        # install_name_tool to correct the library reference to point to our copy.
        for pkg in PkgListGet():
            if PkgSkip(pkg):
                continue

            tp_libdir = os.path.join(tp_dir, pkg.lower(), "lib")
            for lib in glob.glob(os.path.join(tp_libdir, "*.dylib")):
                dylibs[os.path.basename(lib)] = os.path.basename(os.path.realpath(lib))

            if not PkgSkip("PYTHON"):
                for lib in glob.glob(os.path.join(tp_libdir, SDK["PYTHONVERSION"], "*.dylib")):
                    dylibs[os.path.basename(lib)] = os.path.basename(os.path.realpath(lib))

    for pkg in PkgListGet():
        if PkgSkip(pkg):
            continue
        tp_pkg = tp_dir + pkg.lower()

        if GetTarget() == 'windows':
            if os.path.exists(tp_pkg + "/bin"):
                CopyAllFiles(GetOutputDir() + "/bin/", tp_pkg + "/bin/")
                if (PkgSkip("PYTHON")==0 and os.path.exists(tp_pkg + "/bin/" + SDK["PYTHONVERSION"])):
                    CopyAllFiles(GetOutputDir() + "/bin/", tp_pkg + "/bin/" + SDK["PYTHONVERSION"] + "/")

        elif GetTarget() == 'darwin':
            tp_libdir = os.path.join(tp_pkg, "lib")
            tp_libs = glob.glob(os.path.join(tp_libdir, "*.dylib"))

            if not PkgSkip("PYTHON"):
                tp_libs += glob.glob(os.path.join(tp_libdir, SDK["PYTHONVERSION"], "*.dylib"))
                tp_libs += glob.glob(os.path.join(tp_libdir, SDK["PYTHONVERSION"], "*.so"))
                if pkg != 'PYTHON':
                    tp_libs += glob.glob(os.path.join(tp_libdir, SDK["PYTHONVERSION"], "*.py"))

            for tp_lib in tp_libs:
                basename = os.path.basename(tp_lib)
                if basename.endswith('.dylib'):
                    # It's a dynamic link library.  Put it in the lib directory.
                    target = GetOutputDir() + "/lib/" + basename
                    dep_prefix = "@loader_path/../lib/"
                    lib_id = dep_prefix + basename
                else:
                    # It's a Python module, like _rocketcore.so.  Copy it to the root, because
                    # nowadays the 'lib' directory may no longer be on the PYTHONPATH.
                    target = GetOutputDir() + "/" + basename
                    dep_prefix = "@loader_path/lib/"
                    lib_id = basename

                if not NeedsBuild([target], [tp_lib]):
                    continue

                CopyFile(target, tp_lib)
                if os.path.islink(target) or target.endswith('.py'):
                    continue

                # Correct the inter-library dependencies so that the build is relocatable.
                oscmd('install_name_tool -id %s %s' % (lib_id, target))
                oscmd("otool -L %s | grep .dylib > %s/tmp/otool-libs.txt" % (target, GetOutputDir()), True)

                for line in open(GetOutputDir() + "/tmp/otool-libs.txt", "r"):
                    line = line.strip()
                    if not line or line.startswith(dep_prefix) or line.endswith(":"):
                        continue

                    libdep = line.split(" ", 1)[0]
                    dep_basename = os.path.basename(libdep)
                    if dep_basename in dylibs:
                        dep_target = dylibs[dep_basename]
                        oscmd("install_name_tool -change %s %s%s %s" % (libdep, dep_prefix, dep_target, target), True)

                JustBuilt([target], [tp_lib])

            for fwx in glob.glob(tp_pkg + "/*.framework"):
                MakeDirectory(GetOutputDir() + "/Frameworks")
                CopyTree(GetOutputDir() + "/Frameworks/" + os.path.basename(fwx), fwx)

        else:  # Linux / FreeBSD case.
            for tp_lib in glob.glob(tp_pkg + "/lib/*.so*"):
                CopyFile(GetOutputDir() + "/lib/" + os.path.basename(tp_lib), tp_lib)

            if not PkgSkip("PYTHON"):
                for tp_lib in glob.glob(os.path.join(tp_pkg, "lib", SDK["PYTHONVERSION"], "*.so*")):
                    base = os.path.basename(tp_lib)
                    if base.startswith('lib'):
                        CopyFile(GetOutputDir() + "/lib/" + base, tp_lib)
                    else:
                        # It's a Python module, like _rocketcore.so.
                        CopyFile(GetOutputDir() + "/" + base, tp_lib)

    if GetTarget() == 'windows':
        if os.path.isdir(os.path.join(tp_dir, "extras", "bin")):
            CopyAllFiles(GetOutputDir() + "/bin/", tp_dir + "extras/bin/")

        if not PkgSkip("PYTHON"):
            # We need to copy the Python DLL to the bin directory for now.
            pydll = "/" + SDK["PYTHONVERSION"].replace(".", "")
            if GetOptimize() <= 2:
                pydll += "_d.dll"
            else:
                pydll += ".dll"
            CopyFile(GetOutputDir() + "/bin" + pydll, SDK["PYTHON"] + pydll)

            for fn in glob.glob(SDK["PYTHON"] + "/vcruntime*.dll"):
                CopyFile(GetOutputDir() + "/bin/", fn)

            # Copy the whole Python directory.
            if COPY_PYTHON:
                CopyTree(GetOutputDir() + "/python", SDK["PYTHON"])

            # NB: Python does not always ship with the correct manifest/dll.
            # Figure out the correct one to ship, and grab it from WinSxS dir.
            manifest = GetOutputDir() + '/tmp/python.manifest'
            if os.path.isfile(manifest):
                os.unlink(manifest)
            oscmd('mt -inputresource:"%s\\python.exe";#1 -out:"%s" -nologo' % (SDK["PYTHON"], manifest), True)

            if COPY_PYTHON and os.path.isfile(manifest):
                import xml.etree.ElementTree as ET
                tree = ET.parse(manifest)
                idents = tree.findall('./{urn:schemas-microsoft-com:asm.v1}dependency/{urn:schemas-microsoft-com:asm.v1}dependentAssembly/{urn:schemas-microsoft-com:asm.v1}assemblyIdentity')
            else:
                idents = ()

            for ident in idents:
                sxs_name = '_'.join([
                    ident.get('processorArchitecture'),
                    ident.get('name').lower(),
                    ident.get('publicKeyToken'),
                    ident.get('version'),
                ])

                # Find the manifest matching these parameters.
                pattern = os.path.join('C:' + os.sep, 'Windows', 'WinSxS', 'Manifests', sxs_name + '_*.manifest')
                manifests = glob.glob(pattern)
                if not manifests:
                    Warn("Could not locate manifest %s.  You may need to reinstall the Visual C++ Redistributable." % (pattern))
                    continue

                CopyFile(GetOutputDir() + "/python/" + ident.get('name') + ".manifest", manifests[0])

                # Also copy the corresponding msvcr dll.
                pattern = os.path.join('C:' + os.sep, 'Windows', 'WinSxS', sxs_name + '_*', 'msvcr*.dll')
                for file in glob.glob(pattern):
                    CopyFile(GetOutputDir() + "/python/", file)

            # Copy python.exe to ppython.exe.
            if COPY_PYTHON:
                if not os.path.isfile(SDK["PYTHON"] + "/ppython.exe") and os.path.isfile(SDK["PYTHON"] + "/python.exe"):
                    CopyFile(GetOutputDir() + "/python/ppython.exe", SDK["PYTHON"] + "/python.exe")
                if not os.path.isfile(SDK["PYTHON"] + "/ppythonw.exe") and os.path.isfile(SDK["PYTHON"] + "/pythonw.exe"):
                    CopyFile(GetOutputDir() + "/python/ppythonw.exe", SDK["PYTHON"] + "/pythonw.exe")
                ConditionalWriteFile(GetOutputDir() + "/python/panda.pth", "..\n../bin\n")

# Copy over the MSVC runtime.
if GetTarget() == 'windows' and "VISUALSTUDIO" in SDK:
    vcver = "%s%s" % (SDK["MSVC_VERSION"][0], 0)        # ignore minor version.
    crtname = "Microsoft.VC%s.CRT" % (vcver)
    if ("VCTOOLSVERSION" in SDK):
        dir = os.path.join(SDK["VISUALSTUDIO"], "VC", "Redist", "MSVC", SDK["VCTOOLSVERSION"], "onecore", GetTargetArch(), crtname)
    else:
        dir = os.path.join(SDK["VISUALSTUDIO"], "VC", "redist", GetTargetArch(), crtname)

    if os.path.isfile(os.path.join(dir, "msvcr" + vcver + ".dll")):
        CopyFile(GetOutputDir() + "/bin/", os.path.join(dir, "msvcr" + vcver + ".dll"))
    if os.path.isfile(os.path.join(dir, "msvcp" + vcver + ".dll")):
        CopyFile(GetOutputDir() + "/bin/", os.path.join(dir, "msvcp" + vcver + ".dll"))
    if os.path.isfile(os.path.join(dir, "vcruntime" + vcver + ".dll")):
        CopyFile(GetOutputDir() + "/bin/", os.path.join(dir, "vcruntime" + vcver + ".dll"))

########################################################################
##
## Copy various stuff into the build.
##
########################################################################

if GetTarget() == 'windows':
    # Convert to Windows newlines so they can be opened by notepad.
    WriteFile(GetOutputDir() + "/LICENSE", ReadFile("doc/LICENSE"), newline='\r\n')
    WriteFile(GetOutputDir() + "/ReleaseNotes", ReadFile("doc/ReleaseNotes"), newline='\r\n')
    CopyFile(GetOutputDir() + "/pandaIcon.ico", "panda/src/configfiles/pandaIcon.ico")
else:
    CopyFile(GetOutputDir()+"/", "doc/LICENSE")
    CopyFile(GetOutputDir()+"/", "doc/ReleaseNotes")

if not PkgSkip("PYTHON") and os.path.isdir(GetThirdpartyBase() + "/Pmw"):
    CopyTree(GetOutputDir() + "/Pmw", GetThirdpartyBase() + "/Pmw", exclude=["Pmw_1_3", "Pmw_1_3_3"])

# Since Eigen is included by all sorts of core headers, as a convenience
# to C++ users on Win and Mac, we include it in the Panda include directory.
if not PkgSkip("EIGEN") and GetTarget() in ("windows", "darwin") and GetThirdpartyDir():
    CopyTree(GetOutputDir()+'/include/Eigen', GetThirdpartyDir()+'eigen/include/Eigen')

########################################################################
#
# Copy header files to the built/include/parser-inc directory.
#
########################################################################

CopyTree(GetOutputDir()+'/include/parser-inc','dtool/src/parser-inc')
DeleteVCS(GetOutputDir()+'/include/parser-inc')

########################################################################
#
# Transfer all header files to the built/include directory.
#
########################################################################

CopyAllHeaders('dtool/src/dtoolbase')
CopyAllHeaders('dtool/src/dtoolutil', skip=["pandaVersion.h", "checkPandaVersion.h"])
CopyFile(GetOutputDir()+'/include/','dtool/src/dtoolutil/vector_src.cxx')
CopyAllHeaders('dtool/metalibs/dtool')
CopyAllHeaders('dtool/src/prc', skip=["prc_parameters.h"])
CopyAllHeaders('dtool/src/dconfig')
CopyAllHeaders('dtool/src/interrogatedb')
CopyAllHeaders('dtool/metalibs/dtoolconfig')
CopyAllHeaders('panda/src/putil')
CopyAllHeaders('panda/src/pandabase')
CopyAllHeaders('panda/src/express')
CopyAllHeaders('panda/src/downloader')
CopyAllHeaders('panda/metalibs/pandaexpress')

CopyAllHeaders('panda/src/pipeline')
CopyAllHeaders('panda/src/linmath')
CopyAllHeaders('panda/src/putil')
CopyAllHeaders('dtool/src/prckeys')
CopyAllHeaders('panda/src/audio')
CopyAllHeaders('panda/src/event')
CopyAllHeaders('panda/src/mathutil')
CopyAllHeaders('panda/src/gsgbase')
CopyAllHeaders('panda/src/pnmimage')
CopyAllHeaders('panda/src/nativenet')
CopyAllHeaders('panda/src/net')
CopyAllHeaders('panda/src/pstatclient')
CopyAllHeaders('panda/src/gobj')
CopyAllHeaders('panda/src/movies')
CopyAllHeaders('panda/src/pgraphnodes')
CopyAllHeaders('panda/src/pgraph')
CopyAllHeaders('panda/src/cull')
CopyAllHeaders('panda/src/display')
CopyAllHeaders('panda/src/chan')
CopyAllHeaders('panda/src/char')
CopyAllHeaders('panda/src/dgraph')
CopyAllHeaders('panda/src/device')
CopyAllHeaders('panda/src/pnmtext')
CopyAllHeaders('panda/src/text')
CopyAllHeaders('panda/src/grutil')
if not PkgSkip("VISION"):
    CopyAllHeaders('panda/src/vision')
if not PkgSkip("FFMPEG"):
    CopyAllHeaders('panda/src/ffmpeg')
CopyAllHeaders('panda/src/tform')
CopyAllHeaders('panda/src/collide')
CopyAllHeaders('panda/src/parametrics')
CopyAllHeaders('panda/src/pgui')
CopyAllHeaders('panda/src/pnmimagetypes')
CopyAllHeaders('panda/src/recorder')
if not PkgSkip("VRPN"):
    CopyAllHeaders('panda/src/vrpn')
CopyAllHeaders('panda/src/wgldisplay')
CopyAllHeaders('panda/src/ode')
CopyAllHeaders('panda/metalibs/pandaode')
if not PkgSkip("PANDAPHYSICS"):
    CopyAllHeaders('panda/src/physics')
    if not PkgSkip("PANDAPARTICLESYSTEM"):
        CopyAllHeaders('panda/src/particlesystem')
CopyAllHeaders('panda/metalibs/panda')
CopyAllHeaders('panda/src/audiotraits')
CopyAllHeaders('panda/src/audiotraits')
CopyAllHeaders('panda/src/distort')
CopyAllHeaders('panda/src/downloadertools')
CopyAllHeaders('panda/src/windisplay')
CopyAllHeaders('panda/src/dxgsg9')
CopyAllHeaders('panda/metalibs/pandadx9')
if not PkgSkip("EGG"):
    CopyAllHeaders('panda/src/egg')
    CopyAllHeaders('panda/src/egg2pg')
CopyAllHeaders('panda/src/framework')
CopyAllHeaders('panda/metalibs/pandafx')
CopyAllHeaders('panda/src/glstuff')
CopyAllHeaders('panda/src/glgsg')
CopyAllHeaders('panda/src/glesgsg')
CopyAllHeaders('panda/src/gles2gsg')
if not PkgSkip("EGG"):
    CopyAllHeaders('panda/metalibs/pandaegg')
if GetTarget() == 'windows':
    CopyAllHeaders('panda/src/wgldisplay')
elif GetTarget() == 'darwin':
    CopyAllHeaders('panda/src/cocoadisplay')
    if not PkgSkip('GL'):
        CopyAllHeaders('panda/src/cocoagldisplay')
elif GetTarget() == 'android':
    CopyAllHeaders('panda/src/android')
    CopyAllHeaders('panda/src/androiddisplay')
if not PkgSkip('X11'):
    CopyAllHeaders('panda/src/x11display')
    if not PkgSkip('GL'):
        CopyAllHeaders('panda/src/glxdisplay')
CopyAllHeaders('panda/src/egldisplay')
CopyAllHeaders('panda/metalibs/pandagl')
CopyAllHeaders('panda/metalibs/pandagles')
CopyAllHeaders('panda/metalibs/pandagles2')

CopyAllHeaders('panda/metalibs/pandaphysics')
CopyAllHeaders('panda/src/testbed')

if not PkgSkip("BULLET"):
    CopyAllHeaders('panda/src/bullet')
    CopyAllHeaders('panda/metalibs/pandabullet')

if not PkgSkip("SPEEDTREE"):
    CopyAllHeaders('contrib/src/speedtree')

if not PkgSkip("DIRECT"):
    CopyAllHeaders('direct/src/directbase')
    CopyAllHeaders('direct/src/dcparser')
    CopyAllHeaders('direct/src/deadrec')
    CopyAllHeaders('direct/src/distributed')
    CopyAllHeaders('direct/src/interval')
    CopyAllHeaders('direct/src/showbase')
    CopyAllHeaders('direct/src/motiontrail')
    CopyAllHeaders('direct/src/dcparse')

if not PkgSkip("NAMETAG") or not PkgSkip("MOVEMENT") or not PkgSkip("NAVIGATION"):
    CopyAllHeaders('panda/src/otpbase')
    if not PkgSkip("NAMETAG"):
        CopyAllHeaders('panda/src/nametag')
    if not PkgSkip("MOVEMENT"):
        CopyAllHeaders('panda/src/movement')
    if not PkgSkip("NAVIGATION"):
        CopyAllHeaders('panda/src/navigation')

if not PkgSkip("DNA") or not PkgSkip("SUIT") or not PkgSkip("PETS"):
    CopyAllHeaders('panda/src/toontownbase')
    if not PkgSkip("DNA"):
        CopyAllHeaders('panda/src/dna')
    if not PkgSkip("SUIT"):
        CopyAllHeaders('panda/src/suit')
    if not PkgSkip("PETS"):
        CopyAllHeaders('panda/src/pets')

if not PkgSkip("PANDATOOL"):
    CopyAllHeaders('pandatool/src/pandatoolbase')
    CopyAllHeaders('pandatool/src/converter')
    CopyAllHeaders('pandatool/src/progbase')
    CopyAllHeaders('pandatool/src/eggbase')
    CopyAllHeaders('pandatool/src/bam')
    CopyAllHeaders('pandatool/src/daeegg')
    CopyAllHeaders('pandatool/src/daeprogs')
    CopyAllHeaders('pandatool/src/dxf')
    CopyAllHeaders('pandatool/src/dxfegg')
    CopyAllHeaders('pandatool/src/dxfprogs')
    CopyAllHeaders('pandatool/src/palettizer')
    CopyAllHeaders('pandatool/src/egg-mkfont')
    CopyAllHeaders('pandatool/src/eggcharbase')
    CopyAllHeaders('pandatool/src/egg-optchar')
    CopyAllHeaders('pandatool/src/egg-palettize')
    CopyAllHeaders('pandatool/src/egg-qtess')
    CopyAllHeaders('pandatool/src/eggprogs')
    CopyAllHeaders('pandatool/src/flt')
    CopyAllHeaders('pandatool/src/fltegg')
    CopyAllHeaders('pandatool/src/fltprogs')
    CopyAllHeaders('pandatool/src/imagebase')
    CopyAllHeaders('pandatool/src/imageprogs')
    CopyAllHeaders('pandatool/src/pfmprogs')
    CopyAllHeaders('pandatool/src/lwo')
    CopyAllHeaders('pandatool/src/lwoegg')
    CopyAllHeaders('pandatool/src/lwoprogs')
    CopyAllHeaders('pandatool/src/objegg')
    CopyAllHeaders('pandatool/src/objprogs')
    CopyAllHeaders('pandatool/src/vrml')
    CopyAllHeaders('pandatool/src/vrmlegg')
    CopyAllHeaders('pandatool/src/xfile')
    CopyAllHeaders('pandatool/src/xfileegg')
    CopyAllHeaders('pandatool/src/ptloader')
    CopyAllHeaders('pandatool/src/miscprogs')
    CopyAllHeaders('pandatool/src/pstatserver')
    CopyAllHeaders('pandatool/src/text-stats')
    CopyAllHeaders('pandatool/src/vrmlprogs')
    CopyAllHeaders('pandatool/src/win-stats')
    CopyAllHeaders('pandatool/src/xfileprogs')
    if not PkgSkip("DNA"):
        CopyAllHeaders('pandatool/src/dnaprogs')

if not PkgSkip("CONTRIB"):
    CopyAllHeaders('contrib/src/contribbase')
    CopyAllHeaders('contrib/src/ai')

########################################################################
#
# These definitions are syntactic shorthand.  They make it easy
# to link with the usual libraries without listing them all.
#
########################################################################

COMMON_DTOOL_LIBS=[
    'libp3dtool.dll',
    'libp3dtoolconfig.dll',
]

COMMON_PANDA_LIBS=[
    'libpanda.dll',
    'libpandaexpress.dll'
] + COMMON_DTOOL_LIBS

COMMON_EGG2X_LIBS=[
    'libp3eggbase.lib',
    'libp3progbase.lib',
    'libp3converter.lib',
    'libp3pandatoolbase.lib',
    'libpandaegg.dll',
] + COMMON_PANDA_LIBS

########################################################################
#
# This section contains a list of all the files that need to be compiled.
#
########################################################################

print("Generating dependencies...")
sys.stdout.flush()

#
# Compile Panda icon resource file.
# We do it first because we need it at
# the time we compile an executable.
#

if GetTarget() == 'windows':
    OPTS=['DIR:panda/src/configfiles']
    TargetAdd('pandaIcon.res', opts=OPTS, input='pandaIcon.rc')

#
# DIRECTORY: dtool/src/dtoolbase/
#

OPTS=['DIR:dtool/src/dtoolbase', 'BUILDING:DTOOL', 'MIMALLOC']
TargetAdd('p3dtoolbase_composite1.obj', opts=OPTS, input='p3dtoolbase_composite1.cxx')
TargetAdd('p3dtoolbase_composite2.obj', opts=OPTS, input='p3dtoolbase_composite2.cxx')
TargetAdd('p3dtoolbase_lookup3.obj',    opts=OPTS, input='lookup3.c')
TargetAdd('p3dtoolbase_indent.obj',     opts=OPTS, input='indent.cxx')

#
# DIRECTORY: dtool/src/dtoolutil/
#

OPTS=['DIR:dtool/src/dtoolutil', 'BUILDING:DTOOL']
TargetAdd('p3dtoolutil_composite1.obj', opts=OPTS, input='p3dtoolutil_composite1.cxx')
TargetAdd('p3dtoolutil_composite2.obj', opts=OPTS, input='p3dtoolutil_composite2.cxx')
if GetTarget() == 'darwin':
    TargetAdd('p3dtoolutil_filename_assist.obj', opts=OPTS, input='filename_assist.mm')

#
# DIRECTORY: dtool/metalibs/dtool/
#

OPTS=['DIR:dtool/metalibs/dtool', 'BUILDING:DTOOL']
TargetAdd('p3dtool_dtool.obj', opts=OPTS, input='dtool.cxx')
TargetAdd('libp3dtool.dll', input='p3dtool_dtool.obj')
TargetAdd('libp3dtool.dll', input='p3dtoolutil_composite1.obj')
TargetAdd('libp3dtool.dll', input='p3dtoolutil_composite2.obj')
if GetTarget() == 'darwin':
    TargetAdd('libp3dtool.dll', input='p3dtoolutil_filename_assist.obj')
TargetAdd('libp3dtool.dll', input='p3dtoolbase_composite1.obj')
TargetAdd('libp3dtool.dll', input='p3dtoolbase_composite2.obj')
TargetAdd('libp3dtool.dll', input='p3dtoolbase_indent.obj')
TargetAdd('libp3dtool.dll', input='p3dtoolbase_lookup3.obj')
TargetAdd('libp3dtool.dll', opts=['ADVAPI','WINSHELL','WINKERNEL','MIMALLOC'])

#
# DIRECTORY: dtool/src/prc/
#

OPTS=['DIR:dtool/src/prc', 'BUILDING:DTOOLCONFIG', 'OPENSSL']
TargetAdd('p3prc_composite1.obj', opts=OPTS, input='p3prc_composite1.cxx')
TargetAdd('p3prc_composite2.obj', opts=OPTS, input='p3prc_composite2.cxx')

#
# DIRECTORY: dtool/metalibs/dtoolconfig/
#

OPTS=['DIR:dtool/metalibs/dtoolconfig', 'BUILDING:DTOOLCONFIG']
TargetAdd('p3dtoolconfig_dtoolconfig.obj', opts=OPTS, input='dtoolconfig.cxx')
TargetAdd('libp3dtoolconfig.dll', input='p3dtoolconfig_dtoolconfig.obj')
TargetAdd('libp3dtoolconfig.dll', input='p3prc_composite1.obj')
TargetAdd('libp3dtoolconfig.dll', input='p3prc_composite2.obj')
TargetAdd('libp3dtoolconfig.dll', input='libp3dtool.dll')
TargetAdd('libp3dtoolconfig.dll', opts=['ADVAPI', 'OPENSSL', 'WINGDI', 'WINUSER'])

#
# DIRECTORY: dtool/src/prckeys/
#

if not PkgSkip("OPENSSL"):
    OPTS=['DIR:dtool/src/prckeys', 'OPENSSL']
    TargetAdd('make-prc-key_makePrcKey.obj', opts=OPTS, input='makePrcKey.cxx')
    TargetAdd('make-prc-key.exe', input='make-prc-key_makePrcKey.obj')
    TargetAdd('make-prc-key.exe', input=COMMON_DTOOL_LIBS)
    TargetAdd('make-prc-key.exe', opts=['ADVAPI', 'OPENSSL', 'WINSHELL', 'WINGDI', 'WINUSER'])

#
# DIRECTORY: dtool/src/dtoolbase/
#

OPTS=['DIR:dtool/src/dtoolbase']
IGATEFILES=GetDirectoryContents('dtool/src/dtoolbase', ["*_composite*.cxx"])
IGATEFILES += [
    "typeHandle.h",
    "typeHandle_ext.h",
    "typeRegistry.h",
    "typedObject.h",
    "neverFreeMemory.h",
]
TargetAdd('libp3dtoolbase.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3dtoolbase.in', opts=['IMOD:panda3d.core', 'ILIB:libp3dtoolbase', 'SRCDIR:dtool/src/dtoolbase'])
PyTargetAdd('p3dtoolbase_typeHandle_ext.obj', opts=OPTS, input='typeHandle_ext.cxx')

#
# DIRECTORY: dtool/src/dtoolutil/
#

OPTS=['DIR:dtool/src/dtoolutil']
IGATEFILES=GetDirectoryContents('dtool/src/dtoolutil', ["*_composite*.cxx"])
IGATEFILES += [
    "config_dtoolutil.h",
    "pandaSystem.h",
    "dSearchPath.h",
    "executionEnvironment.h",
    "textEncoder.h",
    "textEncoder_ext.h",
    "filename.h",
    "filename_ext.h",
    "globPattern.h",
    "globPattern_ext.h",
    "pandaFileStream.h",
    "lineStream.h",
    "iostream_ext.h",
]
TargetAdd('libp3dtoolutil.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3dtoolutil.in', opts=['IMOD:panda3d.core', 'ILIB:libp3dtoolutil', 'SRCDIR:dtool/src/dtoolutil'])
PyTargetAdd('p3dtoolutil_ext_composite.obj', opts=OPTS, input='p3dtoolutil_ext_composite.cxx')

#
# DIRECTORY: dtool/src/prc/
#

OPTS=['DIR:dtool/src/prc']
IGATEFILES=GetDirectoryContents('dtool/src/prc', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3prc.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3prc.in', opts=['IMOD:panda3d.core', 'ILIB:libp3prc', 'SRCDIR:dtool/src/prc'])
PyTargetAdd('p3prc_ext_composite.obj', opts=OPTS, input='p3prc_ext_composite.cxx')

#
# DIRECTORY: panda/src/pandabase/
#

OPTS=['DIR:panda/src/pandabase', 'BUILDING:PANDAEXPRESS']
TargetAdd('p3pandabase_pandabase.obj', opts=OPTS, input='pandabase.cxx')

#
# DIRECTORY: panda/src/express/
#

OPTS=['DIR:panda/src/express', 'BUILDING:PANDAEXPRESS', 'OPENSSL', 'ZLIB']
TargetAdd('p3express_composite1.obj', opts=OPTS, input='p3express_composite1.cxx')
TargetAdd('p3express_composite2.obj', opts=OPTS, input='p3express_composite2.cxx')

OPTS=['DIR:panda/src/express', 'OPENSSL', 'ZLIB']
IGATEFILES=GetDirectoryContents('panda/src/express', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3express.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3express.in', opts=['IMOD:panda3d.core', 'ILIB:libp3express', 'SRCDIR:panda/src/express'])
PyTargetAdd('p3express_ext_composite.obj', opts=OPTS, input='p3express_ext_composite.cxx')

#
# DIRECTORY: panda/src/downloader/
#

OPTS=['DIR:panda/src/downloader', 'BUILDING:PANDAEXPRESS', 'OPENSSL', 'ZLIB']
TargetAdd('p3downloader_composite1.obj', opts=OPTS, input='p3downloader_composite1.cxx')
TargetAdd('p3downloader_composite2.obj', opts=OPTS, input='p3downloader_composite2.cxx')

OPTS=['DIR:panda/src/downloader', 'OPENSSL', 'ZLIB']
IGATEFILES=GetDirectoryContents('panda/src/downloader', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3downloader.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3downloader.in', opts=['IMOD:panda3d.core', 'ILIB:libp3downloader', 'SRCDIR:panda/src/downloader'])

#
# DIRECTORY: panda/metalibs/pandaexpress/
#

OPTS=['DIR:panda/metalibs/pandaexpress', 'BUILDING:PANDAEXPRESS', 'ZLIB']
TargetAdd('pandaexpress_pandaexpress.obj', opts=OPTS, input='pandaexpress.cxx')
TargetAdd('libpandaexpress.dll', input='pandaexpress_pandaexpress.obj')
TargetAdd('libpandaexpress.dll', input='p3downloader_composite1.obj')
TargetAdd('libpandaexpress.dll', input='p3downloader_composite2.obj')
TargetAdd('libpandaexpress.dll', input='p3express_composite1.obj')
TargetAdd('libpandaexpress.dll', input='p3express_composite2.obj')
TargetAdd('libpandaexpress.dll', input='p3pandabase_pandabase.obj')
TargetAdd('libpandaexpress.dll', input=COMMON_DTOOL_LIBS)
TargetAdd('libpandaexpress.dll', opts=['ADVAPI', 'WINSOCK2', 'OPENSSL', 'ZLIB', 'WINGDI', 'WINUSER', 'ANDROID'])

#
# DIRECTORY: panda/src/pipeline/
#

OPTS=['DIR:panda/src/pipeline', 'BUILDING:PANDA']
TargetAdd('p3pipeline_composite1.obj', opts=OPTS, input='p3pipeline_composite1.cxx')
TargetAdd('p3pipeline_composite2.obj', opts=OPTS, input='p3pipeline_composite2.cxx')
TargetAdd('p3pipeline_contextSwitch.obj', opts=OPTS, input='contextSwitch.c')

OPTS=['DIR:panda/src/pipeline']
IGATEFILES=GetDirectoryContents('panda/src/pipeline', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3pipeline.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3pipeline.in', opts=['IMOD:panda3d.core', 'ILIB:libp3pipeline', 'SRCDIR:panda/src/pipeline'])
PyTargetAdd('p3pipeline_pythonThread.obj', opts=OPTS, input='pythonThread.cxx')

#
# DIRECTORY: panda/src/linmath/
#

OPTS=['DIR:panda/src/linmath', 'BUILDING:PANDA']
TargetAdd('p3linmath_composite1.obj', opts=OPTS, input='p3linmath_composite1.cxx')
TargetAdd('p3linmath_composite2.obj', opts=OPTS, input='p3linmath_composite2.cxx')

OPTS=['DIR:panda/src/linmath']
IGATEFILES=GetDirectoryContents('panda/src/linmath', ["*.h", "*_composite*.cxx"])
for ifile in IGATEFILES[:]:
    if "_src." in ifile:
        IGATEFILES.remove(ifile)
IGATEFILES.remove('cast_to_double.h')
IGATEFILES.remove('lmat_ops.h')
IGATEFILES.remove('cast_to_float.h')
TargetAdd('libp3linmath.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3linmath.in', opts=['IMOD:panda3d.core', 'ILIB:libp3linmath', 'SRCDIR:panda/src/linmath'])

#
# DIRECTORY: panda/src/putil/
#

OPTS=['DIR:panda/src/putil', 'BUILDING:PANDA', 'ZLIB']
TargetAdd('p3putil_composite1.obj', opts=OPTS, input='p3putil_composite1.cxx')
TargetAdd('p3putil_composite2.obj', opts=OPTS, input='p3putil_composite2.cxx')

OPTS=['DIR:panda/src/putil', 'ZLIB']
IGATEFILES=GetDirectoryContents('panda/src/putil', ["*.h", "*_composite*.cxx"])
IGATEFILES.remove("test_bam.h")
TargetAdd('libp3putil.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3putil.in', opts=['IMOD:panda3d.core', 'ILIB:libp3putil', 'SRCDIR:panda/src/putil'])
PyTargetAdd('p3putil_ext_composite.obj', opts=OPTS, input='p3putil_ext_composite.cxx')

#
# DIRECTORY: panda/src/audio/
#

OPTS=['DIR:panda/src/audio', 'BUILDING:PANDA']
TargetAdd('p3audio_composite1.obj', opts=OPTS, input='p3audio_composite1.cxx')

OPTS=['DIR:panda/src/audio']
IGATEFILES=["audio.h"]
TargetAdd('libp3audio.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3audio.in', opts=['IMOD:panda3d.core', 'ILIB:libp3audio', 'SRCDIR:panda/src/audio'])

#
# DIRECTORY: panda/src/event/
#

OPTS=['DIR:panda/src/event', 'BUILDING:PANDA']
TargetAdd('p3event_composite1.obj', opts=OPTS, input='p3event_composite1.cxx')
TargetAdd('p3event_composite2.obj', opts=OPTS, input='p3event_composite2.cxx')

OPTS=['DIR:panda/src/event']
PyTargetAdd('p3event_asyncFuture_ext.obj', opts=OPTS, input='asyncFuture_ext.cxx')
PyTargetAdd('p3event_pythonTask.obj', opts=OPTS, input='pythonTask.cxx')
IGATEFILES=GetDirectoryContents('panda/src/event', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3event.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3event.in', opts=['IMOD:panda3d.core', 'ILIB:libp3event', 'SRCDIR:panda/src/event'])

#
# DIRECTORY: panda/src/mathutil/
#

OPTS=['DIR:panda/src/mathutil', 'BUILDING:PANDA', 'FFTW']
TargetAdd('p3mathutil_composite1.obj', opts=OPTS, input='p3mathutil_composite1.cxx')
TargetAdd('p3mathutil_composite2.obj', opts=OPTS, input='p3mathutil_composite2.cxx')

OPTS=['DIR:panda/src/mathutil', 'FFTW']
IGATEFILES=GetDirectoryContents('panda/src/mathutil', ["*.h", "*_composite*.cxx"])
for ifile in IGATEFILES[:]:
    if "_src." in ifile:
        IGATEFILES.remove(ifile)
TargetAdd('libp3mathutil.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3mathutil.in', opts=['IMOD:panda3d.core', 'ILIB:libp3mathutil', 'SRCDIR:panda/src/mathutil'])

#
# DIRECTORY: panda/src/gsgbase/
#

OPTS=['DIR:panda/src/gsgbase', 'BUILDING:PANDA']
TargetAdd('p3gsgbase_composite1.obj', opts=OPTS, input='p3gsgbase_composite1.cxx')

OPTS=['DIR:panda/src/gsgbase']
IGATEFILES=GetDirectoryContents('panda/src/gsgbase', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3gsgbase.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3gsgbase.in', opts=['IMOD:panda3d.core', 'ILIB:libp3gsgbase', 'SRCDIR:panda/src/gsgbase'])

#
# DIRECTORY: panda/src/pnmimage/
#

OPTS=['DIR:panda/src/pnmimage', 'BUILDING:PANDA', 'ZLIB']
TargetAdd('p3pnmimage_composite1.obj', opts=OPTS, input='p3pnmimage_composite1.cxx')
TargetAdd('p3pnmimage_composite2.obj', opts=OPTS, input='p3pnmimage_composite2.cxx')

if GetTarget() != "emscripten":
  TargetAdd('p3pnmimage_convert_srgb_sse2.obj', opts=OPTS+['SSE2'], input='convert_srgb_sse2.cxx')

OPTS=['DIR:panda/src/pnmimage', 'ZLIB']
IGATEFILES=GetDirectoryContents('panda/src/pnmimage', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3pnmimage.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3pnmimage.in', opts=['IMOD:panda3d.core', 'ILIB:libp3pnmimage', 'SRCDIR:panda/src/pnmimage'])
PyTargetAdd('p3pnmimage_pfmFile_ext.obj', opts=OPTS, input='pfmFile_ext.cxx')

#
# DIRECTORY: panda/src/nativenet/
#

if GetTarget() != 'emscripten':
  OPTS=['DIR:panda/src/nativenet', 'BUILDING:PANDA']
  TargetAdd('p3nativenet_composite1.obj', opts=OPTS, input='p3nativenet_composite1.cxx')

OPTS=['DIR:panda/src/nativenet']
IGATEFILES=GetDirectoryContents('panda/src/nativenet', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3nativenet.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3nativenet.in', opts=['IMOD:panda3d.net', 'ILIB:libp3nativenet', 'SRCDIR:panda/src/nativenet'])

#
# DIRECTORY: panda/src/net/
#

if GetTarget() != 'emscripten':
  OPTS=['DIR:panda/src/net', 'BUILDING:PANDA']
  TargetAdd('p3net_composite1.obj', opts=OPTS, input='p3net_composite1.cxx')
  TargetAdd('p3net_composite2.obj', opts=OPTS, input='p3net_composite2.cxx')

OPTS=['DIR:panda/src/net']
IGATEFILES=GetDirectoryContents('panda/src/net', ["*.h", "*_composite*.cxx"])
IGATEFILES.remove("datagram_ui.h")
TargetAdd('libp3net.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3net.in', opts=['IMOD:panda3d.net', 'ILIB:libp3net', 'SRCDIR:panda/src/net'])

#
# DIRECTORY: panda/src/pstatclient/
#

OPTS=['DIR:panda/src/pstatclient', 'BUILDING:PANDA']
TargetAdd('p3pstatclient_composite1.obj', opts=OPTS, input='p3pstatclient_composite1.cxx')
TargetAdd('p3pstatclient_composite2.obj', opts=OPTS, input='p3pstatclient_composite2.cxx')

OPTS=['DIR:panda/src/pstatclient']
IGATEFILES=GetDirectoryContents('panda/src/pstatclient', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3pstatclient.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3pstatclient.in', opts=['IMOD:panda3d.core', 'ILIB:libp3pstatclient', 'SRCDIR:panda/src/pstatclient'])
PyTargetAdd('p3pstatclient_pStatClient_ext.obj', opts=OPTS, input='pStatClient_ext.cxx')

#
# DIRECTORY: panda/src/gobj/
#

OPTS=['DIR:panda/src/gobj', 'BUILDING:PANDA', 'NVIDIACG', 'ZLIB', 'SQUISH']
TargetAdd('p3gobj_composite1.obj', opts=OPTS, input='p3gobj_composite1.cxx')
TargetAdd('p3gobj_composite2.obj', opts=OPTS+['BIGOBJ'], input='p3gobj_composite2.cxx')

OPTS=['DIR:panda/src/gobj', 'NVIDIACG', 'ZLIB', 'SQUISH']
IGATEFILES=GetDirectoryContents('panda/src/gobj', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3gobj.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3gobj.in', opts=['IMOD:panda3d.core', 'ILIB:libp3gobj', 'SRCDIR:panda/src/gobj'])
PyTargetAdd('p3gobj_ext_composite.obj', opts=OPTS, input='p3gobj_ext_composite.cxx')

#
# DIRECTORY: panda/src/pgraphnodes/
#

OPTS=['DIR:panda/src/pgraphnodes', 'BUILDING:PANDA']
TargetAdd('p3pgraphnodes_composite1.obj', opts=OPTS, input='p3pgraphnodes_composite1.cxx')
TargetAdd('p3pgraphnodes_composite2.obj', opts=OPTS, input='p3pgraphnodes_composite2.cxx')

OPTS=['DIR:panda/src/pgraphnodes']
IGATEFILES=GetDirectoryContents('panda/src/pgraphnodes', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3pgraphnodes.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3pgraphnodes.in', opts=['IMOD:panda3d.core', 'ILIB:libp3pgraphnodes', 'SRCDIR:panda/src/pgraphnodes'])

#
# DIRECTORY: panda/src/pgraph/
#

OPTS=['DIR:panda/src/pgraph', 'BUILDING:PANDA']
TargetAdd('p3pgraph_nodePath.obj', opts=OPTS, input='nodePath.cxx')
TargetAdd('p3pgraph_composite1.obj', opts=OPTS, input='p3pgraph_composite1.cxx')
TargetAdd('p3pgraph_composite2.obj', opts=OPTS, input='p3pgraph_composite2.cxx')
TargetAdd('p3pgraph_composite3.obj', opts=OPTS, input='p3pgraph_composite3.cxx')
TargetAdd('p3pgraph_composite4.obj', opts=OPTS, input='p3pgraph_composite4.cxx')

OPTS=['DIR:panda/src/pgraph']
IGATEFILES=GetDirectoryContents('panda/src/pgraph', ["*.h", "nodePath.cxx", "*_composite*.cxx"])
TargetAdd('libp3pgraph.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3pgraph.in', opts=['IMOD:panda3d.core', 'ILIB:libp3pgraph', 'SRCDIR:panda/src/pgraph'])
PyTargetAdd('p3pgraph_ext_composite.obj', opts=OPTS, input='p3pgraph_ext_composite.cxx')

#
# DIRECTORY: panda/src/cull/
#

OPTS=['DIR:panda/src/cull', 'BUILDING:PANDA']
TargetAdd('p3cull_composite1.obj', opts=OPTS, input='p3cull_composite1.cxx')
TargetAdd('p3cull_composite2.obj', opts=OPTS, input='p3cull_composite2.cxx')

OPTS=['DIR:panda/src/cull']
IGATEFILES=GetDirectoryContents('panda/src/cull', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3cull.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3cull.in', opts=['IMOD:panda3d.core', 'ILIB:libp3cull', 'SRCDIR:panda/src/cull'])

#
# DIRECTORY: panda/src/dgraph/
#

OPTS=['DIR:panda/src/dgraph', 'BUILDING:PANDA']
TargetAdd('p3dgraph_composite1.obj', opts=OPTS, input='p3dgraph_composite1.cxx')
TargetAdd('p3dgraph_composite2.obj', opts=OPTS, input='p3dgraph_composite2.cxx')

OPTS=['DIR:panda/src/dgraph']
IGATEFILES=GetDirectoryContents('panda/src/dgraph', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3dgraph.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3dgraph.in', opts=['IMOD:panda3d.core', 'ILIB:libp3dgraph', 'SRCDIR:panda/src/dgraph'])

#
# DIRECTORY: panda/src/device/
#

OPTS=['DIR:panda/src/device', 'BUILDING:PANDA']
TargetAdd('p3device_composite1.obj', opts=OPTS, input='p3device_composite1.cxx')
TargetAdd('p3device_composite2.obj', opts=OPTS, input='p3device_composite2.cxx')

OPTS=['DIR:panda/src/device']
IGATEFILES=GetDirectoryContents('panda/src/device', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3device.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3device.in', opts=['IMOD:panda3d.core', 'ILIB:libp3device', 'SRCDIR:panda/src/device'])

#
# DIRECTORY: panda/src/display/
#

OPTS=['DIR:panda/src/display', 'BUILDING:PANDA', 'X11']
TargetAdd('p3display_graphicsStateGuardian.obj', opts=OPTS, input='graphicsStateGuardian.cxx')
TargetAdd('p3display_composite1.obj', opts=OPTS, input='p3display_composite1.cxx')
TargetAdd('p3display_composite2.obj', opts=OPTS, input='p3display_composite2.cxx')

OPTS=['DIR:panda/src/display', 'X11']
IGATEFILES=GetDirectoryContents('panda/src/display', ["*.h", "*_composite*.cxx"])
IGATEFILES.remove("renderBuffer.h")
TargetAdd('libp3display.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3display.in', opts=['IMOD:panda3d.core', 'ILIB:libp3display', 'SRCDIR:panda/src/display'])
PyTargetAdd('p3display_ext_composite.obj', opts=OPTS, input='p3display_ext_composite.cxx')

#
# DIRECTORY: panda/src/chan/
#

OPTS=['DIR:panda/src/chan', 'BUILDING:PANDA']
TargetAdd('p3chan_composite1.obj', opts=OPTS, input='p3chan_composite1.cxx')
TargetAdd('p3chan_composite2.obj', opts=OPTS, input='p3chan_composite2.cxx')

OPTS=['DIR:panda/src/chan']
IGATEFILES=GetDirectoryContents('panda/src/chan', ["*.h", "*_composite*.cxx"])
IGATEFILES.remove('movingPart.h')
IGATEFILES.remove('animChannelFixed.h')
TargetAdd('libp3chan.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3chan.in', opts=['IMOD:panda3d.core', 'ILIB:libp3chan', 'SRCDIR:panda/src/chan'])


# DIRECTORY: panda/src/char/
#

OPTS=['DIR:panda/src/char', 'BUILDING:PANDA']
TargetAdd('p3char_composite1.obj', opts=OPTS, input='p3char_composite1.cxx')
TargetAdd('p3char_composite2.obj', opts=OPTS, input='p3char_composite2.cxx')

OPTS=['DIR:panda/src/char']
IGATEFILES=GetDirectoryContents('panda/src/char', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3char.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3char.in', opts=['IMOD:panda3d.core', 'ILIB:libp3char', 'SRCDIR:panda/src/char'])

#
# DIRECTORY: panda/src/pnmtext/
#

if not PkgSkip("FREETYPE"):
    OPTS=['DIR:panda/src/pnmtext', 'BUILDING:PANDA', 'FREETYPE']
    TargetAdd('p3pnmtext_composite1.obj', opts=OPTS, input='p3pnmtext_composite1.cxx')

    OPTS=['DIR:panda/src/pnmtext', 'FREETYPE']
    IGATEFILES=GetDirectoryContents('panda/src/pnmtext', ["*.h", "*_composite*.cxx"])
    TargetAdd('libp3pnmtext.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3pnmtext.in', opts=['IMOD:panda3d.core', 'ILIB:libp3pnmtext', 'SRCDIR:panda/src/pnmtext'])

#
# DIRECTORY: panda/src/text/
#

if not PkgSkip("HARFBUZZ"):
    DefSymbol("HARFBUZZ", "HAVE_HARFBUZZ")

OPTS=['DIR:panda/src/text', 'BUILDING:PANDA', 'ZLIB', 'FREETYPE', 'HARFBUZZ']
TargetAdd('p3text_composite1.obj', opts=OPTS, input='p3text_composite1.cxx')
TargetAdd('p3text_composite2.obj', opts=OPTS, input='p3text_composite2.cxx')

OPTS=['DIR:panda/src/text', 'ZLIB', 'FREETYPE']
IGATEFILES=GetDirectoryContents('panda/src/text', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3text.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3text.in', opts=['IMOD:panda3d.core', 'ILIB:libp3text', 'SRCDIR:panda/src/text'])

#
# DIRECTORY: panda/src/movies/
#

OPTS=['DIR:panda/src/movies', 'BUILDING:PANDA', 'VORBIS', 'OPUS']
TargetAdd('p3movies_composite1.obj', opts=OPTS, input='p3movies_composite1.cxx')

OPTS=['DIR:panda/src/movies', 'VORBIS', 'OPUS']
IGATEFILES=GetDirectoryContents('panda/src/movies', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3movies.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3movies.in', opts=['IMOD:panda3d.core', 'ILIB:libp3movies', 'SRCDIR:panda/src/movies'])

#
# DIRECTORY: panda/src/grutil/
#

OPTS=['DIR:panda/src/grutil', 'BUILDING:PANDA']
TargetAdd('p3grutil_multitexReducer.obj', opts=OPTS, input='multitexReducer.cxx')
TargetAdd('p3grutil_composite1.obj', opts=OPTS, input='p3grutil_composite1.cxx')
TargetAdd('p3grutil_composite2.obj', opts=OPTS, input='p3grutil_composite2.cxx')

OPTS=['DIR:panda/src/grutil']
IGATEFILES=GetDirectoryContents('panda/src/grutil', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3grutil.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3grutil.in', opts=['IMOD:panda3d.core', 'ILIB:libp3grutil', 'SRCDIR:panda/src/grutil'])

#
# DIRECTORY: panda/src/tform/
#

OPTS=['DIR:panda/src/tform', 'BUILDING:PANDA']
TargetAdd('p3tform_composite1.obj', opts=OPTS, input='p3tform_composite1.cxx')
TargetAdd('p3tform_composite2.obj', opts=OPTS, input='p3tform_composite2.cxx')

OPTS=['DIR:panda/src/tform']
IGATEFILES=GetDirectoryContents('panda/src/tform', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3tform.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3tform.in', opts=['IMOD:panda3d.core', 'ILIB:libp3tform', 'SRCDIR:panda/src/tform'])

#
# DIRECTORY: panda/src/collide/
#

OPTS=['DIR:panda/src/collide', 'BUILDING:PANDA']
TargetAdd('p3collide_composite1.obj', opts=OPTS, input='p3collide_composite1.cxx')
TargetAdd('p3collide_composite2.obj', opts=OPTS, input='p3collide_composite2.cxx')

OPTS=['DIR:panda/src/collide']
IGATEFILES=GetDirectoryContents('panda/src/collide', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3collide.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3collide.in', opts=['IMOD:panda3d.core', 'ILIB:libp3collide', 'SRCDIR:panda/src/collide'])
PyTargetAdd('p3collide_ext_composite.obj', opts=OPTS, input='p3collide_ext_composite.cxx')

#
# DIRECTORY: panda/src/parametrics/
#

OPTS=['DIR:panda/src/parametrics', 'BUILDING:PANDA']
TargetAdd('p3parametrics_composite1.obj', opts=OPTS, input='p3parametrics_composite1.cxx')
TargetAdd('p3parametrics_composite2.obj', opts=OPTS, input='p3parametrics_composite2.cxx')

OPTS=['DIR:panda/src/parametrics']
IGATEFILES=GetDirectoryContents('panda/src/parametrics', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3parametrics.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3parametrics.in', opts=['IMOD:panda3d.core', 'ILIB:libp3parametrics', 'SRCDIR:panda/src/parametrics'])

#
# DIRECTORY: panda/src/pgui/
#

OPTS=['DIR:panda/src/pgui', 'BUILDING:PANDA']
TargetAdd('p3pgui_composite1.obj', opts=OPTS, input='p3pgui_composite1.cxx')
TargetAdd('p3pgui_composite2.obj', opts=OPTS, input='p3pgui_composite2.cxx')

OPTS=['DIR:panda/src/pgui']
IGATEFILES=GetDirectoryContents('panda/src/pgui', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3pgui.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3pgui.in', opts=['IMOD:panda3d.core', 'ILIB:libp3pgui', 'SRCDIR:panda/src/pgui'])

#
# DIRECTORY: panda/src/pnmimagetypes/
#

OPTS=['DIR:panda/src/pnmimagetypes', 'DIR:panda/src/pnmimage', 'BUILDING:PANDA', 'PNG', 'ZLIB', 'JPEG', 'TIFF', 'OPENEXR']
if not PkgSkip('OPENEXR') and GetTarget() != 'emscripten':
    OPTS.append('EXCEPTIONS')
TargetAdd('p3pnmimagetypes_composite1.obj', opts=OPTS, input='p3pnmimagetypes_composite1.cxx')
TargetAdd('p3pnmimagetypes_composite2.obj', opts=OPTS, input='p3pnmimagetypes_composite2.cxx')

#
# DIRECTORY: panda/src/recorder/
#

OPTS=['DIR:panda/src/recorder', 'BUILDING:PANDA']
TargetAdd('p3recorder_composite1.obj', opts=OPTS, input='p3recorder_composite1.cxx')
TargetAdd('p3recorder_composite2.obj', opts=OPTS, input='p3recorder_composite2.cxx')

OPTS=['DIR:panda/src/recorder']
IGATEFILES=GetDirectoryContents('panda/src/recorder', ["*.h", "*_composite*.cxx"])
TargetAdd('libp3recorder.in', opts=OPTS, input=IGATEFILES)
TargetAdd('libp3recorder.in', opts=['IMOD:panda3d.core', 'ILIB:libp3recorder', 'SRCDIR:panda/src/recorder'])

#
# DIRECTORY: panda/metalibs/panda/
#

OPTS=['DIR:panda/metalibs/panda', 'BUILDING:PANDA', 'JPEG', 'PNG', 'HARFBUZZ',
    'TIFF', 'OPENEXR', 'ZLIB', 'FREETYPE', 'FFTW', 'ADVAPI', 'WINSOCK2',
    'SQUISH', 'NVIDIACG', 'VORBIS', 'OPUS', 'WINUSER', 'WINMM', 'WINGDI', 'IPHLPAPI',
    'SETUPAPI', 'INOTIFY', 'IOKIT']

TargetAdd('panda_panda.obj', opts=OPTS, input='panda.cxx')

TargetAdd('libpanda.dll', input='panda_panda.obj')
TargetAdd('libpanda.dll', input='p3recorder_composite1.obj')
TargetAdd('libpanda.dll', input='p3recorder_composite2.obj')
TargetAdd('libpanda.dll', input='p3pgraphnodes_composite1.obj')
TargetAdd('libpanda.dll', input='p3pgraphnodes_composite2.obj')
TargetAdd('libpanda.dll', input='p3pgraph_nodePath.obj')
TargetAdd('libpanda.dll', input='p3pgraph_composite1.obj')
TargetAdd('libpanda.dll', input='p3pgraph_composite2.obj')
TargetAdd('libpanda.dll', input='p3pgraph_composite3.obj')
TargetAdd('libpanda.dll', input='p3pgraph_composite4.obj')
TargetAdd('libpanda.dll', input='p3cull_composite1.obj')
TargetAdd('libpanda.dll', input='p3cull_composite2.obj')
TargetAdd('libpanda.dll', input='p3movies_composite1.obj')
TargetAdd('libpanda.dll', input='p3grutil_multitexReducer.obj')
TargetAdd('libpanda.dll', input='p3grutil_composite1.obj')
TargetAdd('libpanda.dll', input='p3grutil_composite2.obj')
TargetAdd('libpanda.dll', input='p3chan_composite1.obj')
TargetAdd('libpanda.dll', input='p3chan_composite2.obj')
TargetAdd('libpanda.dll', input='p3pstatclient_composite1.obj')
TargetAdd('libpanda.dll', input='p3pstatclient_composite2.obj')
TargetAdd('libpanda.dll', input='p3char_composite1.obj')
TargetAdd('libpanda.dll', input='p3char_composite2.obj')
TargetAdd('libpanda.dll', input='p3collide_composite1.obj')
TargetAdd('libpanda.dll', input='p3collide_composite2.obj')
TargetAdd('libpanda.dll', input='p3device_composite1.obj')
TargetAdd('libpanda.dll', input='p3device_composite2.obj')
TargetAdd('libpanda.dll', input='p3dgraph_composite1.obj')
TargetAdd('libpanda.dll', input='p3dgraph_composite2.obj')
TargetAdd('libpanda.dll', input='p3display_graphicsStateGuardian.obj')
TargetAdd('libpanda.dll', input='p3display_composite1.obj')
TargetAdd('libpanda.dll', input='p3display_composite2.obj')
TargetAdd('libpanda.dll', input='p3pipeline_composite1.obj')
TargetAdd('libpanda.dll', input='p3pipeline_composite2.obj')
TargetAdd('libpanda.dll', input='p3pipeline_contextSwitch.obj')
TargetAdd('libpanda.dll', input='p3event_composite1.obj')
TargetAdd('libpanda.dll', input='p3event_composite2.obj')
TargetAdd('libpanda.dll', input='p3gobj_composite1.obj')
TargetAdd('libpanda.dll', input='p3gobj_composite2.obj')
TargetAdd('libpanda.dll', input='p3gsgbase_composite1.obj')
TargetAdd('libpanda.dll', input='p3linmath_composite1.obj')
TargetAdd('libpanda.dll', input='p3linmath_composite2.obj')
TargetAdd('libpanda.dll', input='p3mathutil_composite1.obj')
TargetAdd('libpanda.dll', input='p3mathutil_composite2.obj')
TargetAdd('libpanda.dll', input='p3parametrics_composite1.obj')
TargetAdd('libpanda.dll', input='p3parametrics_composite2.obj')
TargetAdd('libpanda.dll', input='p3pnmimagetypes_composite1.obj')
TargetAdd('libpanda.dll', input='p3pnmimagetypes_composite2.obj')
TargetAdd('libpanda.dll', input='p3pnmimage_composite1.obj')
TargetAdd('libpanda.dll', input='p3pnmimage_composite2.obj')
TargetAdd('libpanda.dll', input='p3text_composite1.obj')
TargetAdd('libpanda.dll', input='p3text_composite2.obj')
TargetAdd('libpanda.dll', input='p3tform_composite1.obj')
TargetAdd('libpanda.dll', input='p3tform_composite2.obj')
TargetAdd('libpanda.dll', input='p3putil_composite1.obj')
TargetAdd('libpanda.dll', input='p3putil_composite2.obj')
TargetAdd('libpanda.dll', input='p3audio_composite1.obj')
TargetAdd('libpanda.dll', input='p3pgui_composite1.obj')
TargetAdd('libpanda.dll', input='p3pgui_composite2.obj')
TargetAdd('libpanda.dll', input='p3pandabase_pandabase.obj')
TargetAdd('libpanda.dll', input='libpandaexpress.dll')
TargetAdd('libpanda.dll', input='libp3dtoolconfig.dll')
TargetAdd('libpanda.dll', input='libp3dtool.dll')

if GetTarget() != "emscripten":
  TargetAdd('libpanda.dll', input='p3net_composite1.obj')
  TargetAdd('libpanda.dll', input='p3net_composite2.obj')
  TargetAdd('libpanda.dll', input='p3nativenet_composite1.obj')
  TargetAdd('libpanda.dll', input='p3pnmimage_convert_srgb_sse2.obj')

if PkgSkip("FREETYPE")==0:
    TargetAdd('libpanda.dll', input="p3pnmtext_composite1.obj")

TargetAdd('libpanda.dll', dep='dtool_have_freetype.dat')
TargetAdd('libpanda.dll', opts=OPTS)

PyTargetAdd('core_module.obj', input='libp3dtoolbase.in')
PyTargetAdd('core_module.obj', input='libp3dtoolutil.in')
PyTargetAdd('core_module.obj', input='libp3prc.in')

PyTargetAdd('core_module.obj', input='libp3downloader.in')
PyTargetAdd('core_module.obj', input='libp3express.in')

PyTargetAdd('core_module.obj', input='libp3recorder.in')
PyTargetAdd('core_module.obj', input='libp3pgraphnodes.in')
PyTargetAdd('core_module.obj', input='libp3pgraph.in')
PyTargetAdd('core_module.obj', input='libp3cull.in')
PyTargetAdd('core_module.obj', input='libp3grutil.in')
PyTargetAdd('core_module.obj', input='libp3chan.in')
PyTargetAdd('core_module.obj', input='libp3pstatclient.in')
PyTargetAdd('core_module.obj', input='libp3char.in')
PyTargetAdd('core_module.obj', input='libp3collide.in')
PyTargetAdd('core_module.obj', input='libp3device.in')
PyTargetAdd('core_module.obj', input='libp3dgraph.in')
PyTargetAdd('core_module.obj', input='libp3display.in')
PyTargetAdd('core_module.obj', input='libp3pipeline.in')
PyTargetAdd('core_module.obj', input='libp3event.in')
PyTargetAdd('core_module.obj', input='libp3gobj.in')
PyTargetAdd('core_module.obj', input='libp3gsgbase.in')
PyTargetAdd('core_module.obj', input='libp3linmath.in')
PyTargetAdd('core_module.obj', input='libp3mathutil.in')
PyTargetAdd('core_module.obj', input='libp3parametrics.in')
PyTargetAdd('core_module.obj', input='libp3pnmimage.in')
PyTargetAdd('core_module.obj', input='libp3text.in')
PyTargetAdd('core_module.obj', input='libp3tform.in')
PyTargetAdd('core_module.obj', input='libp3putil.in')
PyTargetAdd('core_module.obj', input='libp3audio.in')
PyTargetAdd('core_module.obj', input='libp3pgui.in')
PyTargetAdd('core_module.obj', input='libp3movies.in')

if GetTarget() != "emscripten":
  PyTargetAdd('core_module.obj', input='libp3nativenet.in')
  PyTargetAdd('core_module.obj', input='libp3net.in')

if PkgSkip("FREETYPE")==0:
    PyTargetAdd('core_module.obj', input='libp3pnmtext.in')

PyTargetAdd('core_module.obj', opts=['IMOD:panda3d.core', 'ILIB:core', 'INIT:pyenv_init'])

PyTargetAdd('core.pyd', input='libp3dtoolbase_igate.obj')
PyTargetAdd('core.pyd', input='p3dtoolbase_typeHandle_ext.obj')
PyTargetAdd('core.pyd', input='libp3dtoolutil_igate.obj')
PyTargetAdd('core.pyd', input='p3dtoolutil_ext_composite.obj')
PyTargetAdd('core.pyd', input='libp3prc_igate.obj')
PyTargetAdd('core.pyd', input='p3prc_ext_composite.obj')

PyTargetAdd('core.pyd', input='libp3downloader_igate.obj')
PyTargetAdd('core.pyd', input='p3express_ext_composite.obj')
PyTargetAdd('core.pyd', input='libp3express_igate.obj')

PyTargetAdd('core.pyd', input='libp3recorder_igate.obj')
PyTargetAdd('core.pyd', input='libp3pgraphnodes_igate.obj')
PyTargetAdd('core.pyd', input='libp3pgraph_igate.obj')
PyTargetAdd('core.pyd', input='libp3movies_igate.obj')
PyTargetAdd('core.pyd', input='libp3grutil_igate.obj')
PyTargetAdd('core.pyd', input='libp3chan_igate.obj')
PyTargetAdd('core.pyd', input='libp3pstatclient_igate.obj')
PyTargetAdd('core.pyd', input='libp3char_igate.obj')
PyTargetAdd('core.pyd', input='libp3collide_igate.obj')
PyTargetAdd('core.pyd', input='libp3device_igate.obj')
PyTargetAdd('core.pyd', input='libp3dgraph_igate.obj')
PyTargetAdd('core.pyd', input='libp3display_igate.obj')
PyTargetAdd('core.pyd', input='libp3pipeline_igate.obj')
PyTargetAdd('core.pyd', input='libp3event_igate.obj')
PyTargetAdd('core.pyd', input='libp3gobj_igate.obj')
PyTargetAdd('core.pyd', input='libp3gsgbase_igate.obj')
PyTargetAdd('core.pyd', input='libp3linmath_igate.obj')
PyTargetAdd('core.pyd', input='libp3mathutil_igate.obj')
PyTargetAdd('core.pyd', input='libp3parametrics_igate.obj')
PyTargetAdd('core.pyd', input='libp3pnmimage_igate.obj')
PyTargetAdd('core.pyd', input='libp3text_igate.obj')
PyTargetAdd('core.pyd', input='libp3tform_igate.obj')
PyTargetAdd('core.pyd', input='libp3putil_igate.obj')
PyTargetAdd('core.pyd', input='libp3audio_igate.obj')
PyTargetAdd('core.pyd', input='libp3pgui_igate.obj')

if GetTarget() != "emscripten":
  PyTargetAdd('core.pyd', input='libp3net_igate.obj')
  PyTargetAdd('core.pyd', input='libp3nativenet_igate.obj')

if PkgSkip("FREETYPE")==0:
    PyTargetAdd('core.pyd', input="libp3pnmtext_igate.obj")

PyTargetAdd('core.pyd', input='p3pipeline_pythonThread.obj')
PyTargetAdd('core.pyd', input='p3putil_ext_composite.obj')
PyTargetAdd('core.pyd', input='p3pnmimage_pfmFile_ext.obj')
PyTargetAdd('core.pyd', input='p3event_asyncFuture_ext.obj')
PyTargetAdd('core.pyd', input='p3event_pythonTask.obj')
PyTargetAdd('core.pyd', input='p3pstatclient_pStatClient_ext.obj')
PyTargetAdd('core.pyd', input='p3gobj_ext_composite.obj')
PyTargetAdd('core.pyd', input='p3pgraph_ext_composite.obj')
PyTargetAdd('core.pyd', input='p3display_ext_composite.obj')
PyTargetAdd('core.pyd', input='p3collide_ext_composite.obj')

PyTargetAdd('core.pyd', input='core_module.obj')
PyTargetAdd('core.pyd', input=COMMON_PANDA_LIBS)
PyTargetAdd('core.pyd', opts=['WINSOCK2'])

#
# DIRECTORY: panda/src/vision/
#

if not PkgSkip("VISION"):
  # We want to know whether we have ffmpeg so that we can override the .avi association.
    if not PkgSkip("FFMPEG"):
        DefSymbol("OPENCV", "HAVE_FFMPEG")
    if not PkgSkip("OPENCV"):
        DefSymbol("OPENCV", "HAVE_OPENCV")
        if OPENCV_VER_23:
            DefSymbol("OPENCV", "OPENCV_VER_23")

    OPTS=['DIR:panda/src/vision', 'BUILDING:VISION', 'ARTOOLKIT', 'OPENCV', 'DX9', 'DIRECTCAM', 'JPEG', 'EXCEPTIONS']
    TargetAdd('p3vision_composite1.obj', opts=OPTS, input='p3vision_composite1.cxx', dep=[
        'dtool_have_ffmpeg.dat',
        'dtool_have_opencv.dat',
        'dtool_have_directcam.dat',
    ])

    TargetAdd('libp3vision.dll', input='p3vision_composite1.obj')
    TargetAdd('libp3vision.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libp3vision.dll', opts=OPTS)

    OPTS=['DIR:panda/src/vision', 'ARTOOLKIT', 'OPENCV', 'DX9', 'DIRECTCAM', 'JPEG', 'EXCEPTIONS']
    IGATEFILES=GetDirectoryContents('panda/src/vision', ["*.h", "*_composite*.cxx"])
    TargetAdd('libp3vision.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3vision.in', opts=['IMOD:panda3d.vision', 'ILIB:libp3vision', 'SRCDIR:panda/src/vision'])

    PyTargetAdd('vision_module.obj', input='libp3vision.in')
    PyTargetAdd('vision_module.obj', opts=OPTS)
    PyTargetAdd('vision_module.obj', opts=['IMOD:panda3d.vision', 'ILIB:vision', 'IMPORT:panda3d.core'])

    PyTargetAdd('vision.pyd', input='vision_module.obj')
    PyTargetAdd('vision.pyd', input='libp3vision_igate.obj')
    PyTargetAdd('vision.pyd', input='libp3vision.dll')
    PyTargetAdd('vision.pyd', input=COMMON_PANDA_LIBS)

#
# DIRECTORY: panda/src/p3skel
#

if not PkgSkip('SKEL'):
    OPTS=['DIR:panda/src/skel', 'BUILDING:PANDASKEL', 'ADVAPI']
    TargetAdd('p3skel_composite1.obj', opts=OPTS, input='p3skel_composite1.cxx')

    OPTS=['DIR:panda/src/skel', 'ADVAPI']
    IGATEFILES=GetDirectoryContents("panda/src/skel", ["*.h", "*_composite*.cxx"])
    TargetAdd('libp3skel.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3skel.in', opts=['IMOD:panda3d.skel', 'ILIB:libp3skel', 'SRCDIR:panda/src/skel'])

#
# DIRECTORY: panda/src/p3skel
#

if not PkgSkip('SKEL'):
    OPTS=['BUILDING:PANDASKEL', 'ADVAPI']
    TargetAdd('libpandaskel.dll', input='p3skel_composite1.obj')
    TargetAdd('libpandaskel.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandaskel.dll', opts=OPTS)

    PyTargetAdd('skel_module.obj', input='libp3skel.in')
    PyTargetAdd('skel_module.obj', opts=['IMOD:panda3d.skel', 'ILIB:skel', 'IMPORT:panda3d.core'])

    PyTargetAdd('skel.pyd', input='skel_module.obj')
    PyTargetAdd('skel.pyd', input='libp3skel_igate.obj')
    PyTargetAdd('skel.pyd', input='libpandaskel.dll')
    PyTargetAdd('skel.pyd', input=COMMON_PANDA_LIBS)

#
# DIRECTORY: panda/src/distort/
#

if not PkgSkip('PANDAFX'):
    OPTS=['DIR:panda/src/distort', 'BUILDING:PANDAFX']
    TargetAdd('p3distort_composite1.obj', opts=OPTS, input='p3distort_composite1.cxx')

    OPTS=['DIR:panda/metalibs/pandafx', 'DIR:panda/src/distort', 'NVIDIACG']
    IGATEFILES=GetDirectoryContents('panda/src/distort', ["*.h", "*_composite*.cxx"])
    TargetAdd('libp3distort.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3distort.in', opts=['IMOD:panda3d.fx', 'ILIB:libp3distort', 'SRCDIR:panda/src/distort'])

#
# DIRECTORY: panda/metalibs/pandafx/
#

if not PkgSkip('PANDAFX'):
    OPTS=['DIR:panda/metalibs/pandafx', 'DIR:panda/src/distort', 'BUILDING:PANDAFX', 'NVIDIACG']
    TargetAdd('pandafx_pandafx.obj', opts=OPTS, input='pandafx.cxx')

    TargetAdd('libpandafx.dll', input='pandafx_pandafx.obj')
    TargetAdd('libpandafx.dll', input='p3distort_composite1.obj')
    TargetAdd('libpandafx.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandafx.dll', opts=['ADVAPI', 'NVIDIACG'])

    OPTS=['DIR:panda/metalibs/pandafx', 'DIR:panda/src/distort', 'NVIDIACG']
    PyTargetAdd('fx_module.obj', input='libp3distort.in')
    PyTargetAdd('fx_module.obj', opts=OPTS)
    PyTargetAdd('fx_module.obj', opts=['IMOD:panda3d.fx', 'ILIB:fx', 'IMPORT:panda3d.core'])

    PyTargetAdd('fx.pyd', input='fx_module.obj')
    PyTargetAdd('fx.pyd', input='libp3distort_igate.obj')
    PyTargetAdd('fx.pyd', input='libpandafx.dll')
    PyTargetAdd('fx.pyd', input=COMMON_PANDA_LIBS)

#
# DIRECTORY: panda/src/vrpn/
#

if not PkgSkip("VRPN"):
    OPTS=['DIR:panda/src/vrpn', 'BUILDING:VRPN', 'VRPN']
    TargetAdd('p3vrpn_composite1.obj', opts=OPTS, input='p3vrpn_composite1.cxx')
    TargetAdd('libp3vrpn.dll', input='p3vrpn_composite1.obj')
    TargetAdd('libp3vrpn.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libp3vrpn.dll', opts=['VRPN'])

    OPTS=['DIR:panda/src/vrpn', 'VRPN']
    IGATEFILES=GetDirectoryContents('panda/src/vrpn', ["*.h", "*_composite*.cxx"])
    TargetAdd('libp3vrpn.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3vrpn.in', opts=['IMOD:panda3d.vrpn', 'ILIB:libp3vrpn', 'SRCDIR:panda/src/vrpn'])

    PyTargetAdd('vrpn_module.obj', input='libp3vrpn.in')
    PyTargetAdd('vrpn_module.obj', opts=OPTS)
    PyTargetAdd('vrpn_module.obj', opts=['IMOD:panda3d.vrpn', 'ILIB:vrpn', 'IMPORT:panda3d.core'])

    PyTargetAdd('vrpn.pyd', input='vrpn_module.obj')
    PyTargetAdd('vrpn.pyd', input='libp3vrpn_igate.obj')
    PyTargetAdd('vrpn.pyd', input='libp3vrpn.dll')
    PyTargetAdd('vrpn.pyd', input=COMMON_PANDA_LIBS)

#
# DIRECTORY: panda/src/ffmpeg
#
if PkgSkip("FFMPEG") == 0:
    if not PkgSkip("SWSCALE"):
        DefSymbol("FFMPEG", "HAVE_SWSCALE")
    if not PkgSkip("SWRESAMPLE"):
        DefSymbol("FFMPEG", "HAVE_SWRESAMPLE")

    OPTS=['DIR:panda/src/ffmpeg', 'BUILDING:FFMPEG', 'FFMPEG', 'SWSCALE', 'SWRESAMPLE']
    TargetAdd('p3ffmpeg_composite1.obj', opts=OPTS, input='p3ffmpeg_composite1.cxx', dep=[
        'dtool_have_swscale.dat', 'dtool_have_swresample.dat'])

    TargetAdd('libp3ffmpeg.dll', input='p3ffmpeg_composite1.obj')
    TargetAdd('libp3ffmpeg.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libp3ffmpeg.dll', opts=OPTS)

#
# DIRECTORY: panda/src/audiotraits/
#

if PkgSkip("FMODEX") == 0:
    OPTS=['DIR:panda/src/audiotraits', 'BUILDING:FMOD_AUDIO', 'FMODEX']
    TargetAdd('fmod_audio_fmod_audio_composite1.obj', opts=OPTS, input='fmod_audio_composite1.cxx')
    TargetAdd('libp3fmod_audio.dll', input='fmod_audio_fmod_audio_composite1.obj')
    TargetAdd('libp3fmod_audio.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libp3fmod_audio.dll', opts=['MODULE', 'ADVAPI', 'WINUSER', 'WINMM', 'FMODEX'])

if PkgSkip("OPENAL") == 0:
    OPTS=['DIR:panda/src/audiotraits', 'BUILDING:OPENAL_AUDIO', 'OPENAL']
    TargetAdd('openal_audio_openal_audio_composite1.obj', opts=OPTS, input='openal_audio_composite1.cxx')
    TargetAdd('libp3openal_audio.dll', input='openal_audio_openal_audio_composite1.obj')
    TargetAdd('libp3openal_audio.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libp3openal_audio.dll', opts=['MODULE', 'ADVAPI', 'WINUSER', 'WINMM', 'WINSHELL', 'WINOLE', 'OPENAL', 'OPENSLES'])

#
# DIRECTORY: panda/src/downloadertools/
#

if not PkgSkip("OPENSSL") and not PkgSkip("DEPLOYTOOLS"):
    OPTS=['DIR:panda/src/downloadertools', 'ADVAPI', 'WINSOCK2', 'WINSHELL', 'WINGDI', 'WINUSER']

    TargetAdd('pdecrypt_pdecrypt.obj', opts=OPTS, input='pdecrypt.cxx')
    TargetAdd('pdecrypt.exe', input=['pdecrypt_pdecrypt.obj'])
    TargetAdd('pdecrypt.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('pdecrypt.exe', opts=OPTS)

    TargetAdd('pencrypt_pencrypt.obj', opts=OPTS, input='pencrypt.cxx')
    TargetAdd('pencrypt.exe', input=['pencrypt_pencrypt.obj'])
    TargetAdd('pencrypt.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('pencrypt.exe', opts=OPTS)

#
# DIRECTORY: panda/src/downloadertools/
#

if not PkgSkip("ZLIB") and not PkgSkip("DEPLOYTOOLS"):
    OPTS=['DIR:panda/src/downloadertools', 'ZLIB', 'ADVAPI', 'WINSOCK2', 'WINSHELL', 'WINGDI', 'WINUSER']

    TargetAdd('multify_multify.obj', opts=OPTS, input='multify.cxx')
    TargetAdd('multify.exe', input=['multify_multify.obj'])
    TargetAdd('multify.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('multify.exe', opts=OPTS)

    TargetAdd('pzip_pzip.obj', opts=OPTS, input='pzip.cxx')
    TargetAdd('pzip.exe', input=['pzip_pzip.obj'])
    TargetAdd('pzip.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('pzip.exe', opts=OPTS)

    TargetAdd('punzip_punzip.obj', opts=OPTS, input='punzip.cxx')
    TargetAdd('punzip.exe', input=['punzip_punzip.obj'])
    TargetAdd('punzip.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('punzip.exe', opts=OPTS)

#
# DIRECTORY: panda/src/windisplay/
#

if GetTarget() == 'windows':
    OPTS=['DIR:panda/src/windisplay', 'BUILDING:PANDAWIN']
    TargetAdd('p3windisplay_composite1.obj', opts=OPTS+["BIGOBJ"], input='p3windisplay_composite1.cxx')
    TargetAdd('p3windisplay_windetectdx9.obj', opts=OPTS + ["DX9"], input='winDetectDx9.cxx')
    TargetAdd('libp3windisplay.dll', input='p3windisplay_composite1.obj')
    TargetAdd('libp3windisplay.dll', input='p3windisplay_windetectdx9.obj')
    TargetAdd('libp3windisplay.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libp3windisplay.dll', opts=['WINIMM', 'WINGDI', 'WINKERNEL', 'WINOLDNAMES', 'WINUSER', 'WINMM',"BIGOBJ"])

#
# DIRECTORY: panda/metalibs/pandadx9/
#

if GetTarget() == 'windows' and not PkgSkip("DX9"):
    OPTS=['DIR:panda/src/dxgsg9', 'BUILDING:PANDADX', 'DX9', 'NVIDIACG', 'CGDX9']
    TargetAdd('p3dxgsg9_dxGraphicsStateGuardian9.obj', opts=OPTS, input='dxGraphicsStateGuardian9.cxx')
    TargetAdd('p3dxgsg9_composite1.obj', opts=OPTS, input='p3dxgsg9_composite1.cxx')
    OPTS=['DIR:panda/metalibs/pandadx9', 'BUILDING:PANDADX', 'DX9', 'NVIDIACG', 'CGDX9']
    TargetAdd('pandadx9_pandadx9.obj', opts=OPTS, input='pandadx9.cxx')
    TargetAdd('libpandadx9.dll', input='pandadx9_pandadx9.obj')
    TargetAdd('libpandadx9.dll', input='p3dxgsg9_dxGraphicsStateGuardian9.obj')
    TargetAdd('libpandadx9.dll', input='p3dxgsg9_composite1.obj')
    TargetAdd('libpandadx9.dll', input='libp3windisplay.dll')
    TargetAdd('libpandadx9.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandadx9.dll', opts=['MODULE', 'ADVAPI', 'WINGDI', 'WINKERNEL', 'WINUSER', 'WINMM', 'DX9', 'NVIDIACG', 'CGDX9'])

#
# DIRECTORY: panda/src/egg/
#

if not PkgSkip("EGG"):
    OPTS=['DIR:panda/src/egg', 'BUILDING:PANDAEGG', 'ZLIB', 'BISONPREFIX_eggyy', 'FLEXDASHI', 'FLEXVERSION:2.5.6']
    CreateFile(GetOutputDir()+"/include/parser.h")
    TargetAdd('p3egg_parser.obj', opts=OPTS, input='parser.yxx')
    TargetAdd('parser.h', input='p3egg_parser.obj', opts=['DEPENDENCYONLY'])
    TargetAdd('p3egg_lexer.obj', opts=OPTS, input='lexer.lxx')
    TargetAdd('p3egg_composite1.obj', opts=OPTS, input='p3egg_composite1.cxx')
    TargetAdd('p3egg_composite2.obj', opts=OPTS, input='p3egg_composite2.cxx')

    OPTS=['DIR:panda/src/egg', 'ZLIB']
    IGATEFILES=GetDirectoryContents('panda/src/egg', ["*.h", "*_composite*.cxx"])
    if "parser.h" in IGATEFILES:
        IGATEFILES.remove("parser.h")
    TargetAdd('libp3egg.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3egg.in', opts=['IMOD:panda3d.egg', 'ILIB:libp3egg', 'SRCDIR:panda/src/egg'])
    PyTargetAdd('p3egg_ext_composite.obj', opts=OPTS, input='p3egg_ext_composite.cxx')

#
# DIRECTORY: panda/src/egg2pg/
#

if not PkgSkip("EGG"):
    OPTS=['DIR:panda/src/egg2pg', 'BUILDING:PANDAEGG']
    TargetAdd('p3egg2pg_composite1.obj', opts=OPTS, input='p3egg2pg_composite1.cxx')
    TargetAdd('p3egg2pg_composite2.obj', opts=OPTS, input='p3egg2pg_composite2.cxx')

    OPTS=['DIR:panda/src/egg2pg']
    IGATEFILES=['load_egg_file.h', 'save_egg_file.h']
    TargetAdd('libp3egg2pg.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3egg2pg.in', opts=['IMOD:panda3d.egg', 'ILIB:libp3egg2pg', 'SRCDIR:panda/src/egg2pg'])

#
# DIRECTORY: panda/src/framework/
#

deps = []
# Framework wants to link in a renderer when building statically, so tell it what is available.
if GetLinkAllStatic():
    deps = ['dtool_have_gl.dat', 'dtool_have_tinydisplay.dat', 'dtool_have_egg.dat']
    if not PkgSkip("GL"):
        DefSymbol("FRAMEWORK", "HAVE_GL")
    if not PkgSkip("TINYDISPLAY"):
        DefSymbol("FRAMEWORK", "HAVE_TINYDISPLAY")
    if not PkgSkip("EGG"):
        DefSymbol("FRAMEWORK", "HAVE_EGG")

OPTS=['DIR:panda/src/framework', 'BUILDING:FRAMEWORK', 'FRAMEWORK']
TargetAdd('p3framework_composite1.obj', opts=OPTS, input='p3framework_composite1.cxx', dep=deps)
TargetAdd('libp3framework.dll', input='p3framework_composite1.obj')
TargetAdd('libp3framework.dll', input=COMMON_PANDA_LIBS)
TargetAdd('libp3framework.dll', opts=['ADVAPI'])

#
# DIRECTORY: panda/src/glgsg/
#

if not PkgSkip("GL"):
    OPTS=['DIR:panda/src/glgsg', 'DIR:panda/src/glstuff', 'BUILDING:PANDAGL', 'GL', 'NVIDIACG']
    TargetAdd('p3glgsg_config_glgsg.obj', opts=OPTS, input='config_glgsg.cxx')
    TargetAdd('p3glgsg_glgsg.obj', opts=OPTS, input='glgsg.cxx')

#
# DIRECTORY: panda/src/glesgsg/
#

if not PkgSkip("GLES"):
    OPTS=['DIR:panda/src/glesgsg', 'DIR:panda/src/glstuff', 'BUILDING:PANDAGLES', 'GLES']
    TargetAdd('p3glesgsg_config_glesgsg.obj', opts=OPTS, input='config_glesgsg.cxx')
    TargetAdd('p3glesgsg_glesgsg.obj', opts=OPTS, input='glesgsg.cxx')

#
# DIRECTORY: panda/src/gles2gsg/
#

if not PkgSkip("GLES2"):
    OPTS=['DIR:panda/src/gles2gsg', 'DIR:panda/src/glstuff', 'BUILDING:PANDAGLES2', 'GLES2']
    TargetAdd('p3gles2gsg_config_gles2gsg.obj', opts=OPTS, input='config_gles2gsg.cxx')
    TargetAdd('p3gles2gsg_gles2gsg.obj', opts=OPTS, input='gles2gsg.cxx')

#
# DIRECTORY: panda/metalibs/pandaegg/
#

if not PkgSkip("EGG"):
    OPTS=['DIR:panda/metalibs/pandaegg', 'DIR:panda/src/egg', 'BUILDING:PANDAEGG']
    TargetAdd('pandaegg_pandaegg.obj', opts=OPTS, input='pandaegg.cxx')

    TargetAdd('libpandaegg.dll', input='pandaegg_pandaegg.obj')
    TargetAdd('libpandaegg.dll', input='p3egg2pg_composite1.obj')
    TargetAdd('libpandaegg.dll', input='p3egg2pg_composite2.obj')
    TargetAdd('libpandaegg.dll', input='p3egg_composite1.obj')
    TargetAdd('libpandaegg.dll', input='p3egg_composite2.obj')
    TargetAdd('libpandaegg.dll', input='p3egg_parser.obj')
    TargetAdd('libpandaegg.dll', input='p3egg_lexer.obj')
    TargetAdd('libpandaegg.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandaegg.dll', opts=['ADVAPI'])

    OPTS=['DIR:panda/metalibs/pandaegg', 'DIR:panda/src/egg']
    PyTargetAdd('egg_module.obj', input='libp3egg2pg.in')
    PyTargetAdd('egg_module.obj', input='libp3egg.in')
    PyTargetAdd('egg_module.obj', opts=OPTS)
    PyTargetAdd('egg_module.obj', opts=['IMOD:panda3d.egg', 'ILIB:egg', 'IMPORT:panda3d.core'])

    PyTargetAdd('egg.pyd', input='egg_module.obj')
    PyTargetAdd('egg.pyd', input='p3egg_ext_composite.obj')
    PyTargetAdd('egg.pyd', input='libp3egg_igate.obj')
    PyTargetAdd('egg.pyd', input='libp3egg2pg_igate.obj')
    PyTargetAdd('egg.pyd', input='libpandaegg.dll')
    PyTargetAdd('egg.pyd', input=COMMON_PANDA_LIBS)

#
# DIRECTORY: panda/src/x11display/
#

if GetTarget() not in ['windows', 'darwin', 'emscripten'] and not PkgSkip("X11"):
    OPTS=['DIR:panda/src/x11display', 'BUILDING:PANDAX11', 'X11']
    TargetAdd('p3x11display_composite1.obj', opts=OPTS, input='p3x11display_composite1.cxx')

#
# DIRECTORY: panda/src/glxdisplay/
#

if GetTarget() not in ['windows', 'darwin', 'emscripten'] and not PkgSkip("GL") and not PkgSkip("X11"):
    DefSymbol('GLX', 'HAVE_GLX', '')
    OPTS=['DIR:panda/src/glxdisplay', 'BUILDING:PANDAGL', 'GL', 'NVIDIACG', 'CGGL', 'GLX']
    TargetAdd('p3glxdisplay_composite1.obj', opts=OPTS, input='p3glxdisplay_composite1.cxx')
    OPTS=['DIR:panda/metalibs/pandagl', 'BUILDING:PANDAGL', 'GL', 'NVIDIACG', 'CGGL', 'GLX']
    TargetAdd('pandagl_pandagl.obj', opts=OPTS, input='pandagl.cxx')
    TargetAdd('libpandagl.dll', input='p3x11display_composite1.obj')
    TargetAdd('libpandagl.dll', input='pandagl_pandagl.obj')
    TargetAdd('libpandagl.dll', input='p3glgsg_config_glgsg.obj')
    TargetAdd('libpandagl.dll', input='p3glgsg_glgsg.obj')
    TargetAdd('libpandagl.dll', input='p3glxdisplay_composite1.obj')
    TargetAdd('libpandagl.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandagl.dll', opts=['MODULE', 'GL', 'NVIDIACG', 'CGGL', 'X11'])

#
# DIRECTORY: panda/src/cocoadisplay/
#

if GetTarget() == 'darwin' and not PkgSkip("COCOA"):
    OPTS=['DIR:panda/src/cocoadisplay', 'BUILDING:PANDAGL', 'COCOA']
    TargetAdd('p3cocoadisplay_composite1.obj', opts=OPTS, input='p3cocoadisplay_composite1.mm')

#
# DIRECTORY: panda/src/cocoagldisplay/
#

if GetTarget() == 'darwin' and not PkgSkip("COCOA") and not PkgSkip("GL"):
    OPTS=['DIR:panda/src/cocoagldisplay', 'BUILDING:PANDAGL', 'GL', 'NVIDIACG', 'CGGL']
    TargetAdd('p3cocoagldisplay_composite1.obj', opts=OPTS, input='p3cocoagldisplay_composite1.mm')
    OPTS=['DIR:panda/metalibs/pandagl', 'BUILDING:PANDAGL', 'GL', 'NVIDIACG', 'CGGL']
    TargetAdd('pandagl_pandagl.obj', opts=OPTS, input='pandagl.cxx')
    TargetAdd('libpandagl.dll', input='pandagl_pandagl.obj')
    TargetAdd('libpandagl.dll', input='p3glgsg_config_glgsg.obj')
    TargetAdd('libpandagl.dll', input='p3glgsg_glgsg.obj')
    TargetAdd('libpandagl.dll', input='p3cocoadisplay_composite1.obj')
    TargetAdd('libpandagl.dll', input='p3cocoagldisplay_composite1.obj')
    if not PkgSkip('PANDAFX'):
        TargetAdd('libpandagl.dll', input='libpandafx.dll')
    TargetAdd('libpandagl.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandagl.dll', opts=['MODULE', 'GL', 'NVIDIACG', 'CGGL', 'COCOA', 'CARBON', 'QUARTZ'])

#
# DIRECTORY: panda/src/wgldisplay/
#

if GetTarget() == 'windows' and not PkgSkip("GL"):
    OPTS=['DIR:panda/src/wgldisplay', 'DIR:panda/src/glstuff', 'BUILDING:PANDAGL', 'NVIDIACG', 'CGGL']
    TargetAdd('p3wgldisplay_composite1.obj', opts=OPTS, input='p3wgldisplay_composite1.cxx')
    OPTS=['DIR:panda/metalibs/pandagl', 'BUILDING:PANDAGL', 'NVIDIACG', 'CGGL']
    TargetAdd('pandagl_pandagl.obj', opts=OPTS, input='pandagl.cxx')
    TargetAdd('libpandagl.dll', input='pandagl_pandagl.obj')
    TargetAdd('libpandagl.dll', input='p3glgsg_config_glgsg.obj')
    TargetAdd('libpandagl.dll', input='p3glgsg_glgsg.obj')
    TargetAdd('libpandagl.dll', input='p3wgldisplay_composite1.obj')
    TargetAdd('libpandagl.dll', input='libp3windisplay.dll')
    if not PkgSkip('PANDAFX'):
        TargetAdd('libpandagl.dll', input='libpandafx.dll')
    TargetAdd('libpandagl.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandagl.dll', opts=['MODULE', 'WINGDI', 'GL', 'WINKERNEL', 'WINOLDNAMES', 'WINUSER', 'WINMM', 'NVIDIACG', 'CGGL'])

#
# DIRECTORY: panda/src/egldisplay/
#

# If we're not compiling with any windowing system at all, but we do have EGL,
# we can use that to create a headless libpandagl instead.
if not PkgSkip("EGL") and not PkgSkip("GL") and PkgSkip("X11") and GetTarget() not in ('windows', 'darwin'):
    OPTS=['DIR:panda/src/egldisplay', 'DIR:panda/src/glstuff', 'BUILDING:PANDAGL', 'GL', 'EGL']
    TargetAdd('pandagl_egldisplay_composite1.obj', opts=OPTS, input='p3egldisplay_composite1.cxx')
    OPTS=['DIR:panda/metalibs/pandagl', 'BUILDING:PANDAGL', 'GL', 'EGL']
    TargetAdd('pandagl_pandagl.obj', opts=OPTS, input='pandagl.cxx')
    TargetAdd('libpandagl.dll', input='pandagl_pandagl.obj')
    TargetAdd('libpandagl.dll', input='p3glgsg_config_glgsg.obj')
    TargetAdd('libpandagl.dll', input='p3glgsg_glgsg.obj')
    TargetAdd('libpandagl.dll', input='pandagl_egldisplay_composite1.obj')
    TargetAdd('libpandagl.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandagl.dll', opts=['MODULE', 'GL', 'EGL', 'CGGL'])

elif not PkgSkip("EGL") and not PkgSkip("GL") and GetTarget() not in ('windows', 'darwin'):
    # As a temporary solution for #1086, build this module, which we can use as a
    # fallback to OpenGL for headless systems.
    OPTS=['DIR:panda/src/egldisplay', 'DIR:panda/src/glstuff', 'BUILDING:PANDAGL', 'GL', 'EGL']
    TargetAdd('p3headlessgl_egldisplay_composite1.obj', opts=OPTS, input='p3egldisplay_composite1.cxx')
    OPTS=['DIR:panda/metalibs/pandagl', 'BUILDING:PANDAGL', 'GL', 'EGL']
    TargetAdd('p3headlessgl_pandagl.obj', opts=OPTS, input='pandagl.cxx')
    TargetAdd('libp3headlessgl.dll', input='p3headlessgl_pandagl.obj')
    TargetAdd('libp3headlessgl.dll', input='p3glgsg_config_glgsg.obj')
    TargetAdd('libp3headlessgl.dll', input='p3glgsg_glgsg.obj')
    TargetAdd('libp3headlessgl.dll', input='p3headlessgl_egldisplay_composite1.obj')
    TargetAdd('libp3headlessgl.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libp3headlessgl.dll', opts=['MODULE', 'GL', 'EGL', 'CGGL'])

#
# DIRECTORY: panda/src/egldisplay/
#

if GetTarget() != 'android' and not PkgSkip("EGL") and not PkgSkip("GLES"):
    DefSymbol('GLES', 'OPENGLES_1', '')
    OPTS=['DIR:panda/src/egldisplay', 'DIR:panda/src/glstuff', 'BUILDING:PANDAGLES', 'GLES', 'EGL', 'X11']
    TargetAdd('pandagles_egldisplay_composite1.obj', opts=OPTS, input='p3egldisplay_composite1.cxx')
    OPTS=['DIR:panda/metalibs/pandagles', 'BUILDING:PANDAGLES', 'GLES', 'EGL']
    TargetAdd('pandagles_pandagles.obj', opts=OPTS, input='pandagles.cxx')
    if not PkgSkip("X11"):
        TargetAdd('libpandagles.dll', input='p3x11display_composite1.obj')
    TargetAdd('libpandagles.dll', input='pandagles_pandagles.obj')
    TargetAdd('libpandagles.dll', input='p3glesgsg_config_glesgsg.obj')
    TargetAdd('libpandagles.dll', input='p3glesgsg_glesgsg.obj')
    TargetAdd('libpandagles.dll', input='pandagles_egldisplay_composite1.obj')
    TargetAdd('libpandagles.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandagles.dll', opts=['MODULE', 'GLES', 'EGL', 'X11'])

#
# DIRECTORY: panda/src/egldisplay/
#

if GetTarget() != 'android' and not PkgSkip("EGL") and not PkgSkip("GLES2"):
    DefSymbol('GLES2', 'OPENGLES_2', '')
    OPTS=['DIR:panda/src/egldisplay', 'DIR:panda/src/glstuff', 'BUILDING:PANDAGLES2', 'GLES2', 'EGL', 'X11']
    TargetAdd('pandagles2_egldisplay_composite1.obj', opts=OPTS, input='p3egldisplay_composite1.cxx')
    OPTS=['DIR:panda/metalibs/pandagles2', 'BUILDING:PANDAGLES2', 'GLES2', 'EGL']
    TargetAdd('pandagles2_pandagles2.obj', opts=OPTS, input='pandagles2.cxx')
    if not PkgSkip("X11"):
        TargetAdd('libpandagles2.dll', input='p3x11display_composite1.obj')
    TargetAdd('libpandagles2.dll', input='pandagles2_pandagles2.obj')
    TargetAdd('libpandagles2.dll', input='p3gles2gsg_config_gles2gsg.obj')
    TargetAdd('libpandagles2.dll', input='p3gles2gsg_gles2gsg.obj')
    TargetAdd('libpandagles2.dll', input='pandagles2_egldisplay_composite1.obj')
    TargetAdd('libpandagles2.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandagles2.dll', opts=['MODULE', 'GLES2', 'EGL', 'X11'])

#
# DIRECTORY: panda/src/webgldisplay/
#

if GetTarget() == 'emscripten' and not PkgSkip("GLES2"):
  DefSymbol('GLES2', 'OPENGLES_2', '')
  LinkFlag('GLES2', '-s GL_ENABLE_GET_PROC_ADDRESS=1')
  OPTS=['DIR:panda/src/webgldisplay', 'DIR:panda/src/glstuff', 'BUILDING:PANDAGLES2',  'GLES2', 'WEBGL']
  TargetAdd('p3webgldisplay_webgldisplay_composite1.obj', opts=OPTS, input='p3webgldisplay_composite1.cxx')
  TargetAdd('libp3webgldisplay.dll', input='p3gles2gsg_config_gles2gsg.obj')
  TargetAdd('libp3webgldisplay.dll', input='p3gles2gsg_gles2gsg.obj')
  TargetAdd('libp3webgldisplay.dll', input='p3webgldisplay_webgldisplay_composite1.obj')
  TargetAdd('libp3webgldisplay.dll', input=COMMON_PANDA_LIBS)
  TargetAdd('libp3webgldisplay.dll', opts=['MODULE', 'GLES2', 'WEBGL'])

#
# DIRECTORY: panda/src/ode/
#
if not PkgSkip("ODE"):
    OPTS=['DIR:panda/src/ode', 'BUILDING:PANDAODE', 'ODE']
    TargetAdd('p3ode_composite1.obj', opts=OPTS, input='p3ode_composite1.cxx')
    TargetAdd('p3ode_composite2.obj', opts=OPTS, input='p3ode_composite2.cxx')
    TargetAdd('p3ode_composite3.obj', opts=OPTS, input='p3ode_composite3.cxx')

    OPTS=['DIR:panda/src/ode', 'ODE']
    IGATEFILES=GetDirectoryContents('panda/src/ode', ["*.h", "*_composite*.cxx"])
    IGATEFILES.remove("odeConvexGeom.h")
    IGATEFILES.remove("odeHelperStructs.h")
    TargetAdd('libpandaode.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libpandaode.in', opts=['IMOD:panda3d.ode', 'ILIB:libpandaode', 'SRCDIR:panda/src/ode'])
    PyTargetAdd('p3ode_ext_composite.obj', opts=OPTS, input='p3ode_ext_composite.cxx')

#
# DIRECTORY: panda/metalibs/pandaode/
#
if not PkgSkip("ODE"):
    OPTS=['DIR:panda/metalibs/pandaode', 'BUILDING:PANDAODE', 'ODE']
    TargetAdd('pandaode_pandaode.obj', opts=OPTS, input='pandaode.cxx')

    TargetAdd('libpandaode.dll', input='pandaode_pandaode.obj')
    TargetAdd('libpandaode.dll', input='p3ode_composite1.obj')
    TargetAdd('libpandaode.dll', input='p3ode_composite2.obj')
    TargetAdd('libpandaode.dll', input='p3ode_composite3.obj')
    TargetAdd('libpandaode.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandaode.dll', opts=['WINUSER', 'ODE'])

    OPTS=['DIR:panda/metalibs/pandaode', 'ODE']
    PyTargetAdd('ode_module.obj', input='libpandaode.in')
    PyTargetAdd('ode_module.obj', opts=OPTS)
    PyTargetAdd('ode_module.obj', opts=['IMOD:panda3d.ode', 'ILIB:ode', 'IMPORT:panda3d.core'])

    PyTargetAdd('ode.pyd', input='ode_module.obj')
    PyTargetAdd('ode.pyd', input='libpandaode_igate.obj')
    PyTargetAdd('ode.pyd', input='p3ode_ext_composite.obj')
    PyTargetAdd('ode.pyd', input='libpandaode.dll')
    PyTargetAdd('ode.pyd', input=COMMON_PANDA_LIBS)
    PyTargetAdd('ode.pyd', opts=['WINUSER', 'ODE'])

#
# DIRECTORY: panda/src/bullet/
#
if not PkgSkip("BULLET"):
    OPTS=['DIR:panda/src/bullet', 'BUILDING:PANDABULLET', 'BULLET']
    TargetAdd('p3bullet_composite.obj', opts=OPTS, input='p3bullet_composite.cxx')

    OPTS=['DIR:panda/src/bullet', 'BULLET']
    IGATEFILES=GetDirectoryContents('panda/src/bullet', ["*.h", "*_composite*.cxx"])
    TargetAdd('libpandabullet.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libpandabullet.in', opts=['IMOD:panda3d.bullet', 'ILIB:libpandabullet', 'SRCDIR:panda/src/bullet'])

#
# DIRECTORY: panda/metalibs/pandabullet/
#
if not PkgSkip("BULLET"):
    OPTS=['DIR:panda/metalibs/pandabullet', 'BUILDING:PANDABULLET', 'BULLET']
    TargetAdd('pandabullet_pandabullet.obj', opts=OPTS, input='pandabullet.cxx')

    TargetAdd('libpandabullet.dll', input='pandabullet_pandabullet.obj')
    TargetAdd('libpandabullet.dll', input='p3bullet_composite.obj')
    TargetAdd('libpandabullet.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandabullet.dll', opts=['WINUSER', 'BULLET'])

    OPTS=['DIR:panda/metalibs/pandabullet', 'BULLET']
    PyTargetAdd('bullet_module.obj', input='libpandabullet.in')
    PyTargetAdd('bullet_module.obj', opts=OPTS)
    PyTargetAdd('bullet_module.obj', opts=['IMOD:panda3d.bullet', 'ILIB:bullet', 'IMPORT:panda3d.core'])

    PyTargetAdd('bullet.pyd', input='bullet_module.obj')
    PyTargetAdd('bullet.pyd', input='libpandabullet_igate.obj')
    PyTargetAdd('bullet.pyd', input='libpandabullet.dll')
    PyTargetAdd('bullet.pyd', input=COMMON_PANDA_LIBS)
    PyTargetAdd('bullet.pyd', opts=['WINUSER', 'BULLET'])

#
# DIRECTORY: panda/src/physics/
#

if not PkgSkip("PANDAPHYSICS"):
    OPTS=['DIR:panda/src/physics', 'BUILDING:PANDAPHYSICS']
    TargetAdd('p3physics_composite1.obj', opts=OPTS, input='p3physics_composite1.cxx')
    TargetAdd('p3physics_composite2.obj', opts=OPTS, input='p3physics_composite2.cxx')

    OPTS=['DIR:panda/src/physics']
    IGATEFILES=GetDirectoryContents('panda/src/physics', ["*.h", "*_composite*.cxx"])
    IGATEFILES.remove("forces.h")
    TargetAdd('libp3physics.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3physics.in', opts=['IMOD:panda3d.physics', 'ILIB:libp3physics', 'SRCDIR:panda/src/physics'])

#
# DIRECTORY: panda/src/particlesystem/
#

if not PkgSkip("PANDAPHYSICS") and not PkgSkip("PANDAPARTICLESYSTEM"):
    OPTS=['DIR:panda/src/particlesystem', 'BUILDING:PANDAPHYSICS']
    TargetAdd('p3particlesystem_composite1.obj', opts=OPTS, input='p3particlesystem_composite1.cxx')
    TargetAdd('p3particlesystem_composite2.obj', opts=OPTS, input='p3particlesystem_composite2.cxx')

    OPTS=['DIR:panda/src/particlesystem']
    IGATEFILES=GetDirectoryContents('panda/src/particlesystem', ["*.h", "*_composite*.cxx"])
    IGATEFILES.remove('orientedParticle.h')
    IGATEFILES.remove('orientedParticleFactory.h')
    IGATEFILES.remove('particlefactories.h')
    IGATEFILES.remove('emitters.h')
    IGATEFILES.remove('particles.h')
    TargetAdd('libp3particlesystem.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3particlesystem.in', opts=['IMOD:panda3d.physics', 'ILIB:libp3particlesystem', 'SRCDIR:panda/src/particlesystem'])

#
# DIRECTORY: panda/metalibs/pandaphysics/
#

if not PkgSkip("PANDAPHYSICS"):
    OPTS=['DIR:panda/metalibs/pandaphysics', 'BUILDING:PANDAPHYSICS']
    TargetAdd('pandaphysics_pandaphysics.obj', opts=OPTS, input='pandaphysics.cxx')

    TargetAdd('libpandaphysics.dll', input='pandaphysics_pandaphysics.obj')
    TargetAdd('libpandaphysics.dll', input='p3physics_composite1.obj')
    TargetAdd('libpandaphysics.dll', input='p3physics_composite2.obj')
    TargetAdd('libpandaphysics.dll', input='p3particlesystem_composite1.obj')
    TargetAdd('libpandaphysics.dll', input='p3particlesystem_composite2.obj')
    TargetAdd('libpandaphysics.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandaphysics.dll', opts=['ADVAPI'])

    OPTS=['DIR:panda/metalibs/pandaphysics']
    PyTargetAdd('physics_module.obj', input='libp3physics.in')
    if not PkgSkip("PANDAPARTICLESYSTEM"):
        PyTargetAdd('physics_module.obj', input='libp3particlesystem.in')
    PyTargetAdd('physics_module.obj', opts=OPTS)
    PyTargetAdd('physics_module.obj', opts=['IMOD:panda3d.physics', 'ILIB:physics', 'IMPORT:panda3d.core'])

    PyTargetAdd('physics.pyd', input='physics_module.obj')
    PyTargetAdd('physics.pyd', input='libp3physics_igate.obj')
    if not PkgSkip("PANDAPARTICLESYSTEM"):
        PyTargetAdd('physics.pyd', input='libp3particlesystem_igate.obj')
    PyTargetAdd('physics.pyd', input='libpandaphysics.dll')
    PyTargetAdd('physics.pyd', input=COMMON_PANDA_LIBS)

#
# DIRECTORY: contrib/src/speedtree/
#

if not PkgSkip("SPEEDTREE"):
    OPTS=['DIR:contrib/src/speedtree', 'BUILDING:PANDASPEEDTREE', 'SPEEDTREE']
    TargetAdd('pandaspeedtree_composite1.obj', opts=OPTS, input='pandaspeedtree_composite1.cxx')
    IGATEFILES=GetDirectoryContents('contrib/src/speedtree', ["*.h", "*_composite*.cxx"])
    TargetAdd('libpandaspeedtree.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libpandaspeedtree.in', opts=['IMOD:libpandaspeedtree', 'ILIB:libpandaspeedtree', 'SRCDIR:contrib/src/speedtree'])

    PyTargetAdd('libpandaspeedtree_module.obj', input='libpandaspeedtree.in')
    PyTargetAdd('libpandaspeedtree_module.obj', opts=OPTS)
    PyTargetAdd('libpandaspeedtree_module.obj', opts=['IMOD:libpandaspeedtree', 'ILIB:libpandaspeedtree'])
    TargetAdd('libpandaspeedtree.dll', input='pandaspeedtree_composite1.obj')
    PyTargetAdd('libpandaspeedtree.dll', input='libpandaspeedtree_igate.obj')
    TargetAdd('libpandaspeedtree.dll', input='libpandaspeedtree_module.obj')
    TargetAdd('libpandaspeedtree.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandaspeedtree.dll', opts=['SPEEDTREE'])
    if SDK["SPEEDTREEAPI"] == 'OpenGL':
        TargetAdd('libpandaspeedtree.dll', opts=['GL', 'NVIDIACG', 'CGGL'])
    elif SDK["SPEEDTREEAPI"] == 'DirectX9':
        TargetAdd('libpandaspeedtree.dll', opts=['DX9', 'NVIDIACG', 'CGDX9'])

#
# DIRECTORY: panda/src/testbed/
#

if not PkgSkip("PVIEW"):
    OPTS=['DIR:panda/src/testbed']
    TargetAdd('pview_pview.obj', opts=OPTS, input='pview.cxx')
    TargetAdd('pview.exe', input='pview_pview.obj')
    TargetAdd('pview.exe', input='libp3framework.dll')
    if not PkgSkip("EGG"):
        TargetAdd('pview.exe', input='libpandaegg.dll')
    TargetAdd('pview.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('pview.exe', opts=['ADVAPI', 'WINSOCK2', 'WINSHELL'])

    if GetLinkAllStatic() and not PkgSkip("GL"):
        TargetAdd('pview.exe', input='libpandagl.dll')
    if GetTarget() == "emscripten" and not PkgSkip("GLES2"):
        TargetAdd('pview.exe', input='libp3webgldisplay.dll')

#
# DIRECTORY: panda/src/android/
#

if GetTarget() == 'android':
    OPTS=['DIR:panda/src/android', 'PNG']
    TargetAdd('org/panda3d/android/NativeIStream.class', opts=OPTS, input='NativeIStream.java')
    TargetAdd('org/panda3d/android/NativeOStream.class', opts=OPTS, input='NativeOStream.java')
    TargetAdd('org/panda3d/android/PandaActivity.class', opts=OPTS, input='PandaActivity.java')
    TargetAdd('org/panda3d/android/PandaActivity$1.class', opts=OPTS+['DEPENDENCYONLY'], input='PandaActivity.java')
    TargetAdd('org/panda3d/android/PythonActivity.class', opts=OPTS, input='PythonActivity.java')

    TargetAdd('classes.dex', input='org/panda3d/android/NativeIStream.class')
    TargetAdd('classes.dex', input='org/panda3d/android/NativeOStream.class')
    TargetAdd('classes.dex', input='org/panda3d/android/PandaActivity.class')
    TargetAdd('classes.dex', input='org/panda3d/android/PandaActivity$1.class')
    TargetAdd('classes.dex', input='org/panda3d/android/PythonActivity.class')

    TargetAdd('p3android_composite1.obj', opts=OPTS, input='p3android_composite1.cxx')
    TargetAdd('libp3android.dll', input='p3android_composite1.obj')
    TargetAdd('libp3android.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libp3android.dll', opts=['JNIGRAPHICS'])

    TargetAdd('android_native_app_glue.obj', opts=OPTS + ['NOHIDDEN'], input='android_native_app_glue.c')
    TargetAdd('android_main.obj', opts=OPTS, input='android_main.cxx')

    if not PkgSkip("PVIEW"):
        TargetAdd('libpview_pview.obj', opts=OPTS, input='pview.cxx')
        TargetAdd('libpview.dll', input='android_native_app_glue.obj')
        TargetAdd('libpview.dll', input='android_main.obj')
        TargetAdd('libpview.dll', input='libpview_pview.obj')
        TargetAdd('libpview.dll', input='libp3framework.dll')
        if not PkgSkip("EGG"):
            TargetAdd('libpview.dll', input='libpandaegg.dll')
        TargetAdd('libpview.dll', input='libp3android.dll')
        TargetAdd('libpview.dll', input=COMMON_PANDA_LIBS)
        TargetAdd('libpview.dll', opts=['MODULE', 'ANDROID'])

    if not PkgSkip("PYTHON"):
        OPTS += ['PYTHON']
        TargetAdd('ppython_ppython.obj', opts=OPTS, input='python_main.cxx')
        TargetAdd('libppython.dll', input='android_native_app_glue.obj')
        TargetAdd('libppython.dll', input='android_main.obj')
        TargetAdd('libppython.dll', input='ppython_ppython.obj')
        TargetAdd('libppython.dll', input='libp3framework.dll')
        TargetAdd('libppython.dll', input='libp3android.dll')
        TargetAdd('libppython.dll', input=COMMON_PANDA_LIBS)
        TargetAdd('libppython.dll', opts=['MODULE', 'ANDROID', 'PYTHON'])

#
# DIRECTORY: panda/src/androiddisplay/
#

if GetTarget() == 'android' and not PkgSkip("EGL") and not PkgSkip("GLES"):
    DefSymbol('GLES', 'OPENGLES_1', '')
    OPTS=['DIR:panda/src/androiddisplay', 'DIR:panda/src/glstuff', 'BUILDING:PANDAGLES', 'GLES', 'EGL']
    TargetAdd('pandagles_androiddisplay_composite1.obj', opts=OPTS, input='p3androiddisplay_composite1.cxx')
    OPTS=['DIR:panda/metalibs/pandagles', 'BUILDING:PANDAGLES', 'GLES', 'EGL']
    TargetAdd('pandagles_pandagles.obj', opts=OPTS, input='pandagles.cxx')
    TargetAdd('libpandagles.dll', input='pandagles_pandagles.obj')
    TargetAdd('libpandagles.dll', input='p3glesgsg_config_glesgsg.obj')
    TargetAdd('libpandagles.dll', input='p3glesgsg_glesgsg.obj')
    TargetAdd('libpandagles.dll', input='pandagles_androiddisplay_composite1.obj')
    TargetAdd('libpandagles.dll', input='libp3android.dll')
    TargetAdd('libpandagles.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandagles.dll', opts=['MODULE', 'GLES', 'EGL'])

if GetTarget() == 'android' and not PkgSkip("EGL") and not PkgSkip("GLES2"):
    DefSymbol('GLES2', 'OPENGLES_2', '')
    OPTS=['DIR:panda/src/androiddisplay', 'DIR:panda/src/glstuff', 'BUILDING:PANDAGLES2', 'GLES2', 'EGL']
    TargetAdd('pandagles2_androiddisplay_composite1.obj', opts=OPTS, input='p3androiddisplay_composite1.cxx')
    OPTS=['DIR:panda/metalibs/pandagles2', 'BUILDING:PANDAGLES2', 'GLES2', 'EGL']
    TargetAdd('pandagles2_pandagles2.obj', opts=OPTS, input='pandagles2.cxx')
    TargetAdd('libpandagles2.dll', input='pandagles2_pandagles2.obj')
    TargetAdd('libpandagles2.dll', input='p3gles2gsg_config_gles2gsg.obj')
    TargetAdd('libpandagles2.dll', input='p3gles2gsg_gles2gsg.obj')
    TargetAdd('libpandagles2.dll', input='pandagles2_androiddisplay_composite1.obj')
    TargetAdd('libpandagles2.dll', input='libp3android.dll')
    TargetAdd('libpandagles2.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libpandagles2.dll', opts=['MODULE', 'GLES2', 'EGL'])

#
# DIRECTORY: panda/src/tinydisplay/
#

if not PkgSkip("TINYDISPLAY"):
    OPTS=['DIR:panda/src/tinydisplay', 'BUILDING:TINYDISPLAY', 'X11']
    if not PkgSkip("X11"):
        OPTS += ['X11']
    if not PkgSkip("COCOA"):
        OPTS += ['COCOA']
    TargetAdd('p3tinydisplay_composite1.obj', opts=OPTS, input='p3tinydisplay_composite1.cxx')
    TargetAdd('p3tinydisplay_composite2.obj', opts=OPTS, input='p3tinydisplay_composite2.cxx')
    TargetAdd('p3tinydisplay_ztriangle_1.obj', opts=OPTS, input='ztriangle_1.cxx')
    TargetAdd('p3tinydisplay_ztriangle_2.obj', opts=OPTS, input='ztriangle_2.cxx')
    TargetAdd('p3tinydisplay_ztriangle_3.obj', opts=OPTS, input='ztriangle_3.cxx')
    TargetAdd('p3tinydisplay_ztriangle_4.obj', opts=OPTS, input='ztriangle_4.cxx')
    TargetAdd('p3tinydisplay_ztriangle_table.obj', opts=OPTS, input='ztriangle_table.cxx')
    if GetTarget() == 'windows':
        TargetAdd('libp3tinydisplay.dll', input='libp3windisplay.dll')
        TargetAdd('libp3tinydisplay.dll', opts=['WINIMM', 'WINGDI', 'WINKERNEL', 'WINOLDNAMES', 'WINUSER', 'WINMM'])
    elif GetTarget() == 'darwin':
        if not PkgSkip("COCOA"):
            TargetAdd('libp3tinydisplay_tinyCocoaGraphicsWindow.obj', opts=OPTS, input='tinyCocoaGraphicsWindow.mm')
            TargetAdd('libp3tinydisplay.dll', input='libp3tinydisplay_tinyCocoaGraphicsWindow.obj')
            TargetAdd('libp3tinydisplay.dll', input='p3cocoadisplay_composite1.obj')
            TargetAdd('libp3tinydisplay.dll', opts=['COCOA', 'CARBON', 'QUARTZ'])
    elif not PkgSkip("X11"):
        TargetAdd('libp3tinydisplay.dll', input='p3x11display_composite1.obj')
        TargetAdd('libp3tinydisplay.dll', opts=['X11'])
    TargetAdd('libp3tinydisplay.dll', input='p3tinydisplay_composite1.obj')
    TargetAdd('libp3tinydisplay.dll', input='p3tinydisplay_composite2.obj')
    TargetAdd('libp3tinydisplay.dll', input='p3tinydisplay_ztriangle_1.obj')
    TargetAdd('libp3tinydisplay.dll', input='p3tinydisplay_ztriangle_2.obj')
    TargetAdd('libp3tinydisplay.dll', input='p3tinydisplay_ztriangle_3.obj')
    TargetAdd('libp3tinydisplay.dll', input='p3tinydisplay_ztriangle_4.obj')
    TargetAdd('libp3tinydisplay.dll', input='p3tinydisplay_ztriangle_table.obj')
    TargetAdd('libp3tinydisplay.dll', input=COMMON_PANDA_LIBS)

#
# DIRECTORY: direct/src/directbase/
#

if not PkgSkip("DIRECT"):
    OPTS=['DIR:direct/src/directbase']
    TargetAdd('p3directbase_directbase.obj', opts=OPTS+['BUILDING:DIRECT'], input='directbase.cxx')

#
# DIRECTORY: direct/src/dcparser/
#

if not PkgSkip("DIRECT"):
    OPTS=['DIR:direct/src/dcparser', 'BUILDING:DIRECT_DCPARSER', 'WITHINPANDA', 'BISONPREFIX_dcyy']
    CreateFile(GetOutputDir()+"/include/dcParser.h")
    TargetAdd('p3dcparser_dcParser.obj', opts=OPTS, input='dcParser.yxx')
    TargetAdd('dcParser.h', input='p3dcparser_dcParser.obj', opts=['DEPENDENCYONLY'])
    TargetAdd('p3dcparser_dcLexer.obj', opts=OPTS, input='dcLexer.lxx')
    TargetAdd('p3dcparser_composite1.obj', opts=OPTS, input='p3dcparser_composite1.cxx')
    TargetAdd('p3dcparser_composite2.obj', opts=OPTS, input='p3dcparser_composite2.cxx')

    OPTS=['DIR:direct/src/dcparser', 'WITHINPANDA']
    IGATEFILES=GetDirectoryContents('direct/src/dcparser', ["*.h", "*_composite*.cxx"])
    if "dcParser.h" in IGATEFILES:
        IGATEFILES.remove("dcParser.h")
    if "dcmsgtypes.h" in IGATEFILES:
        IGATEFILES.remove('dcmsgtypes.h')
    TargetAdd('libp3dcparser.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3dcparser.in', opts=['IMOD:panda3d.direct', 'ILIB:libp3dcparser', 'SRCDIR:direct/src/dcparser'])
    PyTargetAdd('p3dcparser_ext_composite.obj', opts=OPTS, input='p3dcparser_ext_composite.cxx')

#
# DIRECTORY: direct/src/deadrec/
#

if not PkgSkip("DIRECT"):
    OPTS=['DIR:direct/src/deadrec', 'BUILDING:DIRECT']
    TargetAdd('p3deadrec_composite1.obj', opts=OPTS, input='p3deadrec_composite1.cxx')

    OPTS=['DIR:direct/src/deadrec']
    IGATEFILES=GetDirectoryContents('direct/src/deadrec', ["*.h", "*_composite*.cxx"])
    TargetAdd('libp3deadrec.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3deadrec.in', opts=['IMOD:panda3d.direct', 'ILIB:libp3deadrec', 'SRCDIR:direct/src/deadrec'])

#
# DIRECTORY: direct/src/distributed/
#

if not PkgSkip("DIRECT") and GetTarget() != 'emscripten':
    OPTS=['DIR:direct/src/distributed', 'DIR:direct/src/dcparser', 'WITHINPANDA', 'BUILDING:DIRECT']
    TargetAdd('p3distributed_config_distributed.obj', opts=OPTS, input='config_distributed.cxx')

    OPTS=['DIR:direct/src/distributed', 'WITHINPANDA']
    IGATEFILES=GetDirectoryContents('direct/src/distributed', ["*.h", "*.cxx"])
    TargetAdd('libp3distributed.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3distributed.in', opts=['IMOD:panda3d.direct', 'ILIB:libp3distributed', 'SRCDIR:direct/src/distributed'])
    PyTargetAdd('p3distributed_cConnectionRepository.obj', opts=OPTS, input='cConnectionRepository.cxx')
    PyTargetAdd('p3distributed_cDistributedSmoothNodeBase.obj', opts=OPTS, input='cDistributedSmoothNodeBase.cxx')

#
# DIRECTORY: direct/src/interval/
#

if not PkgSkip("DIRECT"):
    OPTS=['DIR:direct/src/interval', 'BUILDING:DIRECT']
    TargetAdd('p3interval_composite1.obj', opts=OPTS, input='p3interval_composite1.cxx')

    OPTS=['DIR:direct/src/interval']
    IGATEFILES=GetDirectoryContents('direct/src/interval', ["*.h", "*_composite*.cxx"])
    TargetAdd('libp3interval.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3interval.in', opts=['IMOD:panda3d.direct', 'ILIB:libp3interval', 'SRCDIR:direct/src/interval'])
    PyTargetAdd('p3interval_cInterval_ext.obj', opts=OPTS, input='cInterval_ext.cxx')

#
# DIRECTORY: direct/src/showbase/
#

if not PkgSkip("DIRECT"):
    OPTS=['DIR:direct/src/showbase', 'BUILDING:DIRECT']
    TargetAdd('p3showbase_showBase.obj', opts=OPTS, input='showBase.cxx')
    if GetTarget() == 'darwin':
        TargetAdd('p3showbase_showBase_assist.obj', opts=OPTS, input='showBase_assist.mm')

    OPTS=['DIR:direct/src/showbase']
    IGATEFILES=GetDirectoryContents('direct/src/showbase', ["*.h", "showBase.cxx"])
    TargetAdd('libp3showbase.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3showbase.in', opts=['IMOD:panda3d.direct', 'ILIB:libp3showbase', 'SRCDIR:direct/src/showbase'])

#
# DIRECTORY: direct/src/motiontrail/
#

if not PkgSkip("DIRECT"):
    OPTS=['DIR:direct/src/motiontrail', 'BUILDING:DIRECT']
    TargetAdd('p3motiontrail_cMotionTrail.obj', opts=OPTS, input='cMotionTrail.cxx')
    TargetAdd('p3motiontrail_config_motiontrail.obj', opts=OPTS, input='config_motiontrail.cxx')

    OPTS=['DIR:direct/src/motiontrail']
    IGATEFILES=GetDirectoryContents('direct/src/motiontrail', ["*.h", "cMotionTrail.cxx"])
    TargetAdd('libp3motiontrail.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3motiontrail.in', opts=['IMOD:panda3d.direct', 'ILIB:libp3motiontrail', 'SRCDIR:direct/src/motiontrail'])

#
# DIRECTORY: direct/metalibs/direct/
#

if not PkgSkip("DIRECT"):
    TargetAdd('libp3direct.dll', input='p3directbase_directbase.obj')
    TargetAdd('libp3direct.dll', input='p3dcparser_composite1.obj')
    TargetAdd('libp3direct.dll', input='p3dcparser_composite2.obj')
    TargetAdd('libp3direct.dll', input='p3dcparser_dcParser.obj')
    TargetAdd('libp3direct.dll', input='p3dcparser_dcLexer.obj')
    TargetAdd('libp3direct.dll', input='p3showbase_showBase.obj')
    if GetTarget() == 'darwin':
        TargetAdd('libp3direct.dll', input='p3showbase_showBase_assist.obj')
    TargetAdd('libp3direct.dll', input='p3deadrec_composite1.obj')
    if GetTarget() != 'emscripten':
        TargetAdd('libp3direct.dll', input='p3distributed_config_distributed.obj')
    TargetAdd('libp3direct.dll', input='p3interval_composite1.obj')
    TargetAdd('libp3direct.dll', input='p3motiontrail_config_motiontrail.obj')
    TargetAdd('libp3direct.dll', input='p3motiontrail_cMotionTrail.obj')
    TargetAdd('libp3direct.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libp3direct.dll', opts=['ADVAPI', 'WINUSER', 'WINGDI'])

    PyTargetAdd('direct_module.obj', input='libp3dcparser.in')
    PyTargetAdd('direct_module.obj', input='libp3showbase.in')
    PyTargetAdd('direct_module.obj', input='libp3deadrec.in')
    PyTargetAdd('direct_module.obj', input='libp3interval.in')
    if GetTarget() != 'emscripten':
        PyTargetAdd('direct_module.obj', input='libp3distributed.in')
    PyTargetAdd('direct_module.obj', input='libp3motiontrail.in')
    PyTargetAdd('direct_module.obj', opts=['IMOD:panda3d.direct', 'ILIB:direct', 'IMPORT:panda3d.core'])

    PyTargetAdd('direct.pyd', input='libp3dcparser_igate.obj')
    PyTargetAdd('direct.pyd', input='libp3showbase_igate.obj')
    PyTargetAdd('direct.pyd', input='libp3deadrec_igate.obj')
    PyTargetAdd('direct.pyd', input='libp3interval_igate.obj')
    PyTargetAdd('direct.pyd', input='p3interval_cInterval_ext.obj')
    if GetTarget() != 'emscripten':
        PyTargetAdd('direct.pyd', input='libp3distributed_igate.obj')
    PyTargetAdd('direct.pyd', input='libp3motiontrail_igate.obj')

    # These are part of direct.pyd, not libp3direct.dll, because they rely on
    # the Python libraries.  If a C++ user needs these modules, we can move them
    # back and filter out the Python-specific code.
    PyTargetAdd('direct.pyd', input='p3dcparser_ext_composite.obj')
    if GetTarget() != 'emscripten':
        PyTargetAdd('direct.pyd', input='p3distributed_cConnectionRepository.obj')
        PyTargetAdd('direct.pyd', input='p3distributed_cDistributedSmoothNodeBase.obj')

    PyTargetAdd('direct.pyd', input='direct_module.obj')
    PyTargetAdd('direct.pyd', input='libp3direct.dll')
    PyTargetAdd('direct.pyd', input=COMMON_PANDA_LIBS)
    PyTargetAdd('direct.pyd', opts=['WINUSER', 'WINGDI', 'WINSOCK2'])

#
# DIRECTORY: direct/src/dcparse/
#

if not PkgSkip("DIRECT"):
    OPTS=['DIR:direct/src/dcparse', 'DIR:direct/src/dcparser', 'WITHINPANDA', 'ADVAPI']
    TargetAdd('dcparse_dcparse.obj', opts=OPTS, input='dcparse.cxx')
    TargetAdd('p3dcparse.exe', input='dcparse_dcparse.obj')
    TargetAdd('p3dcparse.exe', input='libp3direct.dll')
    TargetAdd('p3dcparse.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('p3dcparse.exe', opts=['ADVAPI'])

#
# DIRECTORY: panda/src/nametag/
#
if not PkgSkip("NAMETAG"):
    OPTS=['DIR:panda/src/nametag', 'BUILDING:OTP']
    TargetAdd('p3nametag_composite1.obj', opts=OPTS, input='nametag_composite1.cxx')
    TargetAdd('p3nametag_composite2.obj', opts=OPTS, input='nametag_composite2.cxx')

    OPTS=['DIR:panda/src/nametag']
    IGATEFILES=GetDirectoryContents('panda/src/nametag', ["*.h", "*_composite*.cxx"])
    TargetAdd('libp3nametag.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3nametag.in', opts=['IMOD:panda3d.otp', 'ILIB:libp3nametag', 'SRCDIR:panda/src/nametag'])

#
# DIRECTORY: panda/src/movement/
#
if not PkgSkip("MOVEMENT"):
    OPTS=['DIR:panda/src/movement', 'BUILDING:OTP']
    TargetAdd('p3movement_composite1.obj', opts=OPTS, input='movement_composite1.cxx')

    OPTS=['DIR:panda/src/movement']
    IGATEFILES=GetDirectoryContents('panda/src/movement', ["*.h", "*_composite*.cxx"])
    TargetAdd('libp3movement.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3movement.in', opts=['IMOD:panda3d.otp', 'ILIB:libp3movement', 'SRCDIR:panda/src/movement'])

#
# DIRECTORY: panda/src/navigation/
#
if not PkgSkip("NAVIGATION"):
    OPTS=['DIR:panda/src/navigation', 'BUILDING:OTP']
    PyTargetAdd('p3navigation_composite1.obj', opts=OPTS, input='navigation_composite1.cxx')

    OPTS=['DIR:panda/src/navigation']
    IGATEFILES=GetDirectoryContents('panda/src/navigation', ["*.h", "*_composite*.cxx"])
    TargetAdd('libp3navigation.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3navigation.in', opts=['IMOD:panda3d.otp', 'ILIB:libp3navigation', 'SRCDIR:panda/src/navigation'])

#
# DIRECTORY: panda/src/nametag/
# DIRECTORY: panda/src/movement/
# DIRECTORY: panda/src/navigation/
#
if not PkgSkip("NAMETAG") or not PkgSkip("MOVEMENT") or not PkgSkip("NAVIGATION"):
    if not PkgSkip("NAMETAG"):
        TargetAdd('libp3otp.dll', input='p3nametag_composite1.obj')
        TargetAdd('libp3otp.dll', input='p3nametag_composite2.obj')
        TargetAdd('libp3otp.dll', input='libp3direct.dll')
    if not PkgSkip("MOVEMENT"):
        TargetAdd('libp3otp.dll', input='p3movement_composite1.obj')
    if not PkgSkip("NAVIGATION"):
        PyTargetAdd('libp3otp.dll', input='p3navigation_composite1.obj')
    TargetAdd('libp3otp.dll', input=COMMON_PANDA_LIBS)

    if not PkgSkip("NAMETAG"):
        PyTargetAdd('otp_module.obj', input='libp3nametag.in')
    if not PkgSkip("MOVEMENT"):
        PyTargetAdd('otp_module.obj', input='libp3movement.in')
    if not PkgSkip("NAVIGATION"):
        PyTargetAdd('otp_module.obj', input='libp3navigation.in')
    PyTargetAdd('otp_module.obj', opts=['IMOD:panda3d.otp', 'ILIB:otp', 'IMPORT:panda3d.core'])

    PyTargetAdd('otp.pyd', input='otp_module.obj')
    if not PkgSkip("NAMETAG"):
        PyTargetAdd('otp.pyd', input='libp3nametag_igate.obj')
    if not PkgSkip("MOVEMENT"):
        PyTargetAdd('otp.pyd', input='libp3movement_igate.obj')
    if not PkgSkip("NAVIGATION"):
        PyTargetAdd('otp.pyd', input='libp3navigation_igate.obj')
    PyTargetAdd('otp.pyd', input='libp3otp.dll')
    PyTargetAdd('otp.pyd', input=COMMON_PANDA_LIBS)

#
# DIRECTORY: panda/src/dna/
#
if not PkgSkip("DNA"):
    OPTS=['DIR:panda/src/dna', 'BUILDING:TOONTOWN']
    TargetAdd('p3dna_composite1.obj', opts=OPTS, input='dnaLoader_composite1.cxx')
    TargetAdd('p3dna_composite2.obj', opts=OPTS, input='dnaLoader_composite2.cxx')

    OPTS=['DIR:panda/src/dna', 'BUILDING:TOONTOWN', 'BISONPREFIX_dnayy', 'FLEXDASHI']
    CreateFile(GetOutputDir()+"/include/dnaParser.h")
    TargetAdd('p3dna_dnaParser.obj', opts=OPTS, input='dnaParser.yxx')
    TargetAdd('dnaParser.h', input='p3dna_dnaParser.obj', opts=['DEPENDENCYONLY'])
    TargetAdd('p3dna_dnaLexer.obj', opts=OPTS, input='dnaLexer.lxx')

    OPTS=['DIR:panda/src/dna']
    IGATEFILES=GetDirectoryContents('panda/src/dna', ["*.h", "*_composite*.cxx"])
    if "dnaParser.h" in IGATEFILES: IGATEFILES.remove("dnaParser.h")
    TargetAdd('libp3dna.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3dna.in', opts=['IMOD:panda3d.toontown', 'ILIB:libp3dna', 'SRCDIR:panda/src/dna'])

#
# DIRECTORY: panda/src/suit/
#
if not PkgSkip("SUIT"):
    if PkgSkip("DNA"):
        exit("libp3suit depends on libp3dna.")

    OPTS=['DIR:panda/src/suit', 'BUILDING:TOONTOWN']
    TargetAdd('p3suit_composite1.obj', opts=OPTS, input='suit_composite1.cxx')

    OPTS=['DIR:panda/src/suit']
    IGATEFILES=GetDirectoryContents('panda/src/suit', ["*.h", "*_composite*.cxx"])
    TargetAdd('libp3suit.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3suit.in', opts=['IMOD:panda3d.toontown', 'ILIB:libp3suit', 'SRCDIR:panda/src/suit'])

#
# DIRECTORY: panda/src/pets/
#
if not PkgSkip("PETS"):
    if PkgSkip("MOVEMENT"):
        exit("libp3pets depends on libp3movement.")

    OPTS=['DIR:panda/src/pets', 'BUILDING:TOONTOWN']
    TargetAdd('p3pets_composite1.obj', opts=OPTS, input='pets_composite1.cxx')

    OPTS=['DIR:panda/src/pets']
    IGATEFILES=GetDirectoryContents('panda/src/pets', ["*.h", "*_composite*.cxx"])
    TargetAdd('libp3pets.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3pets.in', opts=['IMOD:panda3d.toontown', 'ILIB:libp3pets', 'SRCDIR:panda/src/pets'])

#
# DIRECTORY: panda/src/dna/
# DIRECTORY: panda/src/suit/
# DIRECTORY: panda/src/pets/
#
if not PkgSkip("DNA") or not PkgSkip("SUIT") or not PkgSkip("PETS"):
    if not PkgSkip("DNA"):
        TargetAdd('libp3toontown.dll', input='p3dna_composite1.obj')
        TargetAdd('libp3toontown.dll', input='p3dna_composite2.obj')
        TargetAdd('libp3toontown.dll', input='p3dna_dnaParser.obj')
        TargetAdd('libp3toontown.dll', input='p3dna_dnaLexer.obj')
        if not PkgSkip("SUIT"):
            TargetAdd('libp3toontown.dll', input='p3suit_composite1.obj')
    if not PkgSkip("PETS"):
        TargetAdd('libp3toontown.dll', input='p3pets_composite1.obj')
        TargetAdd('libp3toontown.dll', input='libp3otp.dll')
    TargetAdd('libp3toontown.dll', input=COMMON_PANDA_LIBS)

    if not PkgSkip("DNA"):
        PyTargetAdd('toontown_module.obj', input='libp3dna.in')
        if not PkgSkip("SUIT"):
            PyTargetAdd('toontown_module.obj', input='libp3suit.in')
    if not PkgSkip("PETS"):
        PyTargetAdd('toontown_module.obj', input='libp3pets.in')
        PyTargetAdd('toontown_module.obj', opts=['IMOD:panda3d.toontown', 'ILIB:toontown', 'IMPORT:panda3d.otp'])
    else:
        PyTargetAdd('toontown_module.obj', opts=['IMOD:panda3d.toontown', 'ILIB:toontown', 'IMPORT:panda3d.core'])

    PyTargetAdd('toontown.pyd', input='toontown_module.obj')
    if not PkgSkip("DNA"):
        PyTargetAdd('toontown.pyd', input='libp3dna_igate.obj')
        if not PkgSkip("SUIT"):
            PyTargetAdd('toontown.pyd', input='libp3suit_igate.obj')
    if not PkgSkip("PETS"):
        PyTargetAdd('toontown.pyd', input='libp3pets_igate.obj')
    PyTargetAdd('toontown.pyd', input='libp3otp.dll')
    PyTargetAdd('toontown.pyd', input='libp3toontown.dll')
    PyTargetAdd('toontown.pyd', input=COMMON_PANDA_LIBS)

#
# DIRECTORY: pandatool/src/pandatoolbase/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/pandatoolbase']
    TargetAdd('p3pandatoolbase_composite1.obj', opts=OPTS, input='p3pandatoolbase_composite1.cxx')
    TargetAdd('libp3pandatoolbase.lib', input='p3pandatoolbase_composite1.obj')

#
# DIRECTORY: pandatool/src/converter/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/converter']
    TargetAdd('p3converter_somethingToEggConverter.obj', opts=OPTS, input='somethingToEggConverter.cxx')
    TargetAdd('p3converter_eggToSomethingConverter.obj', opts=OPTS, input='eggToSomethingConverter.cxx')
    TargetAdd('libp3converter.lib', input='p3converter_somethingToEggConverter.obj')
    TargetAdd('libp3converter.lib', input='p3converter_eggToSomethingConverter.obj')

#
# DIRECTORY: pandatool/src/progbase/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/progbase', 'ZLIB']
    TargetAdd('p3progbase_composite1.obj', opts=OPTS, input='p3progbase_composite1.cxx')
    TargetAdd('libp3progbase.lib', input='p3progbase_composite1.obj')

#
# DIRECTORY: pandatool/src/eggbase/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/eggbase']
    TargetAdd('p3eggbase_composite1.obj', opts=OPTS, input='p3eggbase_composite1.cxx')
    TargetAdd('libp3eggbase.lib', input='p3eggbase_composite1.obj')

#
# DIRECTORY: pandatool/src/bam/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/bam']
    TargetAdd('bam-info_bamInfo.obj', opts=OPTS, input='bamInfo.cxx')
    TargetAdd('bam-info.exe', input='bam-info_bamInfo.obj')
    TargetAdd('bam-info.exe', input='libp3progbase.lib')
    TargetAdd('bam-info.exe', input='libp3pandatoolbase.lib')
    TargetAdd('bam-info.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('bam-info.exe', opts=['ADVAPI', 'FFTW'])

    if not PkgSkip("EGG"):
        TargetAdd('bam2egg_bamToEgg.obj', opts=OPTS, input='bamToEgg.cxx')
        TargetAdd('bam2egg.exe', input='bam2egg_bamToEgg.obj')
        TargetAdd('bam2egg.exe', input=COMMON_EGG2X_LIBS)
        TargetAdd('bam2egg.exe', opts=['ADVAPI', 'FFTW'])

        TargetAdd('egg2bam_eggToBam.obj', opts=OPTS, input='eggToBam.cxx')
        TargetAdd('egg2bam.exe', input='egg2bam_eggToBam.obj')
        TargetAdd('egg2bam.exe', input=COMMON_EGG2X_LIBS)
        TargetAdd('egg2bam.exe', opts=['ADVAPI', 'FFTW'])

#
# DIRECTORY: pandatool/src/daeegg/
#
if not PkgSkip("PANDATOOL") and not PkgSkip("FCOLLADA") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/daeegg', 'FCOLLADA']
    TargetAdd('p3daeegg_composite1.obj', opts=OPTS, input='p3daeegg_composite1.cxx')
    TargetAdd('libp3daeegg.lib', input='p3daeegg_composite1.obj')
    TargetAdd('libp3daeegg.lib', opts=['FCOLLADA', 'CARBON'])

#
# DIRECTORY: pandatool/src/assimp
#
if not PkgSkip("PANDATOOL") and not PkgSkip("ASSIMP"):
    OPTS=['DIR:pandatool/src/assimp', 'BUILDING:ASSIMP', 'ASSIMP', 'MODULE']
    TargetAdd('p3assimp_composite1.obj', opts=OPTS, input='p3assimp_composite1.cxx')
    TargetAdd('libp3assimp.dll', input='p3assimp_composite1.obj')
    TargetAdd('libp3assimp.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libp3assimp.dll', opts=OPTS+['ZLIB', 'ADVAPI'])

#
# DIRECTORY: pandatool/src/daeprogs/
#
if not PkgSkip("PANDATOOL") and not PkgSkip("FCOLLADA") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/daeprogs', 'FCOLLADA']
    TargetAdd('dae2egg_daeToEgg.obj', opts=OPTS, input='daeToEgg.cxx')
    TargetAdd('dae2egg.exe', input='dae2egg_daeToEgg.obj')
    TargetAdd('dae2egg.exe', input='libp3daeegg.lib')
    TargetAdd('dae2egg.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('dae2egg.exe', opts=['WINUSER', 'FCOLLADA', 'CARBON'])

#
# DIRECTORY: pandatool/src/dxf/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/dxf']
    TargetAdd('p3dxf_composite1.obj', opts=OPTS, input='p3dxf_composite1.cxx')
    TargetAdd('libp3dxf.lib', input='p3dxf_composite1.obj')

#
# DIRECTORY: pandatool/src/dxfegg/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/dxfegg']
    TargetAdd('p3dxfegg_dxfToEggConverter.obj', opts=OPTS, input='dxfToEggConverter.cxx')
    TargetAdd('p3dxfegg_dxfToEggLayer.obj', opts=OPTS, input='dxfToEggLayer.cxx')
    TargetAdd('libp3dxfegg.lib', input='p3dxfegg_dxfToEggConverter.obj')
    TargetAdd('libp3dxfegg.lib', input='p3dxfegg_dxfToEggLayer.obj')

#
# DIRECTORY: pandatool/src/dxfprogs/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/dxfprogs']
    TargetAdd('dxf-points_dxfPoints.obj', opts=OPTS, input='dxfPoints.cxx')
    TargetAdd('dxf-points.exe', input='dxf-points_dxfPoints.obj')
    TargetAdd('dxf-points.exe', input='libp3progbase.lib')
    TargetAdd('dxf-points.exe', input='libp3dxf.lib')
    TargetAdd('dxf-points.exe', input='libp3pandatoolbase.lib')
    TargetAdd('dxf-points.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('dxf-points.exe', opts=['ADVAPI', 'FFTW'])

    if not PkgSkip("EGG"):
        TargetAdd('dxf2egg_dxfToEgg.obj', opts=OPTS, input='dxfToEgg.cxx')
        TargetAdd('dxf2egg.exe', input='dxf2egg_dxfToEgg.obj')
        TargetAdd('dxf2egg.exe', input='libp3dxfegg.lib')
        TargetAdd('dxf2egg.exe', input='libp3dxf.lib')
        TargetAdd('dxf2egg.exe', input=COMMON_EGG2X_LIBS)
        TargetAdd('dxf2egg.exe', opts=['ADVAPI', 'FFTW'])

        TargetAdd('egg2dxf_eggToDXF.obj', opts=OPTS, input='eggToDXF.cxx')
        TargetAdd('egg2dxf_eggToDXFLayer.obj', opts=OPTS, input='eggToDXFLayer.cxx')
        TargetAdd('egg2dxf.exe', input='egg2dxf_eggToDXF.obj')
        TargetAdd('egg2dxf.exe', input='egg2dxf_eggToDXFLayer.obj')
        TargetAdd('egg2dxf.exe', input='libp3dxf.lib')
        TargetAdd('egg2dxf.exe', input=COMMON_EGG2X_LIBS)
        TargetAdd('egg2dxf.exe', opts=['ADVAPI', 'FFTW'])

#
# DIRECTORY: pandatool/src/objegg/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/objegg']
    TargetAdd('p3objegg_objToEggConverter.obj', opts=OPTS, input='objToEggConverter.cxx')
    TargetAdd('p3objegg_eggToObjConverter.obj', opts=OPTS, input='eggToObjConverter.cxx')
    TargetAdd('p3objegg_config_objegg.obj', opts=OPTS, input='config_objegg.cxx')
    TargetAdd('libp3objegg.lib', input='p3objegg_objToEggConverter.obj')
    TargetAdd('libp3objegg.lib', input='p3objegg_eggToObjConverter.obj')
    TargetAdd('libp3objegg.lib', input='p3objegg_config_objegg.obj')

#
# DIRECTORY: pandatool/src/objprogs/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/objprogs']
    TargetAdd('obj2egg_objToEgg.obj', opts=OPTS, input='objToEgg.cxx')
    TargetAdd('obj2egg.exe', input='obj2egg_objToEgg.obj')
    TargetAdd('obj2egg.exe', input='libp3objegg.lib')
    TargetAdd('obj2egg.exe', input=COMMON_EGG2X_LIBS)

    TargetAdd('egg2obj_eggToObj.obj', opts=OPTS, input='eggToObj.cxx')
    TargetAdd('egg2obj.exe', input='egg2obj_eggToObj.obj')
    TargetAdd('egg2obj.exe', input='libp3objegg.lib')
    TargetAdd('egg2obj.exe', input=COMMON_EGG2X_LIBS)

#
# DIRECTORY: pandatool/src/palettizer/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/palettizer']
    TargetAdd('p3palettizer_composite1.obj', opts=OPTS, input='p3palettizer_composite1.cxx')
    TargetAdd('libp3palettizer.lib', input='p3palettizer_composite1.obj')

#
# DIRECTORY: pandatool/src/egg-mkfont/
#

if not PkgSkip("FREETYPE") and not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/egg-mkfont', 'DIR:pandatool/src/palettizer', 'FREETYPE']
    TargetAdd('egg-mkfont_eggMakeFont.obj', opts=OPTS, input='eggMakeFont.cxx')
    TargetAdd('egg-mkfont_rangeDescription.obj', opts=OPTS, input='rangeDescription.cxx')
    TargetAdd('egg-mkfont_rangeIterator.obj', opts=OPTS, input='rangeIterator.cxx')
    TargetAdd('egg-mkfont.exe', input='egg-mkfont_eggMakeFont.obj')
    TargetAdd('egg-mkfont.exe', input='egg-mkfont_rangeDescription.obj')
    TargetAdd('egg-mkfont.exe', input='egg-mkfont_rangeIterator.obj')
    TargetAdd('egg-mkfont.exe', input='libp3palettizer.lib')
    TargetAdd('egg-mkfont.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('egg-mkfont.exe', opts=['ADVAPI', 'FREETYPE'])

#
# DIRECTORY: pandatool/src/eggcharbase/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/eggcharbase', 'ZLIB']
    TargetAdd('p3eggcharbase_composite1.obj', opts=OPTS, input='p3eggcharbase_composite1.cxx')
    TargetAdd('libp3eggcharbase.lib', input='p3eggcharbase_composite1.obj')

#
# DIRECTORY: pandatool/src/egg-optchar/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/egg-optchar']
    TargetAdd('egg-optchar_config_egg_optchar.obj', opts=OPTS, input='config_egg_optchar.cxx')
    TargetAdd('egg-optchar_eggOptchar.obj', opts=OPTS, input='eggOptchar.cxx')
    TargetAdd('egg-optchar_eggOptcharUserData.obj', opts=OPTS, input='eggOptcharUserData.cxx')
    TargetAdd('egg-optchar_vertexMembership.obj', opts=OPTS, input='vertexMembership.cxx')
    TargetAdd('egg-optchar.exe', input='egg-optchar_config_egg_optchar.obj')
    TargetAdd('egg-optchar.exe', input='egg-optchar_eggOptchar.obj')
    TargetAdd('egg-optchar.exe', input='egg-optchar_eggOptcharUserData.obj')
    TargetAdd('egg-optchar.exe', input='egg-optchar_vertexMembership.obj')
    TargetAdd('egg-optchar.exe', input='libp3eggcharbase.lib')
    TargetAdd('egg-optchar.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('egg-optchar.exe', opts=['ADVAPI', 'FREETYPE'])

#
# DIRECTORY: pandatool/src/egg-palettize/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/egg-palettize', 'DIR:pandatool/src/palettizer']
    TargetAdd('egg-palettize_eggPalettize.obj', opts=OPTS, input='eggPalettize.cxx')
    TargetAdd('egg-palettize.exe', input='egg-palettize_eggPalettize.obj')
    TargetAdd('egg-palettize.exe', input='libp3palettizer.lib')
    TargetAdd('egg-palettize.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('egg-palettize.exe', opts=['ADVAPI'])

#
# DIRECTORY: pandatool/src/egg-qtess/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/egg-qtess']
    TargetAdd('egg-qtess_composite1.obj', opts=OPTS, input='egg-qtess_composite1.cxx')
    TargetAdd('egg-qtess.exe', input='egg-qtess_composite1.obj')
    TargetAdd('egg-qtess.exe', input='libp3eggbase.lib')
    TargetAdd('egg-qtess.exe', input='libp3progbase.lib')
    TargetAdd('egg-qtess.exe', input='libp3converter.lib')
    TargetAdd('egg-qtess.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('egg-qtess.exe', opts=['ADVAPI'])

#
# DIRECTORY: pandatool/src/eggprogs/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/eggprogs']
    TargetAdd('egg-crop_eggCrop.obj', opts=OPTS, input='eggCrop.cxx')
    TargetAdd('egg-crop.exe', input='egg-crop_eggCrop.obj')
    TargetAdd('egg-crop.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('egg-crop.exe', opts=['ADVAPI'])

    TargetAdd('egg-make-tube_eggMakeTube.obj', opts=OPTS, input='eggMakeTube.cxx')
    TargetAdd('egg-make-tube.exe', input='egg-make-tube_eggMakeTube.obj')
    TargetAdd('egg-make-tube.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('egg-make-tube.exe', opts=['ADVAPI'])

    TargetAdd('egg-texture-cards_eggTextureCards.obj', opts=OPTS, input='eggTextureCards.cxx')
    TargetAdd('egg-texture-cards.exe', input='egg-texture-cards_eggTextureCards.obj')
    TargetAdd('egg-texture-cards.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('egg-texture-cards.exe', opts=['ADVAPI'])

    TargetAdd('egg-topstrip_eggTopstrip.obj', opts=OPTS, input='eggTopstrip.cxx')
    TargetAdd('egg-topstrip.exe', input='egg-topstrip_eggTopstrip.obj')
    TargetAdd('egg-topstrip.exe', input='libp3eggcharbase.lib')
    TargetAdd('egg-topstrip.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('egg-topstrip.exe', opts=['ADVAPI'])

    TargetAdd('egg-trans_eggTrans.obj', opts=OPTS, input='eggTrans.cxx')
    TargetAdd('egg-trans.exe', input='egg-trans_eggTrans.obj')
    TargetAdd('egg-trans.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('egg-trans.exe', opts=['ADVAPI'])

    TargetAdd('egg2c_eggToC.obj', opts=OPTS, input='eggToC.cxx')
    TargetAdd('egg2c.exe', input='egg2c_eggToC.obj')
    TargetAdd('egg2c.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('egg2c.exe', opts=['ADVAPI'])

    TargetAdd('egg-rename_eggRename.obj', opts=OPTS, input='eggRename.cxx')
    TargetAdd('egg-rename.exe', input='egg-rename_eggRename.obj')
    TargetAdd('egg-rename.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('egg-rename.exe', opts=['ADVAPI'])

    TargetAdd('egg-retarget-anim_eggRetargetAnim.obj', opts=OPTS, input='eggRetargetAnim.cxx')
    TargetAdd('egg-retarget-anim.exe', input='egg-retarget-anim_eggRetargetAnim.obj')
    TargetAdd('egg-retarget-anim.exe', input='libp3eggcharbase.lib')
    TargetAdd('egg-retarget-anim.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('egg-retarget-anim.exe', opts=['ADVAPI'])

    TargetAdd('egg-list-textures_eggListTextures.obj', opts=OPTS, input='eggListTextures.cxx')
    TargetAdd('egg-list-textures.exe', input='egg-list-textures_eggListTextures.obj')
    TargetAdd('egg-list-textures.exe', input=COMMON_EGG2X_LIBS)
    TargetAdd('egg-list-textures.exe', opts=['ADVAPI'])

#
# DIRECTORY: pandatool/src/flt/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/flt', 'ZLIB']
    TargetAdd('p3flt_composite1.obj', opts=OPTS, input='p3flt_composite1.cxx')
    TargetAdd('libp3flt.lib', input=['p3flt_composite1.obj'])

#
# DIRECTORY: pandatool/src/fltegg/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/fltegg']
    TargetAdd('p3fltegg_fltToEggConverter.obj', opts=OPTS, input='fltToEggConverter.cxx')
    TargetAdd('p3fltegg_fltToEggLevelState.obj', opts=OPTS, input='fltToEggLevelState.cxx')
    TargetAdd('libp3fltegg.lib', input=['p3fltegg_fltToEggConverter.obj', 'p3fltegg_fltToEggLevelState.obj'])

#
# DIRECTORY: pandatool/src/fltprogs/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/fltprogs', 'DIR:pandatool/src/flt']
    TargetAdd('flt-info_fltInfo.obj', opts=OPTS, input='fltInfo.cxx')
    TargetAdd('flt-info.exe', input='flt-info_fltInfo.obj')
    TargetAdd('flt-info.exe', input='libp3flt.lib')
    TargetAdd('flt-info.exe', input='libp3progbase.lib')
    TargetAdd('flt-info.exe', input='libp3pandatoolbase.lib')
    TargetAdd('flt-info.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('flt-info.exe', opts=['ADVAPI'])

    TargetAdd('flt-trans_fltTrans.obj', opts=OPTS, input='fltTrans.cxx')
    TargetAdd('flt-trans.exe', input='flt-trans_fltTrans.obj')
    TargetAdd('flt-trans.exe', input='libp3flt.lib')
    TargetAdd('flt-trans.exe', input='libp3progbase.lib')
    TargetAdd('flt-trans.exe', input='libp3pandatoolbase.lib')
    TargetAdd('flt-trans.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('flt-trans.exe', opts=['ADVAPI'])

    if not PkgSkip("EGG"):
        TargetAdd('egg2flt_eggToFlt.obj', opts=OPTS, input='eggToFlt.cxx')
        TargetAdd('egg2flt.exe', input='egg2flt_eggToFlt.obj')
        TargetAdd('egg2flt.exe', input='libp3flt.lib')
        TargetAdd('egg2flt.exe', input=COMMON_EGG2X_LIBS)
        TargetAdd('egg2flt.exe', opts=['ADVAPI'])

        TargetAdd('flt2egg_fltToEgg.obj', opts=OPTS, input='fltToEgg.cxx')
        TargetAdd('flt2egg.exe', input='flt2egg_fltToEgg.obj')
        TargetAdd('flt2egg.exe', input='libp3flt.lib')
        TargetAdd('flt2egg.exe', input='libp3fltegg.lib')
        TargetAdd('flt2egg.exe', input=COMMON_EGG2X_LIBS)
        TargetAdd('flt2egg.exe', opts=['ADVAPI'])

#
# DIRECTORY: pandatool/src/imagebase/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/imagebase']
    TargetAdd('p3imagebase_composite1.obj', opts=OPTS, input='p3imagebase_composite1.cxx')
    TargetAdd('libp3imagebase.lib', input='p3imagebase_composite1.obj')

#
# DIRECTORY: pandatool/src/imageprogs/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/imageprogs']
    TargetAdd('image-info_imageInfo.obj', opts=OPTS, input='imageInfo.cxx')
    TargetAdd('image-info.exe', input='image-info_imageInfo.obj')
    TargetAdd('image-info.exe', input='libp3imagebase.lib')
    TargetAdd('image-info.exe', input='libp3progbase.lib')
    TargetAdd('image-info.exe', input='libp3pandatoolbase.lib')
    TargetAdd('image-info.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('image-info.exe', opts=['ADVAPI'])

    TargetAdd('image-resize_imageResize.obj', opts=OPTS, input='imageResize.cxx')
    TargetAdd('image-resize.exe', input='image-resize_imageResize.obj')
    TargetAdd('image-resize.exe', input='libp3imagebase.lib')
    TargetAdd('image-resize.exe', input='libp3progbase.lib')
    TargetAdd('image-resize.exe', input='libp3pandatoolbase.lib')
    TargetAdd('image-resize.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('image-resize.exe', opts=['ADVAPI'])

    TargetAdd('image-trans_imageTrans.obj', opts=OPTS, input='imageTrans.cxx')
    TargetAdd('image-trans.exe', input='image-trans_imageTrans.obj')
    TargetAdd('image-trans.exe', input='libp3imagebase.lib')
    TargetAdd('image-trans.exe', input='libp3progbase.lib')
    TargetAdd('image-trans.exe', input='libp3pandatoolbase.lib')
    TargetAdd('image-trans.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('image-trans.exe', opts=['ADVAPI'])

#
# DIRECTORY: pandatool/src/pfmprogs/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/pfmprogs']
    TargetAdd('pfm-trans_pfmTrans.obj', opts=OPTS, input='pfmTrans.cxx')
    TargetAdd('pfm-trans.exe', input='pfm-trans_pfmTrans.obj')
    TargetAdd('pfm-trans.exe', input='libp3progbase.lib')
    TargetAdd('pfm-trans.exe', input='libp3pandatoolbase.lib')
    TargetAdd('pfm-trans.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('pfm-trans.exe', opts=['ADVAPI'])

    TargetAdd('pfm-bba_pfmBba.obj', opts=OPTS, input='pfmBba.cxx')
    TargetAdd('pfm-bba_config_pfmprogs.obj', opts=OPTS, input='config_pfmprogs.cxx')
    TargetAdd('pfm-bba.exe', input='pfm-bba_pfmBba.obj')
    TargetAdd('pfm-bba.exe', input='pfm-bba_config_pfmprogs.obj')
    TargetAdd('pfm-bba.exe', input='libp3progbase.lib')
    TargetAdd('pfm-bba.exe', input='libp3pandatoolbase.lib')
    TargetAdd('pfm-bba.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('pfm-bba.exe', opts=['ADVAPI'])

#
# DIRECTORY: pandatool/src/lwo/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/lwo']
    TargetAdd('p3lwo_composite1.obj', opts=OPTS, input='p3lwo_composite1.cxx')
    TargetAdd('libp3lwo.lib', input='p3lwo_composite1.obj')

#
# DIRECTORY: pandatool/src/lwoegg/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/lwoegg']
    TargetAdd('p3lwoegg_composite1.obj', opts=OPTS, input='p3lwoegg_composite1.cxx')
    TargetAdd('libp3lwoegg.lib', input='p3lwoegg_composite1.obj')

#
# DIRECTORY: pandatool/src/lwoprogs/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/lwoprogs', 'DIR:pandatool/src/lwo']
    TargetAdd('lwo-scan_lwoScan.obj', opts=OPTS, input='lwoScan.cxx')
    TargetAdd('lwo-scan.exe', input='lwo-scan_lwoScan.obj')
    TargetAdd('lwo-scan.exe', input='libp3lwo.lib')
    TargetAdd('lwo-scan.exe', input='libp3progbase.lib')
    TargetAdd('lwo-scan.exe', input='libp3pandatoolbase.lib')
    TargetAdd('lwo-scan.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('lwo-scan.exe', opts=['ADVAPI'])

    if not PkgSkip("EGG"):
        TargetAdd('lwo2egg_lwoToEgg.obj', opts=OPTS, input='lwoToEgg.cxx')
        TargetAdd('lwo2egg.exe', input='lwo2egg_lwoToEgg.obj')
        TargetAdd('lwo2egg.exe', input='libp3lwo.lib')
        TargetAdd('lwo2egg.exe', input='libp3lwoegg.lib')
        TargetAdd('lwo2egg.exe', input=COMMON_EGG2X_LIBS)
        TargetAdd('lwo2egg.exe', opts=['ADVAPI'])

#
# DIRECTORY: pandatool/src/vrml/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/vrml', 'ZLIB', 'BISONPREFIX_vrmlyy']
    CreateFile(GetOutputDir() + "/include/vrmlParser.h")
    TargetAdd('p3vrml_vrmlParser.obj', opts=OPTS, input='vrmlParser.yxx')
    TargetAdd('vrmlParser.h', input='p3vrml_vrmlParser.obj', opts=['DEPENDENCYONLY'])
    TargetAdd('p3vrml_vrmlLexer.obj', opts=OPTS, input='vrmlLexer.lxx')
    TargetAdd('p3vrml_parse_vrml.obj', opts=OPTS, input='parse_vrml.cxx')
    TargetAdd('p3vrml_standard_nodes.obj', opts=OPTS, input='standard_nodes.cxx')
    TargetAdd('p3vrml_vrmlNode.obj', opts=OPTS, input='vrmlNode.cxx')
    TargetAdd('p3vrml_vrmlNodeType.obj', opts=OPTS, input='vrmlNodeType.cxx')
    TargetAdd('libp3vrml.lib', input='p3vrml_parse_vrml.obj')
    TargetAdd('libp3vrml.lib', input='p3vrml_standard_nodes.obj')
    TargetAdd('libp3vrml.lib', input='p3vrml_vrmlNode.obj')
    TargetAdd('libp3vrml.lib', input='p3vrml_vrmlNodeType.obj')
    TargetAdd('libp3vrml.lib', input='p3vrml_vrmlParser.obj')
    TargetAdd('libp3vrml.lib', input='p3vrml_vrmlLexer.obj')

#
# DIRECTORY: pandatool/src/vrmlegg/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/vrmlegg', 'DIR:pandatool/src/vrml']
    TargetAdd('p3vrmlegg_indexedFaceSet.obj', opts=OPTS, input='indexedFaceSet.cxx')
    TargetAdd('p3vrmlegg_vrmlAppearance.obj', opts=OPTS, input='vrmlAppearance.cxx')
    TargetAdd('p3vrmlegg_vrmlToEggConverter.obj', opts=OPTS, input='vrmlToEggConverter.cxx')
    TargetAdd('libp3vrmlegg.lib', input='p3vrmlegg_indexedFaceSet.obj')
    TargetAdd('libp3vrmlegg.lib', input='p3vrmlegg_vrmlAppearance.obj')
    TargetAdd('libp3vrmlegg.lib', input='p3vrmlegg_vrmlToEggConverter.obj')

#
# DIRECTORY: pandatool/src/xfile/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/xfile', 'ZLIB', 'BISONPREFIX_xyy', 'FLEXDASHI']
    CreateFile(GetOutputDir() + "/include/xParser.h")
    TargetAdd('p3xfile_xParser.obj', opts=OPTS, input='xParser.yxx')
    TargetAdd('xParser.h', input='p3xfile_xParser.obj', opts=['DEPENDENCYONLY'])
    TargetAdd('p3xfile_xLexer.obj', opts=OPTS, input='xLexer.lxx')
    TargetAdd('p3xfile_composite1.obj', opts=OPTS, input='p3xfile_composite1.cxx')
    TargetAdd('libp3xfile.lib', input='p3xfile_composite1.obj')
    TargetAdd('libp3xfile.lib', input='p3xfile_xParser.obj')
    TargetAdd('libp3xfile.lib', input='p3xfile_xLexer.obj')

#
# DIRECTORY: pandatool/src/xfileegg/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    OPTS=['DIR:pandatool/src/xfileegg', 'DIR:pandatool/src/xfile']
    TargetAdd('p3xfileegg_composite1.obj', opts=OPTS, input='p3xfileegg_composite1.cxx')
    TargetAdd('libp3xfileegg.lib', input='p3xfileegg_composite1.obj')

#
# DIRECTORY: pandatool/src/ptloader/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("EGG"):
    if not PkgSkip("FCOLLADA"):
        DefSymbol("FCOLLADA", "HAVE_FCOLLADA")

    OPTS=['DIR:pandatool/src/ptloader', 'DIR:pandatool/src/flt', 'DIR:pandatool/src/lwo', 'DIR:pandatool/src/xfile', 'DIR:pandatool/src/xfileegg', 'DIR:pandatool/src/daeegg', 'BUILDING:PTLOADER', 'FCOLLADA']
    TargetAdd('p3ptloader_config_ptloader.obj', opts=OPTS, input='config_ptloader.cxx', dep='dtool_have_fcollada.dat')
    TargetAdd('p3ptloader_loaderFileTypePandatool.obj', opts=OPTS, input='loaderFileTypePandatool.cxx')
    TargetAdd('libp3ptloader.dll', input='p3ptloader_config_ptloader.obj')
    TargetAdd('libp3ptloader.dll', input='p3ptloader_loaderFileTypePandatool.obj')
    TargetAdd('libp3ptloader.dll', input='libp3fltegg.lib')
    TargetAdd('libp3ptloader.dll', input='libp3flt.lib')
    TargetAdd('libp3ptloader.dll', input='libp3lwoegg.lib')
    TargetAdd('libp3ptloader.dll', input='libp3lwo.lib')
    TargetAdd('libp3ptloader.dll', input='libp3dxfegg.lib')
    TargetAdd('libp3ptloader.dll', input='libp3dxf.lib')
    #TargetAdd('libp3ptloader.dll', input='libp3objegg.lib')
    TargetAdd('libp3ptloader.dll', input='libp3vrmlegg.lib')
    TargetAdd('libp3ptloader.dll', input='libp3vrml.lib')
    TargetAdd('libp3ptloader.dll', input='libp3xfileegg.lib')
    TargetAdd('libp3ptloader.dll', input='libp3xfile.lib')
    if not PkgSkip("FCOLLADA"): TargetAdd('libp3ptloader.dll', input='libp3daeegg.lib')
    TargetAdd('libp3ptloader.dll', input='libp3eggbase.lib')
    TargetAdd('libp3ptloader.dll', input='libp3progbase.lib')
    TargetAdd('libp3ptloader.dll', input='libp3converter.lib')
    TargetAdd('libp3ptloader.dll', input='libp3pandatoolbase.lib')
    TargetAdd('libp3ptloader.dll', input='libpandaegg.dll')
    TargetAdd('libp3ptloader.dll', input=COMMON_PANDA_LIBS)
    TargetAdd('libp3ptloader.dll', opts=['MODULE', 'ADVAPI', 'FCOLLADA', 'WINUSER'])

#
# DIRECTORY: pandatool/src/miscprogs/
#

# This is a bit of an esoteric tool, and it causes issues because
# it conflicts with tools of the same name in different packages.
#if not PkgSkip("PANDATOOL"):
#    OPTS=['DIR:pandatool/src/miscprogs']
#    TargetAdd('bin2c_binToC.obj', opts=OPTS, input='binToC.cxx')
#    TargetAdd('bin2c.exe', input='bin2c_binToC.obj')
#    TargetAdd('bin2c.exe', input='libp3progbase.lib')
#    TargetAdd('bin2c.exe', input='libp3pandatoolbase.lib')
#    TargetAdd('bin2c.exe', input=COMMON_PANDA_LIBS)
#    TargetAdd('bin2c.exe', opts=['ADVAPI'])

#
# DIRECTORY: pandatool/src/pstatserver/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/pstatserver']
    TargetAdd('p3pstatserver_composite1.obj', opts=OPTS, input='p3pstatserver_composite1.cxx')
    TargetAdd('libp3pstatserver.lib', input='p3pstatserver_composite1.obj')

#
# DIRECTORY: pandatool/src/text-stats/
#

if not PkgSkip("PANDATOOL") and GetTarget() != 'emscripten':
    OPTS=['DIR:pandatool/src/text-stats']
    TargetAdd('text-stats_textMonitor.obj', opts=OPTS, input='textMonitor.cxx')
    TargetAdd('text-stats_textStats.obj', opts=OPTS, input='textStats.cxx')
    TargetAdd('text-stats.exe', input='text-stats_textMonitor.obj')
    TargetAdd('text-stats.exe', input='text-stats_textStats.obj')
    TargetAdd('text-stats.exe', input='libp3progbase.lib')
    TargetAdd('text-stats.exe', input='libp3pstatserver.lib')
    TargetAdd('text-stats.exe', input='libp3pandatoolbase.lib')
    TargetAdd('text-stats.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('text-stats.exe', opts=['ADVAPI'])

#
# DIRECTORY: pandatool/src/vrmlprogs/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/vrmlprogs', 'DIR:pandatool/src/vrml', 'DIR:pandatool/src/vrmlegg']
    TargetAdd('vrml-trans_vrmlTrans.obj', opts=OPTS, input='vrmlTrans.cxx')
    TargetAdd('vrml-trans.exe', input='vrml-trans_vrmlTrans.obj')
    TargetAdd('vrml-trans.exe', input='libp3vrml.lib')
    TargetAdd('vrml-trans.exe', input='libp3progbase.lib')
    TargetAdd('vrml-trans.exe', input='libp3pandatoolbase.lib')
    TargetAdd('vrml-trans.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('vrml-trans.exe', opts=['ADVAPI'])

    if not PkgSkip("EGG"):
        TargetAdd('vrml2egg_vrmlToEgg.obj', opts=OPTS, input='vrmlToEgg.cxx')
        TargetAdd('vrml2egg.exe', input='vrml2egg_vrmlToEgg.obj')
        TargetAdd('vrml2egg.exe', input='libp3vrmlegg.lib')
        TargetAdd('vrml2egg.exe', input='libp3vrml.lib')
        TargetAdd('vrml2egg.exe', input=COMMON_EGG2X_LIBS)
        TargetAdd('vrml2egg.exe', opts=['ADVAPI'])

#
# DIRECTORY: pandatool/src/win-stats/
# DIRECTORY: pandatool/src/gtk-stats/
#

if not PkgSkip("PANDATOOL") and (GetTarget() in ('windows', 'darwin') or not PkgSkip("GTK3")):
    if GetTarget() == 'windows':
        OPTS=['DIR:pandatool/src/win-stats']
        TargetAdd('pstats_composite1.obj', opts=OPTS, input='winstats_composite1.cxx')
    elif GetTarget() == 'darwin':
        OPTS=['DIR:pandatool/src/mac-stats']
        TargetAdd('pstats_composite1.obj', opts=OPTS, input='macstats_composite1.mm')
    else:
        OPTS=['DIR:pandatool/src/gtk-stats', 'GTK3']
        TargetAdd('pstats_composite1.obj', opts=OPTS, input='gtkstats_composite1.cxx')
    TargetAdd('pstats.exe', input='pstats_composite1.obj')
    TargetAdd('pstats.exe', input='libp3pstatserver.lib')
    TargetAdd('pstats.exe', input='libp3progbase.lib')
    TargetAdd('pstats.exe', input='libp3pandatoolbase.lib')
    TargetAdd('pstats.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('pstats.exe', opts=['SUBSYSTEM:WINDOWS', 'WINCOMCTL', 'WINCOMDLG', 'WINSOCK', 'WINIMM', 'WINGDI', 'WINKERNEL', 'WINOLDNAMES', 'WINUSER', 'WINMM', 'UXTHEME', 'GTK3', 'COCOA', 'CARBON', 'QUARTZ'])

#
# DIRECTORY: pandatool/src/xfileprogs/
#

if not PkgSkip("PANDATOOL"):
    OPTS=['DIR:pandatool/src/xfileprogs', 'DIR:pandatool/src/xfile', 'DIR:pandatool/src/xfileegg']
    TargetAdd('x-trans_xFileTrans.obj', opts=OPTS, input='xFileTrans.cxx')
    TargetAdd('x-trans.exe', input='x-trans_xFileTrans.obj')
    TargetAdd('x-trans.exe', input='libp3progbase.lib')
    TargetAdd('x-trans.exe', input='libp3xfile.lib')
    TargetAdd('x-trans.exe', input='libp3pandatoolbase.lib')
    TargetAdd('x-trans.exe', input=COMMON_PANDA_LIBS)
    TargetAdd('x-trans.exe', opts=['ADVAPI'])

    if not PkgSkip("EGG"):
        TargetAdd('egg2x_eggToX.obj', opts=OPTS, input='eggToX.cxx')
        TargetAdd('egg2x.exe', input='egg2x_eggToX.obj')
        TargetAdd('egg2x.exe', input='libp3xfileegg.lib')
        TargetAdd('egg2x.exe', input='libp3xfile.lib')
        TargetAdd('egg2x.exe', input=COMMON_EGG2X_LIBS)
        TargetAdd('egg2x.exe', opts=['ADVAPI'])

        TargetAdd('x2egg_xFileToEgg.obj', opts=OPTS, input='xFileToEgg.cxx')
        TargetAdd('x2egg.exe', input='x2egg_xFileToEgg.obj')
        TargetAdd('x2egg.exe', input='libp3xfileegg.lib')
        TargetAdd('x2egg.exe', input='libp3xfile.lib')
        TargetAdd('x2egg.exe', input=COMMON_EGG2X_LIBS)
        TargetAdd('x2egg.exe', opts=['ADVAPI'])

#
# DIRECTORY: pandatool/src/dnaprogs/
#

if not PkgSkip("PANDATOOL") and not PkgSkip("DNA"):
  OPTS=['DIR:pandatool/src/dnaprogs']
  TargetAdd('dna-trans_dnaTrans.obj', opts=OPTS, input='dnaTrans.cxx')
  TargetAdd('dna-trans.exe', input='dna-trans_dnaTrans.obj')
  TargetAdd('dna-trans.exe', input=COMMON_PANDA_LIBS)
  TargetAdd('dna-trans.exe', input='libp3toontown.dll')
  TargetAdd('dna-trans.exe', opts=['ADVAPI'])

#
# DIRECTORY: contrib/src/ai/
#
if not PkgSkip("CONTRIB"):
    OPTS=['DIR:contrib/src/ai', 'BUILDING:PANDAAI']
    TargetAdd('p3ai_composite1.obj', opts=OPTS, input='p3ai_composite1.cxx')
    TargetAdd('libpandaai.dll', input='p3ai_composite1.obj')
    TargetAdd('libpandaai.dll', input=COMMON_PANDA_LIBS)

    OPTS=['DIR:contrib/src/ai']
    IGATEFILES=GetDirectoryContents('contrib/src/ai', ["*.h", "*_composite*.cxx"])
    TargetAdd('libpandaai.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libpandaai.in', opts=['IMOD:panda3d.ai', 'ILIB:libpandaai', 'SRCDIR:contrib/src/ai'])

    PyTargetAdd('ai_module.obj', input='libpandaai.in')
    PyTargetAdd('ai_module.obj', opts=OPTS)
    PyTargetAdd('ai_module.obj', opts=['IMOD:panda3d.ai', 'ILIB:ai', 'IMPORT:panda3d.core'])

    PyTargetAdd('ai.pyd', input='ai_module.obj')
    PyTargetAdd('ai.pyd', input='libpandaai_igate.obj')
    PyTargetAdd('ai.pyd', input='libpandaai.dll')
    PyTargetAdd('ai.pyd', input=COMMON_PANDA_LIBS)

#
# DIRECTORY: contrib/src/rplight/
#
if not PkgSkip("CONTRIB") and not PkgSkip("PYTHON"):
    OPTS=['DIR:contrib/src/rplight', 'BUILDING:RPLIGHT']
    TargetAdd('p3rplight_composite1.obj', opts=OPTS, input='p3rplight_composite1.cxx')

    IGATEFILES=GetDirectoryContents('contrib/src/rplight', ["*.h", "*_composite*.cxx"])
    TargetAdd('libp3rplight.in', opts=OPTS, input=IGATEFILES)
    TargetAdd('libp3rplight.in', opts=['IMOD:panda3d._rplight', 'ILIB:libp3rplight', 'SRCDIR:contrib/src/rplight'])

    PyTargetAdd('rplight_module.obj', input='libp3rplight.in')
    PyTargetAdd('rplight_module.obj', opts=OPTS)
    PyTargetAdd('rplight_module.obj', opts=['IMOD:panda3d._rplight', 'ILIB:_rplight', 'IMPORT:panda3d.core'])

    PyTargetAdd('_rplight.pyd', input='rplight_module.obj')
    PyTargetAdd('_rplight.pyd', input='libp3rplight_igate.obj')
    PyTargetAdd('_rplight.pyd', input='p3rplight_composite1.obj')
    PyTargetAdd('_rplight.pyd', input=COMMON_PANDA_LIBS)

#
# DIRECTORY: pandatool/src/deploy-stub
#
if PkgSkip("PYTHON") == 0:
    OPTS=['DIR:pandatool/src/deploy-stub', 'BUILDING:DEPLOYSTUB']
    PyTargetAdd('deploy-stub.obj', opts=OPTS, input='deploy-stub.c')
    if GetTarget() == 'windows':
        PyTargetAdd('frozen_dllmain.obj', opts=OPTS, input='frozen_dllmain.c')

    if GetTarget() == 'linux' or GetTarget() == 'freebsd':
        # Setup rpath so libs can be found in the same directory as the deployed game
        LibName('DEPLOYSTUB', "-Wl,--disable-new-dtags,-rpath,\\$ORIGIN")
        LibName('DEPLOYSTUB', "-Wl,-z,origin")
        LibName('DEPLOYSTUB', "-rdynamic")
    elif GetTarget() == 'darwin':
        LibName('DEPLOYSTUB', "-Wl,-sectcreate,__PANDA,__panda,/dev/null")

    PyTargetAdd('deploy-stub.exe', input='deploy-stub.obj')
    if GetTarget() == 'windows':
        PyTargetAdd('deploy-stub.exe', input='frozen_dllmain.obj')
    PyTargetAdd('deploy-stub.exe', opts=['WINSHELL', 'DEPLOYSTUB', 'NOICON', 'ANDROID'])

    if GetTarget() == 'emscripten':
        PyTargetAdd('deploy-stub.exe', opts=['ZLIB'])

    if GetTarget() == 'windows':
        PyTargetAdd('deploy-stubw.exe', input='deploy-stub.obj')
        PyTargetAdd('deploy-stubw.exe', input='frozen_dllmain.obj')
        PyTargetAdd('deploy-stubw.exe', opts=['SUBSYSTEM:WINDOWS', 'WINSHELL', 'DEPLOYSTUB', 'NOICON'])
    elif GetTarget() == 'darwin':
        DefSymbol('MACOS_APP_BUNDLE', 'MACOS_APP_BUNDLE')
        OPTS = OPTS + ['MACOS_APP_BUNDLE']
        PyTargetAdd('deploy-stubw.obj', opts=OPTS, input='deploy-stub.c')
        PyTargetAdd('deploy-stubw.exe', input='deploy-stubw.obj')
        PyTargetAdd('deploy-stubw.exe', opts=['MACOS_APP_BUNDLE', 'DEPLOYSTUB', 'NOICON'])
    elif GetTarget() == 'android':
        TargetAdd('org/jnius/NativeInvocationHandler.class', opts=OPTS, input='NativeInvocationHandler.java')
        TargetAdd('classes.dex', input='org/jnius/NativeInvocationHandler.class')

        PyTargetAdd('deploy-stubw_android_main.obj', opts=OPTS, input='android_main.cxx')
        PyTargetAdd('deploy-stubw_android_log.obj', opts=OPTS, input='android_log.c')
        PyTargetAdd('libdeploy-stubw.dll', input='android_native_app_glue.obj')
        PyTargetAdd('libdeploy-stubw.dll', input='deploy-stubw_android_main.obj')
        PyTargetAdd('libdeploy-stubw.dll', input='deploy-stubw_android_log.obj')
        PyTargetAdd('libdeploy-stubw.dll', input=COMMON_PANDA_LIBS)
        PyTargetAdd('libdeploy-stubw.dll', input='libp3android.dll')
        PyTargetAdd('libdeploy-stubw.dll', opts=['DEPLOYSTUB', 'ANDROID'])

#
# Build the test runner for static builds
#
if GetLinkAllStatic():
    if GetTarget() == 'emscripten':
        LinkFlag('RUN_TESTS_FLAGS', '-s NODERAWFS')
        LinkFlag('RUN_TESTS_FLAGS', '-s ASSERTIONS=2')
        LinkFlag('RUN_TESTS_FLAGS', '-s ALLOW_MEMORY_GROWTH')
        LinkFlag('RUN_TESTS_FLAGS', '-s INITIAL_HEAP=585302016')
        LinkFlag('RUN_TESTS_FLAGS', '-s STACK_SIZE=1048576')
        LinkFlag('RUN_TESTS_FLAGS', '--minify 0')

    if not PkgSkip('DIRECT'):
        DefSymbol('RUN_TESTS_FLAGS', 'HAVE_DIRECT')
    if not PkgSkip('PANDAPHYSICS'):
        DefSymbol('RUN_TESTS_FLAGS', 'HAVE_PHYSICS')
    if not PkgSkip('EGG'):
        DefSymbol('RUN_TESTS_FLAGS', 'HAVE_EGG')
    if not PkgSkip('BULLET'):
        DefSymbol('RUN_TESTS_FLAGS', 'HAVE_BULLET')

    OPTS=['DIR:tests', 'PYTHON', 'RUN_TESTS_FLAGS', 'SUBSYSTEM:CONSOLE']
    PyTargetAdd('run_tests-main.obj', opts=OPTS, input='main.c')
    PyTargetAdd('run_tests.exe', input='run_tests-main.obj')
    PyTargetAdd('run_tests.exe', input='core.pyd')
    if not PkgSkip('DIRECT'):
        PyTargetAdd('run_tests.exe', input='direct.pyd')
    if not PkgSkip('PANDAPHYSICS'):
        PyTargetAdd('run_tests.exe', input='physics.pyd')
    if not PkgSkip('EGG'):
        PyTargetAdd('run_tests.exe', input='egg.pyd')
    if not PkgSkip('BULLET'):
        PyTargetAdd('run_tests.exe', input='bullet.pyd')
    PyTargetAdd('run_tests.exe', input=COMMON_PANDA_LIBS)
    PyTargetAdd('run_tests.exe', opts=['PYTHON', 'BULLET', 'RUN_TESTS_FLAGS'])

#
# Generate the models directory and samples directory
#

if not PkgSkip("DIRECT") and not PkgSkip("EGG"):
    model_extensions = ["*.egg"]

    for model in GetDirectoryContents("models/misc", model_extensions):
        if not PkgSkip("ZLIB") and not PkgSkip("DEPLOYTOOLS"):
            newname = model[:-4] + ".egg.pz"
        else:
            newname = model[:-4] + ".egg"
        TargetAdd(GetOutputDir()+"/models/misc/"+newname, input="models/misc/"+model)

    for model in GetDirectoryContents("models/gui", model_extensions):
        if not PkgSkip("ZLIB") and not PkgSkip("DEPLOYTOOLS"):
            newname = model[:-4] + ".egg.pz"
        else:
            newname = model[:-4] + ".egg"
        TargetAdd(GetOutputDir()+"/models/gui/"+newname, input="models/gui/"+model)

    for model in GetDirectoryContents("models", model_extensions):
        if not PkgSkip("ZLIB") and not PkgSkip("DEPLOYTOOLS"):
            newname = model[:-4] + ".egg.pz"
        else:
            newname = model[:-4] + ".egg"
        TargetAdd(GetOutputDir()+"/models/"+newname, input="models/"+model)

if not PkgSkip("DIRECT"):
    CopyAllFiles(GetOutputDir()+"/models/audio/sfx/",  "models/audio/sfx/",      ".wav")
    CopyAllFiles(GetOutputDir()+"/models/icons/",      "models/icons/",          ".gif")

    CopyAllFiles(GetOutputDir()+"/models/maps/",       "models/maps/",           ".jpg")
    CopyAllFiles(GetOutputDir()+"/models/maps/",       "models/maps/",           ".png")
    CopyAllFiles(GetOutputDir()+"/models/maps/",       "models/maps/",           ".rgb")
    CopyAllFiles(GetOutputDir()+"/models/maps/",       "models/maps/",           ".rgba")


##########################################################################################
#
# Dependency-Based Distributed Build System.
#
##########################################################################################

DEPENDENCYQUEUE=[]

for target in TARGET_LIST:
    name = target.name
    inputs = target.inputs
    opts = target.opts
    deps = target.deps
    DEPENDENCYQUEUE.append([CompileAnything, [name, inputs, opts], [name], deps, []])

def BuildWorker(taskqueue, donequeue):
    while True:
        try:
            task = taskqueue.get(timeout=1)
        except:
            ProgressOutput(None, "Waiting for tasks...")
            task = taskqueue.get()
        sys.stdout.flush()
        if task == 0:
            return
        try:
            task[0](*task[1])
            donequeue.put(task)
        except:
            donequeue.put(0)

def AllSourcesReady(task, pending):
    sources = task[3]
    for x in sources:
        if x in pending:
            return False
    sources = task[1][1]
    for x in sources:
        if x in pending:
            return False
    altsources = task[4]
    for x in altsources:
        if x in pending:
            return False
    return True

def ParallelMake(tasklist):
    # Create the communication queues.
    donequeue = queue.Queue()
    taskqueue = queue.Queue()
    # Build up a table listing all the pending targets
    #task = [CompileAnything, [name, inputs, opts], [name], deps, []]
    # task[2] = [name]
    # task[3] = deps
    pending = {}
    for task in tasklist:
        for target in task[2]:
            pending[target] = 1
    # Create the workers
    for slave in range(THREADCOUNT):
        th = threading.Thread(target=BuildWorker, args=[taskqueue, donequeue])
        th.daemon = True
        th.start()
    # Feed tasks to the workers.
    tasksqueued = 0
    while True:
        if tasksqueued < THREADCOUNT:
            extras = []
            for task in tasklist:
                if tasksqueued < THREADCOUNT and AllSourcesReady(task, pending):
                    if NeedsBuild(task[2], task[3]):
                        tasksqueued += 1
                        taskqueue.put(task)
                    else:
                        for target in task[2]:
                            del pending[target]
                else:
                    extras.append(task)
            tasklist = extras
        sys.stdout.flush()
        if tasksqueued == 0:
            if len(tasklist) > 0:
                continue
            break
        donetask = donequeue.get()
        if donetask == 0:
            exit("Build process aborting.")
        sys.stdout.flush()
        tasksqueued -= 1
        JustBuilt(donetask[2], donetask[3])
        for target in donetask[2]:
            del pending[target]
    # Kill the workers.
    for slave in range(THREADCOUNT):
        taskqueue.put(0)
    # Make sure there aren't any unsatisfied tasks
    if len(tasklist) > 0:
        exit("Dependency problems: {0} tasks not finished. First task unsatisfied: {1}".format(len(tasklist), tasklist[0][2]))


def SequentialMake(tasklist):
    i = 0
    for task in tasklist:
        if NeedsBuild(task[2], task[3]):
            task[0](*task[1] + [(i * 100.0) / len(tasklist)])
            JustBuilt(task[2], task[3])
        i += 1


def RunDependencyQueue(tasklist):
    if THREADCOUNT != 0:
        ParallelMake(tasklist)
    else:
        SequentialMake(tasklist)


try:
    RunDependencyQueue(DEPENDENCYQUEUE)
finally:
    SaveDependencyCache()

# Run the test suite.
if RUNTESTS:
    if GetLinkAllStatic():
        runner = FindLocation("run_tests.exe", [])
        if runner.endswith(".js"):
            cmdstr = "node " + BracketNameWithQuotes(runner)
        else:
            cmdstr = BracketNameWithQuotes(runner)
    else:
        cmdstr = BracketNameWithQuotes(SDK["PYTHONEXEC"].replace('\\', '/'))
        cmdstr += " -B -m pytest"
    cmdstr += " tests"
    if GetVerbose():
        cmdstr += " --verbose"
    oscmd(cmdstr)

# Write out information about the Python versions in the built dir.
python_version_info = GetCurrentPythonVersionInfo()
UpdatePythonVersionInfoFile(python_version_info)

##########################################################################################
#
# The Installers
#
# Under windows, we can build an 'exe' package using NSIS
# Under linux, we can build a 'deb' package or an 'rpm' package.
# Under OSX, we can make a 'dmg' package.
#
##########################################################################################

if INSTALLER:
    ProgressOutput(100.0, "Building installer")
    from makepackage import MakeInstaller

    # When using the --installer flag, only install for the current version.
    python_versions = []
    if python_version_info:
        python_versions.append(python_version_info)

    MakeInstaller(version=VERSION, outputdir=GetOutputDir(),
                  optimize=GetOptimize(), compressor=COMPRESSOR,
                  debversion=DEBVERSION, rpmversion=RPMVERSION,
                  rpmrelease=RPMRELEASE, python_versions=python_versions)

if WHEEL:
    ProgressOutput(100.0, "Building wheel")
    from makewheel import makewheel
    makewheel(WHLVERSION, GetOutputDir())

##########################################################################################
#
# Print final status report.
#
##########################################################################################

WARNINGS.append("Elapsed Time: "+PrettyTime(time.time() - STARTTIME))

printStatus("Makepanda Final Status Report", WARNINGS)
print(GetColor("green") + "Build successfully finished, elapsed time: " + PrettyTime(time.time() - STARTTIME) + GetColor())
