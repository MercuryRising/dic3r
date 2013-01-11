#! /usr/bin/python

import re
import subprocess
import sys
import time
import numpy as np
import os
import random

################## USER PARAMETERS #####################
# where is your slic3r config file? If you don't know, export it now under the file menu of slic3r
configFile = ""

# path to slic3r
slicerPath = ""

# what densities would you like to grade at?
# first one is the first grade to be printed, second will kick in at the set z
densities = ['.2', '.2']

# Fill patterns - must be 1:1 with density, or a blank array []
fillPatterns = ["concentric", "honeycomb"]

# what is the Z-height you would like to splice the stls at?
# you have to pick an actual Z height (no approximations)
# you can pick one from calculating your first layer height + layer heights
layerHeight = .30
firstLayerHeight = .30
layers = 12
layerSwitchHeight = layers*layerHeight

# if using reprap, 'E', if using linuxCNC, 'A'
extruderModifier = "A"

# preferred extension for spliced file
extension = '.ngc'
#########################################################

def grab_file(filePath):
	with open(filePath, 'rb') as f:
		return f.read()

def command_slic3r(filePath, options=None):
	'''
	This function makes slic3r slice at the specified infill densities
	Returns two strings containing the gcode for the infills selected
	'''

	# We loop through the different infill densities, grabbing the fill patterns when necessary
	# and command
	files = []
	# Index allows us to grab fill patterns or other properties if they're there, density is the infill density we'll use
		
	print '\nSlicing %s with options: %s' %(filePath, options)

	command = [slicerPath, '--load', configFile, '--gcode-comments', '--layer-height', str(layerHeight), '--first-layer-height', str(firstLayerHeight)]
	if options:
		command.extend(options)
	command.append(filePath)

	# Call slic3r with command line options
	output = subprocess.check_output(command)

	# Grab the output filename from slic3r
	fileName = re.findall("Exporting G-code to (.*)", output)[0]

	# Grab the extension from the filename
	fileExtension = fileName.split('.')[-1]

	# Open up the file that slic3r created
	data = grab_file(fileName)

	# Create a new file path, as when we call slic3r again our original file will be gone
	newFilePath = filePath[:-4]+'_graded'+time.strftime("_%H_%M_%S_")+str(random.randint(0,100))+'.'+fileExtension

	# Make the new file
	with open(newFilePath, 'wb') as f:
		f.write(data)

	# Save it!
	#print 'Saved %s successfully' %newFilePath

	return data

def splice_gcode(fillA, fillB, axis, position=0):
	'''
	This function splices two files across a boundary.
	The switching position is determined by the position and the axis
	defaults to 0.
	'''

	# add axis logic - Z might be the last one seen at a specific height that is not a retraction
	# X/Y axes are determined by the line to the point
	# We have the starting point, and the ending point, 
	# we need to shorten the line to keep the angles identical

	# For Z, we need a specific height

	# For X/Y, we don't do anything if we end up at a specific height,
	# but if the coordinate extends past (on infill, skirts, whatever)
	# we need to shorten the line

	# Convert the decimal height into the correct axis coordinate
	layerSwitch = axis+str(layerSwitchHeight)

	# Convert the data to lines
	fillALines = fillA.split("\n")
	fillBLines = fillB.split("\n")

	# lineB and lineA are the lines where the transition will occur
	# We initialize lineB to 0 to go into 'interactive' mode if the Z-height is not in the file
	lineB = 0
	while not lineB:
		lineB = re.findall(r"(.*?%s.*)" %layerSwitch, fillB)
		if not lineB:
			newSwitch = raw_input("\nYour Z didn't work! Enter a new Z height! > ")
			layerSwitch = "Z"+newSwitch

	# Grab the last occurrence of the Z height to transition at
	lineB = lineB[-1]

	# if the line does not have an A/E position in it, we need to find out what the last extruder position was
	# so we can transition nicely
	index = fillBLines.index(lineB)
	while extruderModifier not in lineB:
		index += 1 
		lineB = fillBLines[index]
		aPositionB = re.findall(r"(%s[-.0-9]*)" %extruderModifier, lineB)[0]

	lineA = re.findall(r"(.*?%s.*)" %layerSwitch,fillA)[-1]

	if extruderModifier not in lineA:
		index =fillALines.index(lineA)
		aPositionA = re.findall(r"(%s[-.0-9]*)" %extruderModifier,fillALines[index+1])[0]
	else:
		aPositionA = re.findall(r"(%s[-.0-9]*)" %extruderModifier, lineA)[0]

	diff = float(aPositionB[1:]) - float(aPositionA[1:]) # offset we need for A steps to add to second file
	print 'Extrusion Offset: ', diff

	firstPart = fillB.split(lineB)[0]+lineB.strip()+' (end first part)\n'
	secondPart =fillALines[fillALines.index(lineA)+1:]

	modifiedSecondPart = []
	for index, line in enumerate(secondPart):
		if extruderModifier in line:
			if ";" in line and line.index(";") < line.index("A"): 
				pass
			else:
				aPosition = re.findall(r"(?<!;)(%s[-.0-9]*)" %extruderModifier, line)[0]
				newA = float(aPosition[1:])+diff
				line = re.sub(aPosition, extruderModifier+str(newA)+" (%s)"%aPosition, line)
		modifiedSecondPart.append(line)

	data = firstPart + '\n'.join(modifiedSecondPart)

	newFilePath = stlFilePath[:-4]+"_graded"+extension
	with open(newFilePath, "wb") as f:
		f.write(data)

	print "\nWrote %s successfully" %newFilePath
	print "You may want to open the file and search for '(end first part)' to ensure everything is sane."
	totalTime = time.time()-startTime
	print 'Total time: %.1fs' %(totalTime)

def find_extrema(data, axis):
	maximum = 0
	minimum = 999999
	for line in data.split("\n"):
		if ";" in line and axis in line and line.index(";") < line.index(axis) or axis not in line:
			pass
		else:
			position = re.findall(r"%s([-.0-9]*)" %axis, line)[0]
			position = float(position)
			#print position
			if position > maximum:
				maximum = position
			elif position < minimum:
				minimum = position
	return maximum, minimum

def gcode_file_splicer(filePath1, filePath2):
	fillA = grab_file(filePath1)
	fillB = grab_file(filePath2)
	splice_gcode(fillA, fillB, "Z", layerHeight*layers+firstLayerHeight)

def tiler(stlFilePath, number, option, start, end, offset = 20, maxZ=9999):
	'''
	Inputs:
	stlFilePath - path to STL file to tile
	number - number of times to repeat stlFile
	option - slic3r option to grade
	start - start of range for option
	end - end of range for option
	offset - offset for tiles
	maxZ - if printing large objects and only a few layers are desired, stop at this height
	maxZ easier to determine with firstLayerHeight + layers*layerHeight

	Outputs:
	string containing g-code fit to plate size and tiled with number of graded entries
	'''

	with open(configFile, "rb") as f:
		configuration = f.readlines()

	bedX, bedY = [line.split("=")[1].strip().split(",") for line in configuration if "bed_size" in line][0]
	print "Maximum bedx: %s bedy: %s" %(bedX, bedY)

	delta = float((end-start))/float(number)

	variables = np.arange(start, end+delta, delta)
	variables = [str(var) for var in variables]

	print "Slicing %s at %s" %(option, variables)
	print "Start: %s End: %s Number: %s" %(start, end, number)

	with open("gCode", "wb") as f:
		f.write("; split file")

	gCode = os.getcwd() + "/gCode"

	gcodeData = command_slic3r(stlFilePath)

	xSizeMax, xSizeMin = find_extrema(gcodeData, "X")
	ySizeMax, ySizeMin = find_extrema(gcodeData, "Y")
	print "MAX: ", xSizeMax, ySizeMax 
	print_center_x, print_center_y = 20, 20

	tiles = []
	for index, var in enumerate(variables):

		print_center_x += (index+1)*(xSizeMax+offset)

		if (print_center_x + (xSizeMax/1.7)) > bedX:
			print "BIGGER THAN BED!"
			print_center_x = offset+xSizeMax
			print_center_y += ySizeMax+offset

		print "(x,y): %s, %s Maxes: (%s, %s)" %(print_center_x, print_center_y, xSizeMax, ySizeMax)

		if index == 0:
			options = [option, var, "--end-gcode", gCode, '--print-center', '%s,%s' %(print_center_x, print_center_y)]
		elif index < len(variables):
			options = [option, var, "--start-gcode", gCode, "--end-gcode", gCode, '--print-center', '%s,%s' %(print_center_x, print_center_y)]
		else:
			options = [option, var, "--start-gcode", gCode, '--print-center', '%s,%s' %(print_center_x, print_center_y)]

		data = command_slic3r(stlFilePath, options)

		data = offsetter(data, int(index)*offset, "X")
		tiles.append(data)

	with open("tiled.ngc", "wb") as f:
		f.write("\n".join(tiles))

	'''
	densityData = command_slic3r(stlFilePath)
	fillA, fillB = densityData

	for data in [fillA]:
		for axis in ["X", "Y", "Z", "A"]:
			maximum, minimum = find_extrema(axis, data)
			print "%s max: %f min: %f" %(axis, maximum, minimum) 

	newB = offsetter(fillB, find_extrema("X", fillA)[0]+10, "X")

	with open("offsetFile.ngc", "wb") as f:
		newBLines = newB.split("\n")
		fillBLines = fillB.split("\n")
		data = zip(fillBLines, newBLines)
		data = [A+" | " + B for A,B in data]
		data = '\n'.join(data)
		f.write(data)
	'''
def slice_file(stlFilePath):
	'''
	This function slices an STL into separate densities.
	'''

	densityData = command_slic3r(stlFilePath)
	fillA, fillB = densityData
	splice_gcode(fillA, fillB, "Z", layerHeight*layers+firstLayerHeight)

def offsetter(data, offset, axis):
	'''
	Offsets all coordinates in data corresponding to axis by offset
	'''
	offset = float(offset)

	newData = []
	for line in data:
		if ";" in line and axis in line and line.index(";") < line.index(axis) or axis not in line:
			pass
		else:
			position = re.findall(r"%s([-.0-9]*)" %axis, line)[0]
			print line
			position = float(position)

			newPosition = position + offset
			line = re.sub(axis+str(position), axis+str(newPosition), line)
		newData.append(line)
	return '\n'.join(newData)

if __name__ == '__main__':
	startTime = time.time()

	if not (configFile and slicerPath):
		print "Please open the script and enter the path for slic3r and the slic3r config file"
		sys.exit()
	if len(sys.argv) > 1:
		stlFilePath = sys.argv[1]
		print 'Using %s as input file...' %stlFilePath
		tiler(stlFilePath, 5, "--fill-density", 0, 1)
		#slice_file(stlFilePath)
	else:
		print "Please enter an stl file or gcode(s) to grade"