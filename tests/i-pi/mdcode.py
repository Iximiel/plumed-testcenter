import os
import MDAnalysis as mda
import subprocess

class mdcode :
   def __init__( self ) :
       AngToNm = 0.1

   def setParams( self ) :
       params = {
         "temperature": 25,
         "tstep": 25,
         "relaxtime": 10,
         "pressure": 0.0001,
         "prelaxtime": 4.0
       }
       return params

   def runMD( self, mdparams ) : 
       inp = "<simulation verbosity='high'>\n"
       inp = inp + "  <output prefix='tut1'>\n"
       inp = inp + "    <properties filename='md' stride='1'> [step, time{picosecond}, conserved{kelvin}, temperature{kelvin}, potential{kelvin}, kinetic_cv{kelvin}] </properties>\n"
       inp = inp + "    <properties filename='force' stride='20'> [atom_f{piconewton}(atom=0;bead=0)] </properties>\n"
       inp = inp + "    <trajectory filename='pos' stride='1' format='xyz' cell_units='angstrom'> positions{angstrom} </trajectory>\n"
       inp = inp + "    <checkpoint filename='checkpoint' stride='1000' overwrite='True'/>\n"
       inp = inp + "  </output>\n"
       inp = inp + "  <total_steps> " + str(mdparams["nsteps"]) + " </total_steps>\n"
       inp = inp + "  <ffsocket mode='inet' name='driver'>\n"
       inp = inp + "    <address>localhost</address>\n"
       inp = inp + "    <port> 31415 </port>\n"
       inp = inp + "  </ffsocket>\n"
       inp = inp + "  <ffplumed name='plumed'>\n"
       inp = inp + "   <file mode='xyz'> structure.xyz </file>\n"
       inp = inp + "   <plumeddat> plumed.dat </plumeddat>\n"
       inp = inp + "  </ffplumed>\n"
       inp = inp + "  <system>\n"
       inp = inp + "    <initialize nbeads='1'>\n"
       inp = inp + "      <file mode='xyz'> structure.xyz </file>\n"
       inp = inp + "      <velocities mode='thermal' units='kelvin'> " + str(mdparams["temperature"]) + " </velocities>\n"
       inp = inp + "    </initialize>\n"
       inp = inp + "    <forces>\n"
       inp = inp + "      <force forcefield='driver'/>\n"
       inp = inp + "    </forces>\n"
       inp = inp + "    <ensemble>\n"
       inp = inp + "      <temperature units='kelvin'> " + str(mdparams["temperature"]) + " </temperature>\n"
       inp = inp + "      <bias>\n"
       inp = inp + "        <force forcefield='plumed' nbeads='1'></force>\n"
       inp = inp + "      </bias>\n"
       inp = inp + "    </ensemble>\n"
       inp = inp + "    <motion mode='dynamics'>\n"
       inp = inp + "      <dynamics mode='nvt'>\n"
       inp = inp + "        <thermostat mode='pile_g'>\n"
       inp = inp + "          <tau units='femtosecond'> " + str(mdparams["tstep"]) + " </tau>\n"
       inp = inp + "        </thermostat>\n"
       inp = inp + "        <timestep units='femtosecond'> " + str(mdparams["relaxtime"]) + " </timestep>\n"
       inp = inp + "      </dynamics>\n"
       inp = inp + "    </motion>\n"
       inp = inp + "  </system>\n"
       inp = inp + "  <smotion mode='metad'>\n"
       inp = inp + "      <metad> <metaff> [ plumed ] </metaff> <use_energy> True </use_energy> </metad>\n"
       inp = inp + "  </smotion>\n"
       inp = inp + "</simulation>\n"
       of = open("input.xml","w+")
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
       return 25*0.001  # Convert timestep in fs to ps

   def getNumberOfAtoms( self, rundir ) :
       natoms, traj, [], mda.coordinates.XYZ.XYZReader( rundir + "/tut1.pos_0.xyz")
       for frame in traj.trajectory : natoms.append( frame.positions.shape[0] )
       return natoms
       
   def getPositions( self, rundir ) :
       first, traj = True, mda.coordinates.XYZ.XYZReader( rundir + "/tut1.pos_0.xyz")
       for frame in traj.trajectory :
          if first : pos, first = frame.positions / 10, False
          else : pos = np.concatenate( (pos, frame.positions / 10), axis=0 )
       return pos

   def getCell( self, rundir ) :
       return 0

   def getMasses( self, rundir ) :
       raise Exception("No function to get masses yet")

   def getCharges( self, rundir ) :
       raise Exception("No function to get charges yet")
  
   def getEnergy( self, rundir ) :
       return 0