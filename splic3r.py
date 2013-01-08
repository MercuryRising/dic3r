import re
import subprocess
import sys
import time

################## USER PARAMETERS #####################

# where is your slic3r config file? If you don't know, export it now under the file menu of slic3r
configFile = "/home/andrew/cnc/files/config.ini"

# path to slic3r
slicerPath = "/home/andrew/cnc/slicer/bin/slic3r"

# what densities would you like to grade at?
# first one is the first grade to be printed, second will kick in at the set z
densities = ['.2', '.9']

# what is the Z-height you would like to splice the stls at?
# you have to pick an actual Z height (no approximations)
# you can pick one from calculating your first layer height + layer heights
layerHeight = .25
firstLayerHeight = .35
layers = 15
layerSwitchHeight = layers*layerHeight

# Or manually set it
layerSwitchHeight = 5.100

# if using reprap, 'E', if using linuxCNC, 'A'
extruderModifier = "A"

# preferred extension for spliced file
extension = '.ngc'

#########################################################

'''
Explanation of how it works:

This script will splice an stl file at specific densities.
The densities are calculated with slic3r, meaning each density needs to be sliced separately (automated)
Currently only two densities are supported
The script finds the last Z height as specified by layerSwitch, and switches over to the other density at that point
It compensates for the difference in extrusion depending on the difference in fill density

Limitations:
Currently only works in the Z-dimension.
I will attempt to add the ability to grade X and Y as well, which would be really nice for something like the money clip bottle opener,
where only one side needs to have a high fill density (where the bottle is opened), while the other can be springier with less fill.

No logic for finding a 'good' Z. 
You need to tell it exactly what height to separate at. If you get it wrong, it will slice two (or more) stls, and then crash.
Feature: Interactive mode for finding new Z heights.

'''

def grab_file(filePath):
	with open(filePath, 'rb') as f:
		return f.read()

def command_slic3r(filePath):
	'''
	This function makes slic3r slice at the specified infill densities
	Returns two strings containing the gcode for the infills selected
	'''
	sliceStartTime = time.time()
	files = []
	for density in densities:
		print '\nSlicing %s at density %s' %(filePath, density)
		output = subprocess.check_output([slicerPath, '--load', configFile, '--fill-density', density, filePath])
		fileName = re.findall("Exporting G-code to (.*)", output)[0]
		fileExtension = fileName.split('.')[-1]
		data = grab_file(fileName)
		newFilePath = filePath[:-4]+'_graded_'+density[1:]+'.'+fileExtension
		with open(newFilePath, 'wb') as f:
			f.write(data)

		print 'Saved %s successfully' %newFilePath
		files.append(data)

	return files, time.time()-sliceStartTime

def splice_gcode(fill20, fill90, sliceTime=None):
	layerSwitch = "Z"+str(layerSwitchHeight)
	fill20Lines = fill20.split("\n")
	fill90Lines = fill90.split("\n")

	line90 = 0
	while not line90:
		line90 = re.findall(r"(.*?%s.*)" %layerSwitch, fill90)
		if not line90:
			newSwitch = raw_input("\nYour Z didn't work! Enter a new Z height! > ")
			layerSwitch = "Z"+newSwitch
	line90 = line90[-1]

	if extruderModifier not in line90:
		index = fill90Lines.index(line90)
		a90 = re.findall(r"(%s[-.0-9].*)" %extruderModifier, fill90Lines[index+1])[0]
	else:
		a90 = re.findall(r"(%s[-.0-9].*)" %extruderModifier, line90)[0]

	line20 = re.findall(r"(.*?%s.*)" %layerSwitch, fill20)[-1]

	if extruderModifier not in line20:
		index = fill20Lines.index(line20)
		a20 = re.findall(r"(%s[-.0-9].*)" %extruderModifier, fill20Lines[index+1])[0]
	else:
		a20 = re.findall(r"(%s[-.0-9].*)" %extruderModifier, line20)[0]

	print 'A20 step: ', a20[1:], ' A90step: ', a90[1:]
	diff = float(a90[1:]) - float(a20[1:]) # offset we need for A steps to add to second file
	print '\nOffset for densities: ', diff

	firstPart = fill90.split(line90)[0]+line90.strip()+' (end first part)\n'

	secondPart = fill20Lines[fill20Lines.index(line20)+1:]

	modifiedSecondPart = []
	for index, line in enumerate(secondPart):
		if extruderModifier in line:
			#print line
			aPosition = re.findall(r"(%s.*)" %extruderModifier, line)[0]
			newA = float(aPosition[1:])+diff
			line = re.sub(aPosition, extruderModifier+str(newA)+" (%s)"%aPosition, line)

		modifiedSecondPart.append(line)

	data = firstPart + '\n'.join(modifiedSecondPart)

	nfp = stlFilePath[:-4]+"_graded"+extension
	with open(nfp, "wb") as f:
		f.write(data)

	print "\nWrote %s successfully" %nfp
	print "You may want to open the file and search for '(end first part)' to ensure everything is sane."
	totalTime = time.time()-startTime
	if sliceTime is not None:
		print 'Total time: %.1fs Slice time: %.1fs Grade time: %.1fs' %(totalTime, sliceTime, totalTime-sliceTime)
	else:
		print 'Total time: %.1fs' %(totalTime)

def gcode_file_splicer(filePath1, filePath2):
	fill20 = grab_file(filePath1)
	fill90 = grab_file(filePath2)
	splice_gcode(fill20, fill90)

def slice_file(stlFilePath):
	densityData, sliceTime = command_slic3r(stlFilePath)
	fill20, fill90 = densityData
	splice_gcode(fill20, fill90, sliceTime)

if __name__ == '__main__':
	startTime = time.time()

	if not (configFile and slicerPath):
		print "Please open the file and enter the path for slic3r and the slic3r config file"
		sys.exit()
	if len(sys.argv) > 1:
		if len(sys.argv) > 2:
			firstFile = sys.argv[1]
			secondFile = sys.argv[2]
			print 'Using %s and %s as input files...' %(firstFile, secondFile)
			stlFilePath = firstFile
			gcode_file_splicer(firstFile, secondFile)
		else:
			stlFilePath = sys.argv[1]
			print 'Using %s as input file...' %stlFilePath
			slice_file(stlFilePath)
	else:
		print "Please enter an stl file or gcode(s) to grade"
