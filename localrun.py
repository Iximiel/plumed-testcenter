import shutil
import importlib
from runtests import buildTestPages, runTests
import click


@click.command()
@click.argument("codedir", type=click.Path(exists=True))
@click.option(
    "--prefix", default="local_", help="The local run prefix for the data directories."
)
@click.option(
    "--plumed",
    "-p",
    default=["plumed"],
    help="The plumed executable(s) to run.",
    multiple=True,
)
@click.option("--printJson", "printJson", is_flag=True, default=False)
def localRun(codedir: str, prefix: str, plumed: "list[str]", printJson: bool):
    """Simple local run CLI

    Specify the directory in wich the settings for the test are stored as a first argument
    For example: localrun.py tests/quantum_espresso

    The plumed executable defaults to "plumed"

    The default prefix is "local_" (files are stored in "local_pages", "local_tests",...)

    Before running this you may need to manually remove some directories in "*prefix*tests".
    An error message will be printed if the directory is not empty.
    """
    code: str = codedir.split("/")[-1]
    # to run PATH must contain the dir to plumed and the one to the executable of your code
    # code = "quantum_espresso"
    plumedToRun = [{"plumed": p, "printJson": printJson} for p in plumed]

    print("Code: " + code)
    print("Preparing pages")
    # Engforce and engvir share the same procedure
    shutil.copy("pages/engforce.md", "pages/engvir.md")
    buildTestPages(codedir, prefix, plumedToRun)
    # this usues > 50% of the time
    buildTestPages("pages", prefix, plumedToRun)
    # Create an __init__.py module for the desired code
    with open(codedir + "/__init__.py", "w") as ipf:
        ipf.write("from .mdcode import mdcode\n")
    myMDcode = importlib.import_module(codedir.replace("/", "."), "mdcode")
    # And create the class that interfaces with the MD code output
    runner = myMDcode.mdcode()
    # Now run the tests
    print("Running the tests on stable")
    # execNameChanged=False because in my case I have compiled qe without changing its suffix
    runTests(
        code,
        "stable",
        runner,
        prefix=prefix,
        settingsFor_runMDCalc=dict(execNameChanged=False, makeArchive=False),
    )


if __name__ == "__main__":
    try:
        localRun()
    except FileExistsError as e:
        print(e)
        print(
            "Please remove (and backup, if you need it) this directory before running again"
        )
        exit(1)
    except Exception as e:
        print(e)
        exit(1)
