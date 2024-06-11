import os
import time
import numpy as np
import MDAnalysis as mda
import subprocess

class mdcode :
   def __init__( self ) :
       AngToNm = 0.1

   def setParams( self ) :
       params = {
         "temperature": 300,
         "tstep": 0.002,
         "relaxtime": 2.0,
         "pressure": 1,
         "prelaxtime": 2.0
       }
       return params

   def runMD( self, mdparams ) : 
       npt_stuff = ""
       if mdparams["ensemble"]=="npt" : 
          npt_stuff = f"""
pcoupl                   = Parrinello-Rahman
tau_p                    = {mdparams["prelaxtime"]}
compressibility          = 4.46e-5
ref_p                    = {mdparams["pressure"]}
"""

       inp = f"""
integrator               = md        
dt                       = {mdparams["tstep"]}     
nsteps                   = {mdparams["nsteps"]} 

nstenergy                = 1
nstlog                   = 1
nstxout-compressed       = 1

continuation             = yes
constraint-algorithm     = lincs
constraints              = h-bonds

cutoff-scheme            = Verlet

coulombtype              = PME
rcoulomb                 = 1.0

vdwtype                  = Cut-off
rvdw                     = 1.0
DispCorr                 = EnerPres

tcoupl                   = v-rescale
tc-grps                  = System
tau-t                    = {mdparams["relaxtime"]}
ref-t                    = {mdparams["temperature"]}

{npt_stuff}
"""
       of = open("md.mdp", "w+")
       of.write(inp)
       of.close()
       # Work out the script that will run ipi for us
       executible = mdparams["executible"] 
       # Now run the calculation using subprocess
       with open("stdout","w") as stdout:
        with open("stderr","w") as stderr:
           out = subprocess.run([executible], text=True, input=inp, stdout=stdout, stderr=stderr )
       return out.returncode

   def getTimestep( self ) :
       return 0.002

   def getNumberOfAtoms( self, rundir ) :
       natoms, fnum = [], 0 
       with mda.coordinates.XTC.XTCFile( rundir + "/traj_comp.xtc") as xtc : 
         for frame in xtc :
             if fnum>0 : natoms.append( xtc.n_atoms )
             fnum = fnum + 1
       return natoms
       
   def getPositions( self, rundir ) :
       fnum = 0
       with mda.coordinates.XTC.XTCFile( rundir + "/traj_comp.xtc") as xtc :
         for frame in xtc :
             if fnum==1 : pos = frame.x
             elif fnum>0 : pos = np.concatenate( (pos, frame.x), axis=0 )
             fnum = fnum + 1
       return pos

   def getCell( self, rundir ) :
       fnum = 0 
       with mda.coordinates.XTC.XTCFile( rundir + "/traj_comp.xtc") as xtc :
         for frame in xtc :
             dim = xtc.dimensions
             if fnum==1 : cell = np.array( [dim[0],0,0,0,dim[1],0,0,0,dim[2]] )
             elif fnum>0 : 
                box = np.array( [dim[0],0,0,0,dim[1],0,0,0,dim[2]] )
                cell = np.concatenage( (cell, box) )
             fnum = fnum + 1
       return cell

   def getMasses( self, rundir ) :
       return 0

   def getCharges( self, rundir ) :
       return 0
  
   def getEnergy( self, rundir ) :
       return 0