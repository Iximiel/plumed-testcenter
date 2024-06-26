import numpy as np
import MDAnalysis as mda
import subprocess

class mdcode :
   def setParams( self ) :
       params = {
         "temperature": 1.0,
         "tstep": 0.005,
         "relaxtime": 1.0,
         "pressure": 1.0,
         "prelaxtime": 4
       }
       return params
 
   def runMD( self, mdparams ) :
       # Prepare a string that contains the input for simplemd
       inp = "inputfile input.xyz\n"
       inp = inp + "outputfile output.xyz\n"
       inp = inp + "temperature " + str(mdparams["temperature"]) + "\n"
       inp = inp + "tstep " + str(mdparams["tstep"]) + "\n"
       inp = inp + "friction " + str(1.0/mdparams["relaxtime"]) + "\n"
       inp = inp + "forcecutoff 2.5\n"
       inp = inp + "listcutoff  3.0\n"
       inp = inp + "nstep " + str(mdparams["nsteps"]) + "\n"
       inp = inp + "nconfig 1 trajectory.xyz\n"
       inp = inp + "nstat   1 energies.dat\n"
       of=open("in","w+")
       of.write(inp)
       of.close()
       # Code to deal with restraint 
       if "restraint" in mdparams and mdparams["restraint"]>0 : 
          f = open("plumed.dat","w+")
          f.write("dd: DISTANCE ATOMS=1,2 \nRESTRAINT ARG=dd KAPPA=2000 AT=" + str(mdparams["restraint"]) + "\nPRINT ARG=dd FILE=colvar FMT=%8.4f\n")
          f.close()
       # Work out the name of the plumed executable 
       executible = mdparams["executible"] 
       cmd = [executible, "simplemd"]
       # Now run the calculation using subprocess
       with open("stdout","w") as stdout:
        with open("stderr","w") as stderr:
           plumed_out = subprocess.run(cmd, text=True, input=inp, stdout=stdout, stderr=stderr )
       return plumed_out.returncode

   def getTimestep( self ) :
       return 0.005

   def getNumberOfAtoms( self, rundir ) :
       natoms, traj = [], mda.coordinates.XYZ.XYZReader( rundir + "/trajectory.xyz") 
       for frame in traj.trajectory : natoms.append( frame.positions.shape[0] )
       return natoms 

   def getPositions( self, rundir ) :
       first, traj = True, mda.coordinates.XYZ.XYZReader( rundir + "/trajectory.xyz") 
       for frame in traj.trajectory :
          if first : pos, first = frame.positions.copy(), False
          else : pos = np.concatenate( (pos, frame.positions), axis=0 )
       return pos

   def getCell( self, rundir ) :
       nframes = len( self.getNumberOfAtoms( rundir ) )
       cell = np.zeros([nframes,9])
       f = open( rundir + "/trajectory.xyz", "r" )
       lines = f.read().splitlines()
       f.close()
       natoms = int( lines[0] )
       for i in range(nframes) : 
           cellstr = lines[i*(2+natoms)+1].split() 
           cell[i,0], cell[i,4], cell[i,8] = float(cellstr[0]), float(cellstr[1]), float(cellstr[2])
       return cell

   def getMasses( self, rundir ) :
       natoms = self.getNumberOfAtoms( rundir )
       return np.ones( natoms[0] )

   def getCharges( self, rundir ) :
       natoms = self.getNumberOfAtoms( rundir )
       return np.zeros( natoms[0] )

   def getEnergy( self, rundir ) :
       return np.loadtxt( rundir + "/energies.dat" )[:,3]
