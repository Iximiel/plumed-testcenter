import os
import sys
import yaml
import getopt
import shutil
import subprocess
import numpy as np
import importlib
from pathlib import Path
import MDAnalysis as mda
from datetime import date
from contextlib import contextmanager
from PlumedToHTML import test_plumed, get_html

STANDARD_RUN_SETTINGS = [
    {"plumed": "plumed", "printJson": False},
    {"plumed": "plumed_master", "printJson": True, "version": "master"},
]


@contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)


def yamlToDict(filename, **yamlOpts):
    """Simply opens a yaml file an returns an object with the parsed data"""
    with open(filename, "r") as stram:
        ymldata = yaml.load(stram, **yamlOpts)
        # the return closes the file :)
        return ymldata


def processMarkdown(filename, prefix="", runSettings=STANDARD_RUN_SETTINGS):
    if not os.path.exists(filename):
        raise RuntimeError("Found no file called " + filename)
    with open(filename, "r") as f:
        inp = f.read()

    if prefix != "":
        directory = prefix + os.path.dirname(filename)
        Path(f"./{directory}").mkdir(parents=True, exist_ok=True)
        shutil.copy(filename, prefix + filename)
        filename = prefix + filename
    with open(filename, "w+") as ofile:
        inplumed = False
        plumed_inp = ""
        ninputs = 0
        for line in inp.splitlines():
            # Detect and copy plumed input files
            if "```plumed" in line:
                inplumed = True
                plumed_inp = ""
                ninputs += 1
            # Test plumed input files that have been found in tutorial
            elif inplumed and "```" in line:
                inplumed = False
                solutionfile = f"working{ninputs}.dat"
                with open(solutionfile, "w+") as sf:
                    sf.write(plumed_inp)
                # preparing for get_html
                successes = []
                plumed_exec = []
                versions = []
                usejson = False
                for plmd in runSettings:
                    successes.append(
                        test_plumed(
                            plmd["plumed"], solutionfile, printjson=plmd["printJson"]
                        )
                    )
                    plumed_exec.append(plmd["plumed"])
                    # if we asked to print json and we suceed we can use json in the get_html
                    if not usejson and not successes[-1] and plmd["printJson"]:
                        usejson = True

                    # Get the version
                    if "version" in plmd:
                        versions.append(plmd["version"])
                    else:
                        versions.append(
                            subprocess.check_output(
                                f"{plmd['plumed']} info --version", shell=True
                            )
                            .decode("utf-8")
                            .strip()
                        )

                # Use PlumedToHTML to create the input with all the bells and whistles
                html = get_html(
                    plumed_inp,
                    solutionfile,
                    solutionfile,
                    versions,
                    successes,
                    plumed_exec,
                    usejson=usejson,
                )
                # Print the html for the solution
                ofile.write("{% raw %}\n" + html + "\n {% endraw %} \n")
            elif inplumed:
                if "__FILL__" in line:
                    raise RuntimeError("Should not be incomplete files in this page")
                plumed_inp += line + "\n"
            # Just copy any line that isn't part of a plumed input
            elif not inplumed:
                ofile.write(line + "\n")


def buildTestPages(directory, prefix="", runSettings=STANDARD_RUN_SETTINGS):
    for page in os.listdir(directory):
        if ".md" in page:
            processMarkdown(directory + "/" + page, prefix, runSettings)


def runMDCalc(name: str, code: str, version: str, runner, params: dict):
    # Get the name of the executible
    basedir = f"tests/{code}"
    params["executible"] = (
        yamlToDict(f"{basedir}/info.yml", Loader=yaml.BaseLoader)["executible"]
        + f"_{version}"
    )

    # Now test that the executable exists if it doesn't then the test is broken
    if shutil.which(params["executible"]) == None:
        return True
    # Copy all the input needed for the MD calculation
    wdir = f"{basedir}/{name}_{version}"
    shutil.copytree(f"{basedir}/input", f"{wdir}")
    # Change to the directory to run the calculation
    with cd(f"{wdir}"):
        # Output the plumed file
        with open("plumed.dat", "w+") as of:
            of.write(params["plumed"])
        # Now run the MD calculation
        mdExitCode = runner.runMD(params)
    # Make a zip archive that contains the input and output
    shutil.make_archive(f"{wdir}", "zip", f"{wdir}")
    return mdExitCode


# the "*" forces the subsequent arguments to be named
def runTests(code: str, version: str, runner):
    # Read in the information on the tests that should be run for this code
    basedir = f"tests/{code}"
    ymldata = yamlToDict(f"{basedir}/info.yml", Loader=yaml.BaseLoader)
    info = ymldata["tests"]
    tolerance = float(ymldata["tolerance"])
    fname = "testout.md"
    usestable = version == "stable"

    if version == "master":
        fname = "testout_" + version + ".md"
    elif version != "stable":
        raise ValueError("version should be master or stable")

    of = open(f"{basedir}/{fname}", "w+")
    of.write(f"Testing {code}\n")
    of.write("------------------------\n \n")
    stable_version = (
        subprocess.check_output("plumed info --version", shell=True)
        .decode("utf-8")
        .strip()
    )
    if version == "stable":
        version = "v" + stable_version
    # it looks strange, but strings do not need the + to be concatenated
    of.write(
        f"The tests described in the following table were performed on "
        f"__{date.today().strftime('%B %d, %Y')}__ to test whether the "
        f"interface between {code} and "
        f"the {version} version of PLUMED is working correctly.\n\n"
    )
    if info["virial"] == "no":
        of.write(
            f"WARNING: {code} does not pass the virial to PLUMED and it is thus "
            "not possible to run NPT simulations with this code\n\n"
        )
    if "warning" in ymldata.keys():
        for warn in ymldata["warning"]:
            of.write(f"WARNING: {warn}\n\n")

    params = runner.setParams()
    basic_md_failed = True
    if (
        info["positions"] == "yes"
        or info["timestep"] == "yes"
        or info["mass"] == "yes"
        or info["charge"] == "yes"
    ):
        dumpMassesStr = ""
        if info["mass"] == "yes":
            dumpMassesStr = f"DUMPMASSCHARGE FILE=mq_plumed {'' if info['charge'] == 'yes' else 'ONLY_MASSES'}"
        timeStepStr = ""
        if info["timestep"] == "yes":
            timeStepStr = "t1: TIME\nPRINT ARG=t1 FILE=colvar"
        params[
            "plumed"
        ] = f"""DUMPATOMS ATOMS=@mdatoms FILE=plumed.xyz
c: CELL
PRINT ARG=c.* FILE=cell_data
{dumpMassesStr}
{timeStepStr}
"""
        params["nsteps"] = 10
        params["ensemble"] = "npt"
        basic_md_failed = runMDCalc("basic", code, version, runner, params)

    val1, val2 = 0.1, 0.1
    of.write("| Description of test | Status | \n")
    of.write("|:--------------------|:------:| \n")
    if info["positions"] == "yes":
        plumednatoms = []
        codenatoms = []
        codepos = np.ones(10)
        plumedpos = np.ones(10)
        codecell = np.ones(10)
        plumedcell = np.ones(10)

        if not basic_md_failed:
            # Get the trajectory that was output by PLUMED
            if os.path.exists(f"{basedir}/basic_{version}/plumed.xyz"):
                plumedtraj = mda.coordinates.XYZ.XYZReader(
                    f"{basedir}/basic_{version}/plumed.xyz"
                )
                # Get the number of atoms in each frame from plumed trajectory
                codenatoms = runner.getNumberOfAtoms(f"{basedir}/basic_{version}")
                plumednatoms = []
                for frame in plumedtraj.trajectory:
                    plumednatoms.append(frame.positions.shape[0])
                # Concatenate all the trajectory frames
                codepos = runner.getPositions(f"{basedir}/basic_{version}")
                first = True

                for frame in plumedtraj.trajectory:
                    if first:
                        first = False
                        plumedpos = frame.positions.copy()
                    else:
                        plumedpos = np.concatenate((plumedpos, frame.positions), axis=0)
                codecell = runner.getCell(f"{basedir}/basic_{version}")
                plumedcell = np.loadtxt(f"{basedir}/basic_{version}/cell_data")[:, 1:]

            else:
                basic_md_failed = True

        # Output results from tests on natoms
        writeReportPage(
            "natoms",
            code,
            version,
            basic_md_failed,
            ["basic"],
            np.array(codenatoms),
            np.array(plumednatoms),
            0.01 * np.ones(len(codenatoms)),
        )
        of.write(
            "| MD code number of atoms passed correctly | "
            + getBadge(
                check(
                    basic_md_failed,
                    np.array(codenatoms),
                    np.array(plumednatoms),
                    0.01 * np.ones(len(codenatoms)),
                    0,
                ),
                "natoms",
                code,
                version,
            )
            + "| \n"
        )
        # Output results from tests on positions
        writeReportPage(
            "positions",
            code,
            version,
            basic_md_failed,
            ["basic"],
            np.array(codepos),
            plumedpos,
            tolerance * np.ones(plumedpos.shape),
        )
        of.write(
            "| MD code positions passed correctly | "
            + getBadge(
                check(
                    basic_md_failed,
                    np.array(codepos),
                    plumedpos,
                    tolerance * np.ones(plumedpos.shape),
                    0,
                ),
                "positions",
                code,
                version,
            )
            + "| \n"
        )
        writeReportPage(
            "cell",
            code,
            version,
            basic_md_failed,
            ["basic"],
            np.array(codecell),
            plumedcell,
            tolerance * np.ones(plumedcell.shape),
        )
        of.write(
            "| MD code cell vectors passed correctly | "
            + getBadge(
                check(
                    basic_md_failed,
                    np.array(codecell),
                    plumedcell,
                    tolerance * np.ones(plumedcell.shape),
                    0,
                ),
                "cell",
                code,
                version,
            )
            + " | \n"
        )
    if info["timestep"] == "yes":
        md_tstep = 0.1
        plumed_tstep = 0.1
        if not basic_md_failed:
            plumedtimes = np.loadtxt(f"{basedir}/basic_{version}/colvar")[:, 1]
            md_tstep = runner.getTimestep()
            plumed_tstep = plumedtimes[1] - plumedtimes[0]

            for i in range(1, len(plumedtimes)):
                if plumedtimes[i] - plumedtimes[i - 1] != plumed_tstep:
                    ValueError("Timestep should be the same for all MD steps")
        writeReportPage(
            "timestep",
            code,
            version,
            basic_md_failed,
            ["basic"],
            md_tstep,
            plumed_tstep,
            0.0001,
        )
        of.write(
            "| MD timestep passed correctly | "
            + getBadge(
                check(basic_md_failed, md_tstep, plumed_tstep, 0.0001, 0),
                "timestep",
                code,
                version,
            )
            + " | \n"
        )
    if info["mass"] == "yes":
        md_masses = np.ones(10)
        pl_masses = np.ones(10)
        if not basic_md_failed:
            md_masses = runner.getMasses(f"{basedir}/basic_{version}")
            pl_masses = np.loadtxt(f"{basedir}/basic_{version}/mq_plumed")[:, 1]
        writeReportPage(
            "mass",
            code,
            version,
            basic_md_failed,
            ["basic"],
            np.array(md_masses),
            pl_masses,
            tolerance * np.ones(pl_masses.shape),
        )
        of.write(
            "| MD code masses passed correctly | "
            + getBadge(
                check(
                    basic_md_failed,
                    np.array(md_masses),
                    pl_masses,
                    tolerance * np.ones(pl_masses.shape),
                    0,
                ),
                "mass",
                code,
                version,
            )
            + " | \n"
        )
    if info["charge"] == "yes":
        md_charges, pl_charges = np.ones(10), np.ones(10)
        if not basic_md_failed:
            md_charges = runner.getCharges(f"{basedir}/basic_{version}")
            pl_charges = np.loadtxt(f"{basedir}/basic_{version}/mq_plumed")[:, 2]
        writeReportPage(
            "charge",
            code,
            version,
            basic_md_failed,
            ["basic"],
            np.array(md_charges),
            pl_charges,
            tolerance * np.ones(pl_charges.shape),
        )
        of.write(
            "| MD code charges passed correctly | "
            + getBadge(
                check(
                    basic_md_failed,
                    np.array(md_charges),
                    pl_charges,
                    tolerance * np.ones(pl_charges.shape),
                    0,
                ),
                "charge",
                code,
                version,
            )
            + " | \n"
        )
    if info["forces"] == "yes":
        # First run a calculation to find the reference distance between atom 1 and 2
        rparams = runner.setParams()
        rparams["nsteps"] = 2
        rparams["ensemble"] = "nvt"
        rparams["plumed"] = "dd: DISTANCE ATOMS=1,2 \nPRINT ARG=dd FILE=colvar"
        refrun = runMDCalc("refres", code, version, runner, rparams)
        mdrun = True
        plrun = True

        if not refrun:
            # Get the reference distance between the atoms
            refdist = np.loadtxt(f"{basedir}/refres_{version}/colvar")[0, 1]
            # Run the calculation with the restraint applied by the MD code
            rparams["nsteps"], rparams["ensemble"] = 20, "nvt"
            rparams["restraint"] = refdist
            rparams["plumed"] = "dd: DISTANCE ATOMS=1,2 \nPRINT ARG=dd FILE=colvar"
            mdrun = runMDCalc("forces1", code, version, runner, rparams)
            # Run the calculation with the restraint applied by PLUMED
            rparams["restraint"] = -10
            rparams["plumed"] = (
                "dd: DISTANCE ATOMS=1,2\n"
                f"RESTRAINT ARG=dd KAPPA=2000 AT={refdist}\n"
                "PRINT ARG=dd FILE=colvar\n"
            )
            plrun = runMDCalc("forces2", code, version, runner, rparams)
            # And create our reports from the two runs
            md_failed = mdrun or plrun
            val1 = np.ones(1)
            val2 = np.ones(1)
        if not md_failed:
            val1 = np.loadtxt(f"{basedir}/forces1_{version}/colvar")[:, 1]
            val2 = np.loadtxt(f"{basedir}/forces2_{version}/colvar")[:, 1]

        writeReportPage(
            "forces",
            code,
            version,
            md_failed,
            ["forces1", "forces2"],
            val1,
            val2,
            tolerance * np.ones(val1.shape),
        )
        of.write(
            "| PLUMED forces passed correctly | "
            + getBadge(
                check(
                    md_failed, val1, val2, tolerance * np.ones(val1.shape), tolerance
                ),
                "forces",
                code,
                version,
            )
            + " | \n"
        )
    if info["virial"] == "yes":
        params = runner.setParams()
        params["nsteps"], params["ensemble"] = 50, "npt"
        params["plumed"] = "vv: VOLUME \n PRINT ARG=vv FILE=volume"
        run1 = runMDCalc("virial1", code, version, runner, params)
        params["pressure"] = 1001 * params["pressure"]
        run3 = runMDCalc("virial3", code, version, runner, params)
        params["plumed"] = (
            "vv: VOLUME\n"
            "RESTRAINT AT=0.0 ARG=vv SLOPE=-60.221429\n"
            "PRINT ARG=vv FILE=volume\n"
        )
        run2 = runMDCalc("virial2", code, version, runner, params)
        md_failed = run1 or run2 or run3
        val1 = np.ones(1)
        val2 = np.ones(1)
        val3 = np.ones(1)

        if not md_failed:
            val1 = np.loadtxt(f"{basedir}/virial1_{version}/volume")[:, 1]
            val2 = np.loadtxt(f"{basedir}/virial2_{version}/volume")[:, 1]
            val3 = np.loadtxt(f"{basedir}/virial3_{version}/volume")[:, 1]
        writeReportPage(
            "virial",
            code,
            version,
            md_failed,
            ["virial1", "virial2", "virial3"],
            val1,
            val2,
            np.abs(val3 - val1),
        )
        of.write(
            "| PLUMED virial passed correctly | "
            + getBadge(
                check(md_failed, val1, val2, np.abs(val3 - val1), tolerance),
                "virial",
                code,
                version,
            )
            + " | \n"
        )
    if info["energy"] == "yes":
        params["nsteps"] = 150
        params["plumed"] = "e: ENERGY \nPRINT ARG=e FILE=energy"
        md_failed = runMDCalc("energy", code, version, runner, params)
        md_energy = np.ones(1)
        pl_energy = np.ones(1)

        if not md_failed and os.path.exists(f"{basedir}/energy_{version}/energy"):
            md_energy = runner.getEnergy(f"{basedir}/energy_{version}")
            pl_energy = np.loadtxt(f"{basedir}/energy_{version}/energy")[:, 1]

        else:
            md_failed = True
        writeReportPage(
            "energy",
            code,
            version,
            md_failed,
            ["energy"],
            md_energy,
            pl_energy,
            tolerance * np.ones(len(md_energy)),
        )
        of.write(
            "| MD code potential energy passed correctly | "
            + getBadge(
                check(
                    md_failed,
                    md_energy,
                    pl_energy,
                    tolerance * np.ones(len(md_energy)),
                    tolerance,
                ),
                "energy",
                code,
                version,
            )
            + " | \n"
        )
        sqrtalpha = 1.1
        alpha = sqrtalpha * sqrtalpha
        if info["engforces"] == "yes":
            params = runner.setParams()
            params["nsteps"], params["ensemble"] = 50, "nvt"
            params[
                "plumed"
            ] = """e: ENERGY
v: VOLUME
PRINT ARG=e,v FILE=energy
"""
            run1 = runMDCalc("engforce1", code, version, runner, params)
            params["temperature"] = params["temperature"] * alpha
            params["relaxtime"] = params["relaxtime"] / sqrtalpha
            params["tstep"] = params["tstep"] / sqrtalpha
            run3 = runMDCalc("engforce3", code, version, runner, params)
            params[
                "plumed"
            ] = f"""e: ENERGY
v: VOLUME
PRINT ARG=e,v FILE=energy
RESTRAINT AT=0.0 ARG=e SLOPE={alpha - 1}
"""

            run2 = runMDCalc("engforce2", code, version, runner, params)
            md_failed = run1 or run2 or run3
            val1 = np.ones(1)
            val2 = np.ones(1)
            val3 = np.ones(1)

            if not md_failed:
                val1 = np.loadtxt(f"{basedir}/engforce1_{version}/energy")[:, 1:]
                val2 = np.loadtxt(f"{basedir}/engforce2_{version}/energy")[:, 1:]
                val3 = np.loadtxt(f"{basedir}/engforce3_{version}/energy")[:, 1:]

            writeReportPage(
                "engforce",
                code,
                version,
                md_failed,
                ["engforce1", "engforce2", "engforce3"],
                val1,
                val2,
                np.abs(val1 - val3),
            )
            of.write(
                "| PLUMED forces on potential energy passed correctly | "
                + getBadge(
                    check(md_failed, val1, val2, np.abs(val1 - val3), tolerance),
                    "engforce",
                    code,
                    version,
                )
                + " | \n"
            )
        if info["engforces"] and info["virial"] == "yes":
            params = runner.setParams()
            params["nsteps"] = 150
            params["ensemble"] = "npt"
            params["plumed"] = "e: ENERGY\n v: VOLUME \n PRINT ARG=e,v FILE=energy"
            run1 = runMDCalc("engvir1", code, version, runner, params)
            params["temperature"] = params["temperature"] * alpha
            params["relaxtime"], params["prelaxtime"] = (
                params["relaxtime"] / sqrtalpha,
                params["prelaxtime"] / sqrtalpha,
            )
            params["tstep"] = params["tstep"] / sqrtalpha
            run3 = runMDCalc("engvir3", code, version, runner, params)
            params["plumed"] = (
                "e: ENERGY\n"
                "v: VOLUME\n"
                "PRINT ARG=e,v FILE=energy\n"
                f"RESTRAINT AT=0.0 ARG=e SLOPE={alpha - 1}"
            )
            run2 = runMDCalc("engvir2", code, version, runner, params)
            md_failed = run1 or run2 or run3
            val1 = np.ones(1)
            val2 = np.ones(1)
            val3 = np.ones(1)

            if not md_failed:
                val1 = np.loadtxt(f"{basedir}/engvir1_{version}/energy")[:, 1:]
                val2 = np.loadtxt(f"{basedir}/engvir2_{version}/energy")[:, 1:]
                val3 = np.loadtxt(f"{basedir}/engvir3_{version}/energy")[:, 1:]

            writeReportPage(
                "engvir",
                code,
                version,
                md_failed,
                ["engvir1", "engvir2", "engvir3"],
                val1,
                val2,
                np.abs(val1 - val3),
            )
            of.write(
                "| PLUMED contribution to virial due to force on potential energy passed correctly | "
                + getBadge(
                    check(md_failed, val1, val2, np.abs(val1 - val3), tolerance),
                    "engvir",
                    code,
                    version,
                )
                + " | \n"
            )
    of.close()
    # Read output file to get status
    with open(f"{basedir}/" + fname, "r") as ifn:
        inp = ifn.read()

    of = open(f"{basedir}/info.yml", "a")
    if "failed-red.svg" in inp:
        of.write(f"test_plumed{version}: broken \n")
    elif "%25-green.svg" in inp and ("%25-red.svg" in inp or "%25-yellow.svg" in inp):
        of.write(f"test_plumed{version}: partial\n")
    elif "%25-yellow.svg" in inp:
        of.write(f"test_plumed{version}: partial\n")
    elif "%25-green.svg" in inp:
        of.write(f"test_plumed{version}: working \n")
    elif "%25-red.svg" in inp:
        of.write(f"test_plumed{version}: broken \n")
    else:
        raise Exception(
            f"Found no test badges in output for tests on {code} with " + version
        )
    of.close()


def getBadge(sucess, filen, code, version: str):
    badge = f"[![tested on {version}](https://img.shields.io/badge/{version}-"
    if sucess < 0:
        badge = badge + "failed-red.svg"
    elif sucess < 5:
        badge = badge + f"fail {sucess}%25-green.svg"
    elif sucess < 20:
        badge = badge + f"fail {sucess}%25-yellow.svg"
    else:
        badge = badge + f"fail {sucess}%25-yellow.svg"
    return badge + f")]({filen}_{version}.html)"


def writeReportPage(filen, code, version, md_fail, zipfiles, ref, data, denom):
    # Read in the file
    f = open("pages/" + filen + ".md", "r")
    inp = f.read()
    f.close()
    # Now output the file
    of = open(f"tests/{code}/{filen}_{version}.md", "w+")
    for line in inp.splitlines():
        if "Trajectory" in line and "#" in line:
            if len(zipfiles) != 1:
                raise ValueError("wrong number of trajectories")
            of.write(line + "\n")
            of.write(
                "Input and output files for the test calculation are available in this [zip archive]("
                + zipfiles[0]
                + "_"
                + version
                + ".zip) \n\n"
            )
        elif "Trajectories" in line and "#" in line:
            if len(zipfiles) == 2:
                of.write(line + "\n")
                of.write(
                    "1. Input and output files for the calculation where the restraint is applied by the MD code available in this [zip archive]("
                    + zipfiles[0]
                    + "_"
                    + version
                    + ".zip) \n"
                )
                of.write(
                    "2. Input and output files for the calculation where the restraint is applied by PLUMED are available in this [zip archive]("
                    + zipfiles[1]
                    + "_"
                    + version
                    + ".zip) \n\n"
                )
            elif len(zipfiles) == 3:
                of.write(line + "\n")
                of.write(
                    "1. Input and output files for the unpeturbed calculation are available in this [zip archive]("
                    + zipfiles[0]
                    + "_"
                    + version
                    + ".zip) \n"
                )
                of.write(
                    "2. Input and output files for the peturbed calculation are available in this [zip archive]("
                    + zipfiles[2]
                    + "_"
                    + version
                    + ".zip) \n\n"
                )
                of.write(
                    "2. Input and output files for the peturbed calculation in which a PLUMED restraint is used to undo the effect of the changed MD parameters are available in this [zip archive]("
                    + zipfiles[1]
                    + "_"
                    + version
                    + ".zip) \n\n"
                )
            else:
                raise ValueError("wrong number of trajectories")
        elif "Results" in line and "#" in line and md_fail:
            of.write(line + "\n")
            of.write(
                "Calculations were not sucessful and no data was generated for comparison\n"
            )
        else:
            of.write(line + "\n")
    if not md_fail and hasattr(data, "__len__"):
        if len(zipfiles) == 1:
            of.write(
                "\n| MD code output | PLUMED output | Tolerance | % Difference | \n"
            )
        else:
            of.write(
                "\n| Original result | Result with PLUMED | Effect of peturbation | % Difference | \n"
            )
        of.write("|:-------------|:--------------|:--------------|:--------------| \n")
        nlines = min(20, len(ref))
        percent_diff = 100 * np.divide(
            np.abs(ref - data), denom, out=np.zeros_like(denom), where=denom != 0
        )
        for i in range(nlines):
            if hasattr(ref[i], "__len__"):
                ref_strings = ["%.4f" % x for x in ref[i]]
                data_strings = ["%.4f" % x for x in data[i]]
                denom_strings = ["%.4f" % x for x in denom[i]]
                pp_strings = ["%.4f" % x for x in percent_diff[i]]
                of.write(
                    "|"
                    + " ".join(ref_strings)
                    + " | "
                    + " ".join(data_strings)
                    + " | "
                    + " ".join(denom_strings)
                    + " | "
                    + " ".join(pp_strings)
                    + "| \n"
                )
            else:
                of.write(
                    "|"
                    + str(ref[i])
                    + " | "
                    + str(data[i])
                    + " | "
                    + str(denom[i])
                    + " | "
                    + str(percent_diff[i])
                    + "| \n"
                )
    elif not md_fail:
        if len(zipfiles) == 1:
            of.write(
                "\n| MD code output | PLUMED output | Tolerance | % Difference | \n"
            )
        else:
            of.write(
                "| Original result | Result with PLUMED | Effect of peturbation | % Difference | \n"
            )
        of.write("|:-------------|:--------------|:--------------|:--------------| \n")
        of.write(
            "| "
            + str(ref)
            + " | "
            + str(data)
            + " | "
            + str(denom)
            + " | "
            + str(100 * np.abs(ref - data) / denom)
            + " | \n"
        )
    of.close()


def check(md_failed, val1, val2, val3, tolerance):
    if md_failed:
        return -1
    if hasattr(val2, "__len__") and len(val1) != len(val2):
        return -1
    if hasattr(val2, "__len__") and len(val3) != len(val2):
        return -1
    percent_diff = 100 * np.divide(
        np.abs(val1 - val2), val3, out=np.zeros_like(val3), where=val3 > tolerance
    )
    return int(np.round(np.average(percent_diff)))


if __name__ == "__main__":
    code, version, argv = "", "", sys.argv[1:]
    try:
        opts, args = getopt.getopt(argv, "hc:v:", ["code="])
    except:
        print("runtests.py -c <code> -v <version>")

    for opt, arg in opts:
        if opt in ["-h"]:
            print("runtests.py -c <code>")
            sys.exit()
        elif opt in ["-c", "--code"]:
            code = arg
        elif opt in ["-v", "--version"]:
            version = arg

    # Build all the pages that describe the tests for this code
    buildTestPages("tests/" + code)
    # Copy the engforce file
    shutil.copy("pages/engforce.md", "pages/engvir.md")
    # Build the default test pages
    buildTestPages("pages")
    # Create an __init__.py module for the desired code
    ipf = open(f"tests/{code}/__init__.py", "w+")
    ipf.write("from .mdcode import mdcode\n")
    ipf.close()
    # Now import the module
    d = importlib.import_module("tests." + code, "mdcode")
    # And create the class that interfaces with the MD code output
    runner = d.mdcode()
    # Now run the tests
    runTests(code, version, runner)
