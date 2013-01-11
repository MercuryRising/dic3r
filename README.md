## Dic3r

##### What does it do?
Dic3r is designed to be used in conjunction with slic3r. It automates slic3r's command line interface to allow you
to quickly and easily vary settings.

This is very useful in machine calibration, when you want to 'dial in' on a certain parameter.

#### How to use the script
Clone it or copy the single dic3r.py file.

Change the following parameters in the first part of the script:
* Path to slic3r
* Path to slic3r config file (if you don't know where it is, you probably need to export yours with file>export config
* First layer height
* Layer height
* Number of layers to swap

Find where it is, run

    python splic3r.py STL_FILE.stl 

The script will then ask you some questions about what you would like to calibrate.

There are currently only two supported: fill-density and extrusion modifier. More coming soon!
