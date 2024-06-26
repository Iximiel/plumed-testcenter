# Cloning the i-pi repository
git clone https://github.com/i-pi/i-pi.git
#git clone https://github.com/gtribello/i-pi.git

# Build the fortran drivers
cd i-pi/drivers/f90
make
cd ../../../

# Copy i-pi to $HOME/opt
cp -pr i-pi $HOME/opt

if [ -d "$HOME/opt/lib/plumed$suffix/python" ]; then
   echo FOUND PYTHON DIRECTORY FOR RUNNING PLUMED
else 
   echo DID NOT FIND PYTHON DIRECTORY FOR RUNNING PLUMED
fi

# Make a script to run i-pi
echo "#!/bin/bash" > $HOME/opt/bin/i-pi
echo "export PYTHONPATH=$HOME/opt/lib/plumed$suffix/python" >> $HOME/opt/bin/i-pi
echo "$HOME/opt/i-pi/bin/i-pi input.xml & sleep 5; $HOME/opt/i-pi/bin/i-pi-driver -m sg -h localhost -o 15 -p 31415" >> $HOME/opt/bin/i-pi
chmod u+x $HOME/opt/bin/i-pi
