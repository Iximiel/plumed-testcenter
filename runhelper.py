from typing import TextIO
import numpy as np


def getBadge(sucess, filen, version: str, local=False):
    successStr = "failed"
    color = "red"
    if sucess < 0:
        successStr = "failed"
        color = "red"
    else:
        if sucess < 5:
            color = "green"
        elif sucess < 20:
            color = "yellow"
        else:
            ########################################################################
            # should this be "red"?
            ########################################################################
            color = "yellow"
        if local:
            successStr = f"fail {sucess}%"
        else:
            successStr = f"fail {sucess}%25"

    if local:
        return (
            f'[<span style="color:{color}">{successStr}</span>]({filen}_{version}.md)'
        )
    else:
        return (
            f"[![tested on {version}]"
            f"(https://img.shields.io/badge/{version}-{successStr}-{color}.svg)"
            f"]({filen}_{version}.html)"
        )


def writeReportPage(
    filen, code, version, md_fail, zipfiles, ref, data, denom, *, prefix=""
):
    # Read in the file
    with open(f"{prefix}pages/{filen}.md", "r") as f:
        inp = f.read()

    # Now output the file
    with open(f"{prefix}tests/{code}/{filen}_{version}.md", "w+") as of:
        for line in inp.splitlines():
            if "Trajectory" in line and "#" in line:
                if len(zipfiles) != 1:
                    raise ValueError("wrong number of trajectories")
                of.write(
                    f"{line}\n"
                    "Input and output files for the test calculation are available in "
                    f"this [zip archive]({zipfiles[0]}_{version}.zip)\n\n"
                )
            elif "Trajectories" in line and "#" in line:
                if len(zipfiles) == 2:
                    of.write(
                        f"{line}\n"
                        "1. Input and output files for the calculation where the restraint "
                        "is applied by the MD code available in "
                        f"this [zip archive]({zipfiles[0]}_{version}.zip)\n"
                        "2. Input and output files for the calculation where the restraint "
                        "is applied by PLUMED are available in t"
                        f"his [zip archive]({zipfiles[1]}_{version}.zip)\n\n"
                    )
                elif len(zipfiles) == 3:
                    of.write(
                        f"{line}\n"
                        "1. Input and output files for the unpeturbed calculation "
                        "are available in "
                        f"this [zip archive]({zipfiles[0]}_{version}.zip)\n"
                        "2. Input and output files for the peturbed calculation "
                        "are available in "
                        f"this [zip archive]({zipfiles[2]}_{version}.zip)\n\n"
                        "3. Input and output files for the peturbed calculation in "
                        "which a PLUMED restraint is used to undo the effect of the "
                        "changed MD parameters are available in "
                        f"this [zip archive]({zipfiles[1]}_{version}.zip)\n\n"
                    )
                else:
                    raise ValueError("wrong number of trajectories")
            elif "Results" in line and "#" in line and md_fail:
                of.write(
                    f"{line}\n"
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
            of.write(
                "|:-------------|:--------------|:--------------|:--------------| \n"
            )
            nlines = min(20, len(ref))
            percent_diff = 100 * np.divide(
                np.abs(ref - data), denom, out=np.zeros_like(denom), where=denom != 0
            )
            for i in range(nlines):
                if hasattr(ref[i], "__len__"):
                    ref_strings = " ".join([f"{x:.4f}" for x in ref[i]])
                    data_strings = " ".join([f"{x:.4f}" for x in data[i]])
                    denom_strings = " ".join([f"{x:.4f}" for x in denom[i]])
                    pp_strings = " ".join([f"{x:.4f}" for x in percent_diff[i]])
                    of.write(
                        f"| {ref_strings} | {data_strings} | {denom_strings} | {pp_strings} | \n"
                    )
                else:
                    # TODO:ask if also this needs formatting (just append ":.4f")
                    of.write(
                        f"| {ref[i]} | {data[i]} | {denom[i]} | {percent_diff[i]} |\n"
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
            of.write(
                "|:-------------|:--------------|:--------------|:--------------| \n"
                f"| {ref} | {data} | {denom} | {100 * np.abs(ref - data) / denom} | \n"
            )


def check(md_failed: "int|bool", val1, val2, val3, tolerance: float = 0.0) -> int:
    # this may be part of writeReportForSimulations
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


class writeReportForSimulations:
    """helper class to write the report tof the simulations"""

    def __init__(
        self,
        testout: TextIO,
        code: str,
        version: str,
        md_failed,
        simulations,
        *,
        prefix="",
    ) -> None:
        # note that the prefix cannot accidentally be set, because it must explicitly named to be set
        self.testout = testout
        self.code = code
        self.version = version
        self.md_failed = md_failed
        self.simulations = simulations
        self.prefix = prefix

    def writeReportAndTable(
        self,
        kind: str,
        docstring: str,
        val1,
        val2,
        val3,
        *,
        tolerance: float = 0.0,
    ):
        writeReportPage(
            kind,
            self.code,
            self.version,
            self.md_failed,
            self.simulations,
            val1,
            val2,
            val3,
            prefix=self.prefix,
        )
        self.testout.write(
            f"| {docstring} | "
            + getBadge(
                check(self.md_failed, val1, val2, val3, tolerance=tolerance),
                kind,
                self.version,
                local=self.prefix != "",
            )
            + " |\n"
        )
