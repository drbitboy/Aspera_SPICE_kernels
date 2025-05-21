import json
import math as m
import os
from pathlib import Path
import subprocess
import spiceypy as sp
import stat
import urllib.request

def hms2deg(hms_set):
    """Convert hh:mm:ss.ss format of RA to decimal degrees (open source code).

    Args:
        hms_set (set): RA set in sexigesimal coordinates from .JSON list of galaxies

    Returns:
        float: RA in decimal degrees
    """

    # Convert .JSON set into string and split into time units based on colon placement
    hms_str = next(iter(hms_set))
    hours, minutes, seconds = map(float, hms_str.split(':'))
    degrees = (hours + minutes / 60 + seconds / 3600) * 15

    return degrees

def dms2deg(dms_set):
    """Convert dd\u00b0mm'ss.ss" format of DEC to decimal degrees (open source code).

    Args:
        dms_set (set): DEC set in sexigesimal coordinates from .JSON list of galaxies

    Returns:
        float: DEC in decimal degrees
    """

    # Convert .JSON set into string
    dms_str = next(iter(dms_set))

    # Remove degree, minute, second symbols and split
    dms_str = dms_str.replace("\u00b0", " ").replace("'", " ").replace("\"", "")
    parts = dms_str.strip().split()

    # Extract sign
    sign = -1 if parts[0].startswith("-") else 1

    # Absolute value parsing
    degrees = abs(float(parts[0]))
    minutes = float(parts[1])
    seconds = float(parts[2])

    # Convert to decimal degrees
    decimal_deg = sign * (degrees + minutes / 60 + seconds / 3600)

    return decimal_deg

def main():
    """Creates and/or updates PCK files for each galaxy in a .JSON list.

    Args:
        None

    Returns:
        None
    """
    # Load galaxy data
    tpc_dir = os.path.dirname(__file__)
    json_filename = os.path.join(tpc_dir, 'galaxies.json')
    def_fn = os.path.join(tpc_dir, 'ngc.defs')

    # Load .JSON file
    with open(json_filename, "r") as f:
        galaxies = json.load(f)

    # Track the next available ID
    used_ids = {g["id"] for g in galaxies if g["id"]}
    next_id = 9999000


    open(def_fn, "w").close()

    # Update IDs and create .tpc files
    for galaxy in galaxies:

        # Assign new ID if missing
        if not galaxy["id"]:
            galaxy["id"] = str(next_id)
            next_id += 1
            while str(next_id) in used_ids: next_id += 1

        # Convert RA/DEC values from .JSON into decimal degree units
        ra_deg = hms2deg({galaxy['RA']})
        dec_deg = dms2deg({galaxy['DEC']})

        # Use decimal degree RA/DEC values to compute unit vector
        x,y,z = sp.radrec(1.0, ra_deg*sp.rpd(), dec_deg*sp.rpd())

        contents = f"""
\\begindata
NAIF_BODY_NAME        += ( '{galaxy['name']}' )
NAIF_BODY_CODE        += ( {galaxy['id']} )
NH_TARGET_BODIES      += ( {galaxy['id']} )
BODY{galaxy['id']}_POLE_RA    = ({ra_deg} 0. 0.)
BODY{galaxy['id']}_POLE_DEC   = ({dec_deg} 0. 0.)
BODY{galaxy['id']}_PM         = (0. 0. 0.)
BODY{galaxy['id']}_POLE_RADII = (0. 0. 0.)
\\begintext

PINPOINT parameters for galaxy {galaxy['name']}:
\\begindata
SITES                 += ( 'SITE{galaxy['id']}' )
SITE{galaxy['id']}_FRAME      = 'J2000'
SITE{galaxy['id']}_IDCODE     = {galaxy['id']}
SITE{galaxy['id']}_XYZ        = ({x} {y} {z})
SITE{galaxy['id']}_CENTER     = -1999
\\begintext
""".lstrip()

        # Write PCK, also append to PINPOINT definition files
        tpc_fn = os.path.join(tpc_dir, '_'.join(galaxy['name'].split())) + '.tpc'

        with open(tpc_fn, "w") as tpc_file: tpc_file.write(contents)
        with open(def_fn, "a") as def_file: def_file.write(contents)

    # Save updated .JSON
    with open(json_filename, "w") as f:
        json.dump(galaxies, f, indent=4)

    # Confirm code ran successfully to here
    print("Galaxy IDs updated and .tpc files created.")

    # Write SPK ...
    # 1) ... start by getting PINPOINT executable ...
    pinp_exe = 'pinpoint'
    have_pinpoint = subprocess.Popen(f"which {pinp_exe}".split(), stdout=subprocess.PIPE).stdout.read()
    if not have_pinpoint:
        pinp_exe = os.path.join(tpc_dir and tpc_dir or '.', 'pinpoint')
        pinpurl = 'https://naif.jpl.nasa.gov/pub/naif/utilities/PC_Linux_64bit/pinpoint'
        with urllib.request.urlopen(pinpurl) as response:
            with open(pinp_exe,'wb') as pinpfile:
                pinpfile.write(response.read())
        pinpprm = ( stat.S_IRWXU
                  | stat.S_IRGRP|stat.S_IXGRP
                  | stat.S_IROTH|stat.S_IXOTH
                  )
        os.chmod(pinp_exe,pinpprm)
        print(f"Retrieved PINPOINT executable from https://naif.jpl.nasa.gov/ as {pinp_exe}")

    # 2) ... then run pinpoint
    spk_fn = os.path.join(tpc_dir, '..', 'spk', 'galaxies.bsp')
    ret = subprocess.Popen(f"{pinp_exe} -def {def_fn} -spk {spk_fn}".split()
                          , stdout=subprocess.PIPE
                          ).stdout.read().decode('8859')
    if ret:
        print(f"Failed to create SPK {spk_fn}:")
        print(ret)
    else:
        print(f"Created SPK {spk_fn}")

    # Cleanup
    if not have_pinpoint:
        try:
            os.remove(pinp_exe)
            print(f"Removed {pinp_exe}")
        except:
            if 'DEBUG' in os.environ:
                import traceback
                traceback.print_exc()

    try:
        os.remove(def_fn)
        print(f"Removed {def_fn}")
    except:
        if 'DEBUG' in os.environ:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
