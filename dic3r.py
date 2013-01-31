#! /usr/bin/python

import re
import subprocess
import sys
import time
import os
import random
from getopt import getopt

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
		
	#print '\nSlicing %s with options: %s' %(filePath, options)

	command = [slicerPath, '--load', configFile, '--gcode-comments', '--layer-height', str(layerHeight), '--first-layer-height', str(firstLayerHeight)]
	if options:
		command.extend(options)
	command.append(filePath)

	#print command

	# Call slic3r with command line options
	output = subprocess.check_output(command)

	# Grab the output filename from slic3r
	fileName = re.findall("Exporting G-code to (.*)", output)[0]

	# Grab the extension from the filename
	fileExtension = fileName.split('.')[-1]

	# Open up the file that slic3r created
	data = grab_file(fileName)

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
				aPosition = re.findall(r"(%s[-.0-9]*)" %extruderModifier, line)[0]
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
			if position > maximum:
				maximum = position
			elif position < minimum:
				minimum = position
	return maximum, minimum

def gcode_file_splicer(filePath1, filePath2):
	fillA = grab_file(filePath1)
	fillB = grab_file(filePath2)
	splice_gcode(fillA, fillB, "Z", layerHeight*layers+firstLayerHeight)

def get_bed_size():
	with open(configFile, "rb") as f:
		configuration = f.readlines()
	return [line.split("=")[1].strip().split(",") for line in configuration if "bed_size " in line][0]

def tiler(stlFilePath, option, start, end, number, offset=30, maxZ=9999):
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

	bedX, bedY = [line.split("=")[1].strip().split(",") for line in configuration if "bed_size " in line][0]
	bedX, bedY= float(bedX), float(bedY)
	print "Maximum bedx: %s bedy: %s" %(bedX, bedY)

	# ; retract_length = 1
	retractionDistance = [int(line.split("=")[1].strip()) for line in configuration if "retract_length " in line][0]
	print "Retraction distance: ", retractionDistance

	# ; extrusion_axis = A
	extrusionAxis = [line.split("=")[1].strip() for line in configuration if "extrusion_axis " in line][0]
	print "extrusionAxis: ", extrusionAxis
	delta = float((end-start))/float(number-1)

	variables = [str(start+index*delta) for index in range(number)]

	print "Slicing %s at %s" %(option, variables)
	print "Start: %s End: %s Number: %s" %(start, end, number)

	with open("gCode", "wb") as f:
		f.write("; split file")

	gCode = os.getcwd() + "/gCode"

	gcodeData = command_slic3r(stlFilePath, ['--start-gcode', gCode, '--end-gcode', gCode])

	xmax, xmin = find_extrema(gcodeData, "X")
	ymax, ymin = find_extrema(gcodeData, "Y")
	
	xSizeMax = xmax-xmin
	ySizeMax = ymax-ymin

	startX, startY = 20, 20
	print_center_x, print_center_y = 20, 20
	
	aPosition = 0

	tiles = []

	centers = []

	for index, var in enumerate(variables):

		if print_center_y > bedY:
			print "Please reduce the number of prints!" 
			print "Rerun with a smaller number of prints."
			break

		print "Centering at (x,y): %s and %s Maxes: (%s and %s)" %(print_center_x, print_center_y, xSizeMax, ySizeMax)

		if index == 0:
			options = [option, var, "--end-gcode", gCode, '--print-center', '%s,%s' %(print_center_x, print_center_y)]
		elif index < len(variables)-1:
			options = [option, var, "--start-gcode", gCode, "--end-gcode", gCode, '--print-center', '%s,%s' %(print_center_x, print_center_y)]
		else:
			options = [option, var, "--start-gcode", gCode, '--print-center', '%s,%s' %(print_center_x, print_center_y)]

		data = command_slic3r(stlFilePath, options)

		if index:
			dataLines = data.split("\n")
			dataStart = 0
			for lineFinder, line in enumerate(dataLines):
				if ("G0" not in line) and ("G1" not in line):
					continue
				else:
					dataStart = lineFinder
					break

			data = '\n'.join(dataLines[dataStart:])

			extrusionEndPosition, extrusionStart = find_extrema(data, "A")
			data = offsetter(data, lastExtrusionEnd+retractionDistance, "A")

		lastExtrusionEnd, extrusionStart = find_extrema(data, "A")
		lastXmax, a = find_extrema(data, "X")
		lastYmax, a = find_extrema(data, "Y")

		centers.append((var, print_center_x, print_center_y))

		tiles.append(data)

		print_center_x = lastXmax+offset

		if (print_center_x + (xSizeMax)/float(2)) > bedX:
			print_center_x = startX
			print_center_y = lastYmax+offset

	tiledFileName = "tiled.ngc"
	with open(tiledFileName, "wb") as f:
		f.write("\n".join(tiles))

	print "Wrote file %s successfully." %tiledFileName
	print "The following %s are centered at:" %option
	for var, x, y in centers:
		print "Param: %.4f (%s, %s)" %(float(var), x, y)


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
	for line in data.split("\n"):
		if ";" in line and axis in line and line.index(";") < line.index(axis) or axis not in line:
			pass
		else:
			position = re.findall(r"%s([-.0-9]*)" %axis, line)[0]
			position = float(position)
			newPosition = position + offset
			line = re.sub(axis+str(position), axis+str(newPosition), line)
		newData.append(line)
	return '\n'.join(newData)

if __name__ == '__main__':
	startTime = time.time()

	#elif len(sys.argv) == 2:
	#		tiler(sys.argv[1], "--"+"extrusion-multiplier", .9, 1.1, 25)
	#

	if not (configFile and slicerPath):
		print "Please open the script and enter the path for slic3r and the slic3r config file"
		sys.exit()

	if True:
		#stlFilePath = sys.argv[1]
		print "Welcome to the calibrator!"
		print "Your first option: What do you want to calibrate?\n"
		choice = ''
		while not choice:
			options = ["bed leveling", "fill density", "extrusion multiplier"]
			for index, option in enumerate(options):
				print "[%s] %s" %(index, option)
			selection = raw_input("\nPick something to calibrate > ")
			try:
				selection = int(selection)
				choice = options[selection]
			except:
				pass

		bedX, bedY = get_bed_size()
		print_center_x, print_center_y = float(bedX)/2., float(bedY)/2.


		if choice == "bed leveling":
			numSkirts = 15
			outputFilename = "bed_calibration"+extension
			skirtDistance = print_center_x - 10
			print "\nYour bed is %s by %s, centering at (%s, %s) and printing a skirt %s from the object" %(bedX, bedY, print_center_x, print_center_y, skirtDistance)
			command_slic3r(os.getcwd()+"/20mm-box.stl", ['--print-center', '%s,%s' %(print_center_x, print_center_y), 
														 "--skirts", str(numSkirts), 
														 "--skirt-distance", str(skirtDistance),
														 "-o", outputFilename])
			print "Bed leveling with %s skirts, stop your printer when the bed is levelled." %numSkirts
			print "The output file is located at", outputFilename 
			
		elif choice == "fill density":
			start = -1
			while start < 0:
				start = raw_input("What would you like this parameter to start at? > ")
				try:
					start = float(start)
				except:
					pass
			end = ''
			while not end:
				end = raw_input("What would you like this parameter to end at? > ")
				try:
					end = float(end)
				except:
					print "Invalid number!"
					pass

			number = ''
			while not number:
				inp = raw_input("How many do you want in between? >")
				try:
					int(inp)
					if int(inp) > 1:
						number = int(inp) 
				except:
					print "Number must be greater than 1"
					pass

			print "Generating gcode for %s starting at %s ending at %s broken into %s chunks" %(option, start, end, number)
			tiler(stlFilePath, "--"+option, start, end, number)
			#slice_file(stlFilePath)

		elif choice == "extrusion multiplier":
			gotStartingValue = False
			while not gotStartingValue:
				startValue = raw_input("Do you want to start at 1? (y or number) > ")
				if startValue.lower() == "y": 
					startExtrusion = 1
					gotStartingValue = True
				else:
					try:
						startExtrusion = float(startValue)
						gotStartingValue = True
					except:
						print "I need a number"

			print "Generating output file now..."
			outputFilename = "extrusion_multiplier_calibration"+extension
			extrusion_multiplier = lambda extrusionMultiplier: command_slic3r(os.getcwd()+"/0.5mm-thin-wall.stl", 
												["--print-center", "%s,%s" %(print_center_x, print_center_y), 
												 "--extrusion-multiplier", str(extrusionMultiplier),
												 "--skirts", "2", 
												 "--skirt-distance", "10",
												 "-o", outputFilename])

			extrusion_multiplier(startExtrusion)

			print "\nOutput file: %s" %outputFilename
			print "When you print it, come back and enter the actual thickness of the walls (measured with a caliper), then I'll make you a new file."
			print "You can type 'q' to quit."
			while True:
				actual_thickness = raw_input("\nActual thickness? (in mm)\n(enter multiple numbers and I'll take the average) > ")
				if actual_thickness.lower() == "q":
					print "Thanks for  calibrating!"
					sys.exit()
				
				if " " in actual_thickness:
					numbers = actual_thickness.split(" ")
					actual_thickness = sum([float(num) for num in numbers])/float(len(numbers))
					print "The average wall thickness is:", actual_thickness

				try:	
					actual_thickness = float(actual_thickness)
					if actual_thickness == 5:
						print "Right on! You could be done!"
					else:
						startExtrusion = 5*startExtrusion/actual_thickness
						print "The new extrusion multiplier is %s" %startExtrusion
						print "Generating output now... "
						extrusion_multiplier(startExtrusion)
						print "\nOutput file: %s" %outputFilename

				except:
					print "Need a number..."