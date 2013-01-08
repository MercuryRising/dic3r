## Splic3r
(not related, in any way, to slic3r)

##### What does it do?
This script allows you to specify a Z height to change infill densities at. 
If you need to infill a small part of your object at 90% for strength, you need to infill the whole thing at 90%.
Not anymore!

#### How to use the script
Clone it or copy the single .py file.

Change the following parameters in the first part of the script:
* Path to slic3r
* Path to slic3r config file (if you don't know where it is, you probably need to export yours with file>export config
* First layer height
* Layer height
* Number of layers to swap
* Densities (.2 and .9 are defaults) **Currently only supports two infill densities**

Find where it is, run

  python splic3r.py PATH_TO_STL_FILE.stl

#### Explanation of how it works:

This script will splice an stl file at specific densities.
The densities are calculated with slic3r, meaning each density needs to be sliced separately (automated)
Currently only two densities are supported
The script finds the last Z height as specified by layerSwitch, and switches over to the other density at that point
It compensates for the difference in extrusion depending on the difference in fill density

#### Limitations:
Currently only works in the Z-dimension.
I will attempt to add the ability to grade X and Y as well, which would be really nice for something like the money clip bottle opener,
where only one side needs to have a high fill density (where the bottle is opened), while the other can be springier with less fill.
